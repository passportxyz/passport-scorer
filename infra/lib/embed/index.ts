import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import { TargetGroup, ListenerRule } from "@pulumi/aws/lb";
import { Listener } from "@pulumi/aws/alb";
import * as command from "@pulumi/command";
import { secretsManager } from "infra-libs";
import { stack, defaultTags } from "../tags";

export function createEmbedLambda(config: {
  name: string;
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListener: pulumi.Output<Listener>;
  ceramicCacheScorerId: number;
  scorerSecret: aws.secretsmanager.Secret;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcPrivateSubnetIds: pulumi.Output<any>;
}) {
  const apiLambdaEnvironment = [
    ...secretsManager.getEnvironmentVars({
      vault: "DevOps",
      repo: "passport-scorer",
      env: stack,
      section: "api",
    }),
    {
      name: "DEBUG",
      value: "off",
    },
    {
      name: "LOGGING_STRATEGY",
      value: "structlog_json",
    },
    {
      name: "FF_API_ANALYTICS",
      value: "on",
    },
    {
      name: "CERAMIC_CACHE_SCORER_ID",
      value: `${config.ceramicCacheScorerId}`,
    },
    {
      name: "SCORER_SERVER_SSM_ARN",
      value: config.scorerSecret.arn,
    },
    {
      name: "VERIFIER_URL",
      value: "http://core-alb.private.gitcoin.co/verifier/verify",
    },
  ].sort(secretsManager.sortByName);

  const lambdaLoggingPolicyDocument = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        actions: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ],
        resources: ["arn:aws:logs:*:*:*"],
      },
    ],
  });

  const lambdaEc2PolicyDocument = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        actions: [
          "ec2:DescribeNetworkInterfaces",
          "ec2:CreateNetworkInterface",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeInstances",
          "ec2:AttachNetworkInterface",
        ],
        resources: ["*"],
      },
    ],
  });

  const lambdaSecretsManagerPolicyDocument = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        actions: ["secretsmanager:GetSecretValue"],
        resources: ["arn:aws:secretsmanager:*:*:*"],
      },
    ],
  });

  const lambdaLoggingPolicy = new aws.iam.Policy(
    `${config.name}-logging-policy`,
    {
      path: "/",
      description: "IAM policy for logging from a lambda",
      policy: lambdaLoggingPolicyDocument.then(
        (lambdaLoggingPolicyDocument) => lambdaLoggingPolicyDocument.json
      ),
      tags: { ...defaultTags, Name: `${config.name}-logging-policy` },
    }
  );

  const lambdaEc2Policy = new aws.iam.Policy(`${config.name}-ec2-policy`, {
    path: "/",
    description: "IAM policy for interfacing with EC2 network",
    policy: lambdaEc2PolicyDocument.then(
      (lambdaEc2PolicyDocument) => lambdaEc2PolicyDocument.json
    ),
    tags: { ...defaultTags, Name: `${config.name}-ec2-policy` },
  });

  const lambdaSecretsManagerPolicy = new aws.iam.Policy(
    `${config.name}-secret-manager-policy`,
    {
      path: "/",
      description: "IAM policy for interfacing with SecretManager network",
      policy: lambdaSecretsManagerPolicyDocument.then(
        (lambdaSecretsManagerPolicyDocument) =>
          lambdaSecretsManagerPolicyDocument.json
      ),
      tags: { ...defaultTags, Name: `${config.name}-secret-manager-policy` },
    }
  );

  const assumeRole = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        principals: [
          {
            type: "Service",
            identifiers: ["lambda.amazonaws.com"],
          },
        ],
        actions: ["sts:AssumeRole"],
      },
    ],
  });

  const lambdaRole = new aws.iam.Role(`${config.name}`, {
    name: config.name,
    assumeRolePolicy: assumeRole.then((assumeRole) => assumeRole.json),
    tags: {
      ...defaultTags,
      Name: `${config.name}`,
    },
  });

  const lambdaLogRoleAttachment = new aws.iam.RolePolicyAttachment(
    `${config.name}-log-role-attachment`,
    {
      role: lambdaRole.name,
      policyArn: lambdaLoggingPolicy.arn,
    }
  );

  const lambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment(
    `${config.name}-ec2-role-attachment`,
    {
      role: lambdaRole.name,
      policyArn: lambdaEc2Policy.arn,
    }
  );

  const lambdaSecretsManagerRoleAttachment = new aws.iam.RolePolicyAttachment(
    `${config.name}-secret-manager-role-attachment`,
    {
      role: lambdaRole.name,
      policyArn: lambdaSecretsManagerPolicy.arn,
    }
  );

  const cmd =
    "cd ../../api && poetry export -f requirements.txt -o requirements.txt && poetry run pip install \
    --platform manylinux2014_x86_64 \
    --target=../infra/aws/python/lib/python3.12/site-packages/ \
    --implementation cp \
    --only-binary=:all: --upgrade \
    -r requirements.txt";

  const poetryLock = archive.getFile({
    type: "zip",
    outputPath: "__pythonDeps.zip",
    sourceFile: "../../api/poetry.lock",
  });

  const layerFolder = new command.local.Command("lambda-python-dependencies", {
    create: cmd,
    update: cmd,
    archivePaths: ["python/**", "!**__pycache__**"],
    triggers: [poetryLock.then((pLock) => pLock.outputBase64sha256)],
  });

  // const output = pythonDeps.stdout;

  // The layer will contain all the dependencies we have installed
  const lambdaArchive = archive.getFile({
    type: "zip",
    outputPath: "test.zip",
    sourceDir: "./__layer",
    excludes: ["**/__pycache__"],
  });
  // const layerArchive = new pulumi.asset.FileArchive("../../api/layer.zip");

  // TODO: create this bucket externally
  const codeBucketName = `${config.name}-code-bucket-123`;
  const bucket = new aws.s3.Bucket(codeBucketName, {
    bucket: codeBucketName,
    versioning: {
      enabled: true,
    },
    tags: {
      ...defaultTags,
      Name: codeBucketName,
    },
  });

  const layerBucketObjectName = `${config.name}-layer-code.zip`;

  // The layer will contain all the dependencies we have installed
  const bucketObject = new aws.s3.BucketObject(
    layerBucketObjectName,
    {
      bucket: bucket.id, // reference to the bucket we created above
      // sourceHash: layerFolder.archive.apply(a)  => accessLogsBucket.o),
      source: layerFolder.archive,
      sourceHash: poetryLock.then((pLock) => pLock.outputBase64sha256),
      // source: "test.zip",
      // sourceHash: lambdaArchive.then((pLock) => pLock.outputBase64sha256),
      tags: {
        ...defaultTags,
        Name: layerBucketObjectName,
      },
    },
    { dependsOn: [layerFolder] }
  );

  // The layer will contain all the dependencies we have installed
  // const bucketObject = new aws.s3.BucketObject(
  //   layerBucketObjectName,
  //   {
  //     bucket: bucket.id, // reference to the bucket we created above
  //     source: layerArchive,
  //     // sourceHash: layerArchive.((layerArchive) => archive.outputBase64sha256),
  //     tags: {
  //       ...defaultTags,
  //       Name: layerBucketObjectName,
  //     },
  //   },
  //   { dependsOn: [pythonDeps] }
  // );

  // const bucketTestObject = new aws.s3.BucketObject(
  //   "test-4.zip",
  //   {
  //     bucket: bucket.id, // reference to the bucket we created above
  //     // source: "test.zip", // Pulumi Asset representing the files
  //     source: pythonDeps.archive,
  //     // sourceHash: pythonDeps.archive.apply(a => a.),
  //   },
  //   { dependsOn: [pythonDeps] }
  // );

  const layerName = `passport-${stack}-scorer-python-deps`;
  const lambdaLayer = new aws.lambda.LayerVersion(
    layerName,
    {
      s3Bucket: bucket.id,
      s3Key: bucketObject.id,
      s3ObjectVersion: bucketObject.versionId,
      layerName: layerName,
      compatibleRuntimes: [aws.lambda.Runtime.Python3d12],
    },
    { dependsOn: [bucketObject] }
  );

  // The lambda will contain our own code (everything from the `api` folder for now)
  const lambdaCode = archive.getFile({
    type: "zip",
    sourceDir: "../../api",
    outputPath: "lambda_function_payload.zip",
    excludes: ["**/__pycache__"],
  });

  const lambdaName = `${config.name}-lambda`;
  const lambda = new aws.lambda.Function(
    lambdaName,
    {
      name: lambdaName,
      vpcConfig: {
        // vpcId: vpc.vpcId,
        securityGroupIds: [config.privateSubnetSecurityGroup.id],
        subnetIds: config.vpcPrivateSubnetIds,
      },
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      role: lambdaRole.arn,
      handler: "embed.lambda.lambda_handler", // TODO: change this
      // TODO: check if we need the hash here, given that we have it in the layer
      sourceCodeHash: lambdaCode.then((archive) => archive.outputBase64sha256),
      runtime: aws.lambda.Runtime.Python3d12,
      environment: {
        variables: apiLambdaEnvironment.reduce(
          (
            acc: { [key: string]: pulumi.Input<string> },
            e: { name: string; value: pulumi.Input<string> }
          ) => {
            acc[e.name] = e.value;
            return acc;
          },
          {}
        ),
      },
      memorySize: 128,
      timeout: 60,
      layers: [lambdaLayer.arn],
      tags: {
        ...defaultTags,
        Name: lambdaName,
      },
    },
    {}
  );

  // Create alarm to monitor lambda errors
  const metricAlarmName = `${config.name}-lambda-errors`;
  const lambdaErrorsAlarm = new aws.cloudwatch.MetricAlarm(metricAlarmName, {
    tags: { ...defaultTags, Name: metricAlarmName },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    datapointsToAlarm: 1,
    dimensions: {
      FunctionName: lambdaName,
    },
    evaluationPeriods: 24,
    metricName: "Errors",
    name: metricAlarmName,
    namespace: "AWS/Lambda",
    period: 60 * 60, // 1 hours
    unit: "Seconds",
    statistic: "SampleCount",
    treatMissingData: "notBreaching",
    threshold: 1,
  });

  ///////////////////////////////////////////////////////////////////////////
  const lambdaTargetGroup = new aws.lb.TargetGroup(
    `${config.name}-lambda-target-group`,
    {
      name: `${config.name}-lambda-target-group`,
      targetType: "lambda",
      tags: { ...defaultTags, Name: `${config.name}-lambda` },
    }
  );

  const withLb = new aws.lambda.Permission(`${config.name}-lambda-permission`, {
    action: "lambda:InvokeFunction",
    function: lambda.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: lambdaTargetGroup.arn,
  });
  const lambdaTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    `${config.name}-lambda-target-group-attachment`,
    {
      targetGroupArn: lambdaTargetGroup.arn,
      targetId: lambda.arn,
    },
    {
      dependsOn: [withLb],
    }
  );

  const conditions: any = [
    {
      pathPattern: {
        values: ["/test"],
      },
    },
    {
      httpRequestMethod: {
        values: ["POST"],
      },
    },
  ];

  const targetPassportRule = new ListenerRule(`${config.name}-rule-lambda`, {
    tags: { ...defaultTags, Name: `${config.name}-rule-lambda` },
    listenerArn: config.httpsListener.arn,
    priority: 12345,
    actions: [
      {
        type: "forward",
        targetGroupArn: lambdaTargetGroup.arn,
      },
    ],
    conditions,
  });
}