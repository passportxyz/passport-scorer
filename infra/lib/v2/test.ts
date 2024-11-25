import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import { TargetGroup, ListenerRule } from "@pulumi/aws/lb";
import { Listener } from "@pulumi/aws/alb";
import { local } from "@pulumi/command";
import { secretsManager } from "infra-libs";
import { stack, defaultTags } from "../tags";

export function createTestLambda(config: {
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

  const exportLambdaRole = new aws.iam.Role(`${config.name}`, {
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
      role: exportLambdaRole.name,
      policyArn: lambdaLoggingPolicy.arn,
    }
  );

  const lambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment(
    `${config.name}-ec2-role-attachment`,
    {
      role: exportLambdaRole.name,
      policyArn: lambdaEc2Policy.arn,
    }
  );

  const lambdaSecretsManagerRoleAttachment = new aws.iam.RolePolicyAttachment(
    `${config.name}-secret-manager-role-attachment`,
    {
      role: exportLambdaRole.name,
      policyArn: lambdaSecretsManagerPolicy.arn,
    }
  );

  const pythonDeps = new local.Command("install-python-deps", {
    create:
      "poetry export -f requirements.txt -o requirements.txt && pip install \
    --platform manylinux2014_x86_64 \
    --target=../infra/lib/v2/layer/python/lib/python3.12/site-packages/ \
    --implementation cp \
    --only-binary=:all: --upgrade \
    -r requirements.txt",
    dir: "../../api",
  });

  const lambda = archive.getFile({
    type: "zip",
    outputPath: "test.zip",
    sourceDir: "../lib/v2/layer",
    excludes: ["**/__pycache__"],
  });

  // Create an AWS S3 Bucket to host files
  //   const bucket = new aws.s3.Bucket("my-bucket", {
  //     acl: "private",
  //   });
  const dataExportsBucketName = "passport-lambda-code-bucket-123";
  const bucket = new aws.s3.Bucket(dataExportsBucketName, {
    bucket: dataExportsBucketName,
    versioning: {
      enabled: true,
    },
    tags: {
      ...defaultTags,
      Name: dataExportsBucketName,
    },
  });

  const bucketObject = new aws.s3.BucketObject(
    "test-3.zip",
    {
      bucket: bucket.id, // reference to the bucket we created above
      source: "test.zip", // Pulumi Asset representing the files
      sourceHash: lambda.then((lambda) => lambda.outputBase64sha256),
    },
    { dependsOn: [pythonDeps] }
  );

  const lambdaLayer = new aws.lambda.LayerVersion(
    "lambda_layer",
    {
      s3Bucket: bucket.id,
      s3Key: bucketObject.id,
      s3ObjectVersion: bucketObject.versionId,
      layerName: "lambda_layer_name_1",
      compatibleRuntimes: [aws.lambda.Runtime.Python3d12],
    },
    { dependsOn: [bucketObject] }
  );

  const lambdaCode = archive.getFile({
    type: "zip",
    sourceDir: "../../api",
    outputPath: "lambda_function_payload.zip",
    excludes: ["**/__pycache__"],
  });

  const lambdaName = `${config.name}-incremental-exports`;
  const exportLambda = new aws.lambda.Function(lambdaName, {
    vpcConfig: {
      // vpcId: vpc.vpcId,
      securityGroupIds: [config.privateSubnetSecurityGroup.id],
      subnetIds: config.vpcPrivateSubnetIds,
    },
    code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
    name: lambdaName,
    role: exportLambdaRole.arn,
    handler: "lambda_test.lambda.lambda_handler",
    sourceCodeHash: lambda.then((lambda) => lambda.outputBase64sha256),
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
  });

  // const scheduledEventRuleName = `${config.name}-rule`;
  // const scheduledEventRule = new aws.cloudwatch.EventRule(
  //   scheduledEventRuleName,
  //   {
  //     scheduleExpression: "cron(30 0 ? * * *)", // Trigger this 30 minutes after midnight UTC
  //     tags: {
  //       ...defaultTags,
  //       Name: scheduledEventRuleName,
  //     },
  //   }
  // );

  // Granting EventBridge the necessary permissions to trigger the Lambda function.
  // new aws.lambda.Permission(`${config.name}-permission`, {
  //   action: "lambda:InvokeFunction",
  //   function: exportLambda,
  //   principal: "events.amazonaws.com",
  //   sourceArn: scheduledEventRule.arn,
  // });

  // Target the rule to the lambda
  // const scheduledEventTargetName = `${config.name}-target`;
  // new aws.cloudwatch.EventTarget(scheduledEventTargetName, {
  //   rule: scheduledEventRule.name,
  //   arn: exportLambda.arn,
  // });

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
  const lambdaTargetGroup = new aws.lb.TargetGroup(`l-${config.name}`, {
    name: `l-${config.name}`,
    targetType: "lambda",
    tags: { ...defaultTags, Name: `l-${config.name}` },
  });

  const withLb = new aws.lambda.Permission(`withLb-${config.name}`, {
    action: "lambda:InvokeFunction",
    function: exportLambda.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: lambdaTargetGroup.arn,
  });
  const lambdaTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    `lambdaTargetGroupAttachment-${config.name}`,
    {
      targetGroupArn: lambdaTargetGroup.arn,
      targetId: exportLambda.arn,
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

  //   if (httpRequestMethods) {
  //     conditions.push({
  //       httpRequestMethod: {
  //         values: httpRequestMethods,
  //       },
  //     });
  //   }

  const targetPassportRule = new ListenerRule(`lrule-lambda-${config.name}`, {
    tags: { ...defaultTags, Name: `lrule-lambda-${config.name}` },
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
