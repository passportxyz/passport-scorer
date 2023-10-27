import { LogGroup } from "@pulumi/aws/cloudwatch/logGroup";
import { Role } from "@pulumi/aws/iam/role";
import * as awsx from "@pulumi/awsx";
import { Input, Output, interpolate } from "@pulumi/pulumi";
import { TargetGroup, ListenerRule } from "@pulumi/aws/lb";
import * as aws from "@pulumi/aws";

import { Cluster } from "@pulumi/aws/ecs";
import { Topic } from "@pulumi/aws/sns";
import { Listener } from "@pulumi/aws/alb";
import { SecurityGroup } from "@pulumi/aws/ec2";
import { RolePolicyAttachment } from "@pulumi/aws/iam";

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;

export type ScorerService = {
  dockerImageScorer: Input<string>;
  dockerImageVerifier: Input<string>;
  securityGroup: aws.ec2.SecurityGroup;
  executionRole: Role;
  cluster: Cluster;
  logGroup: LogGroup;
  subnets: Input<Input<string>[]>;
  needsVerifier: boolean;
  httpListenerArn: Input<string>;
  httpListenerRulePaths?: Input<Input<string>[]>;
  listenerRulePriority?: Input<number>;
  targetGroup: TargetGroup;
  autoScaleMaxCapacity?: number;
  autoScaleMinCapacity?: number;
  alb: aws.lb.LoadBalancer;
  alertTopic?: Topic;
  cpu?: number;
  memory?: number;
  desiredCount?: number;
};

export type ScorerEnvironmentConfig = {
  domain: Input<string>;
  rdsConnectionUrl: Input<string>;
  uiDomains: Input<string>;
  allowedHosts: Input<string>;
  csrfTrustedOrigins: Input<string>;
  redisCacheOpsConnectionUrl: Input<string>;
  debug?: Input<string>;
  readReplicaConnectionUrl?: Input<string>;
  passportPublicUrl?: Input<string>;
};

export const secrets = [
  {
    name: "SECRET_KEY",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:SECRET_KEY::`,
  },
  {
    name: "GOOGLE_OAUTH_CLIENT_ID",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:GOOGLE_OAUTH_CLIENT_ID::`,
  },
  {
    name: "GOOGLE_CLIENT_SECRET",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:GOOGLE_CLIENT_SECRET::`,
  },
  {
    name: "RATELIMIT_ENABLE",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:RATELIMIT_ENABLE::`,
  },
  {
    name: "TRUSTED_IAM_ISSUER",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:TRUSTED_IAM_ISSUER::`,
  },
  {
    name: "CERAMIC_CACHE_SCORER_ID",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:CERAMIC_CACHE_SCORER_ID::`,
  },
  {
    name: "FF_API_ANALYTICS",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:FF_API_ANALYTICS::`,
  },
  {
    name: "FF_DEDUP_WITH_LINK_TABLE",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:FF_DEDUP_WITH_LINK_TABLE::`,
  },
  {
    name: "CGRANTS_API_TOKEN",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:CGRANTS_API_TOKEN::`,
  },
  {
    name: "S3_DATA_AWS_SECRET_KEY_ID",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:S3_DATA_AWS_SECRET_KEY_ID::`,
  },
  {
    name: "S3_DATA_AWS_SECRET_ACCESS_KEY",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:S3_DATA_AWS_SECRET_ACCESS_KEY::`,
  },
  {
    name: "S3_WEEKLY_BACKUP_BUCKET_NAME",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:S3_WEEKLY_BACKUP_BUCKET_NAME::`,
  },
  {
    name: "REGISTRY_API_READ_DB",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:REGISTRY_API_READ_DB::`,
  },
  {
    name: "STAKING_SUBGRAPH_API_KEY",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:STAKING_SUBGRAPH_API_KEY::`,
  },
];

export function getEnvironment(config: ScorerEnvironmentConfig) {
  return [
    {
      name: "DEBUG",
      value: config.debug || "off",
    },
    {
      name: "DATABASE_URL",
      value: config.rdsConnectionUrl,
    },
    {
      name: "READ_REPLICA_0_URL",
      value: config.readReplicaConnectionUrl || config.rdsConnectionUrl,
    },
    {
      name: "UI_DOMAINS",
      value: config.uiDomains,
    },
    {
      name: "ALLOWED_HOSTS",
      value: JSON.stringify([config.domain, "*"]),
    },
    {
      name: "CSRF_TRUSTED_ORIGINS",
      value: JSON.stringify([`https://${config.domain}`]),
    },
    {
      name: "CELERY_BROKER_URL",
      value: config.redisCacheOpsConnectionUrl,
    },
    {
      name: "CERAMIC_CACHE_CACAO_VALIDATION_URL",
      value: "http://localhost:8001/verify",
    },
    {
      name: "SECURE_SSL_REDIRECT",
      value: "off",
    },
    {
      name: "SECURE_PROXY_SSL_HEADER",
      value: JSON.stringify(["HTTP_X_FORWARDED_PROTO", "https"]),
    },
    {
      name: "LOGGING_STRATEGY",
      value: "structlog_json",
    },
    {
      name: "PASSPORT_PUBLIC_URL",
      value: config.passportPublicUrl || "https://passport.gitcoin.co/",
    },
  ];
}

export function createTargetGroup(
  name: string,
  vpcId: Input<string>
): TargetGroup {
  return new TargetGroup(name, {
    tags: { name: name },
    port: 80,
    protocol: "HTTP",
    vpcId: vpcId,
    targetType: "ip",
    healthCheck: { path: "/health/", unhealthyThreshold: 5 },
  });
}

export function createScorerECSService(
  name: string,
  config: ScorerService,
  envConfig: ScorerEnvironmentConfig
): awsx.ecs.FargateService {
  //////////////////////////////////////////////////////////////
  // Create target group and load balancer rules
  //////////////////////////////////////////////////////////////

  if (config.httpListenerRulePaths) {
    const targetPassportRule = new ListenerRule(`lrule-${name}`, {
      tags: { name: name },
      listenerArn: config.httpListenerArn,
      priority: config.listenerRulePriority,
      actions: [
        {
          type: "forward",
          targetGroupArn: config.targetGroup.arn,
        },
      ],
      conditions: [
        {
          pathPattern: {
            values: config.httpListenerRulePaths,
          },
        },
      ],
    });
  }

  //////////////////////////////////////////////////////////////
  // Create the task definition and the service
  //////////////////////////////////////////////////////////////

  const containers: Record<
    string,
    awsx.types.input.ecs.TaskDefinitionContainerDefinitionArgs
  > = {
    scorer: {
      name: "scorer",
      image: config.dockerImageScorer,
      memory: config.memory ? config.memory : 4096,
      cpu: config.cpu ? config.cpu : 4096,
      portMappings: [{ containerPort: 80, hostPort: 80 }],
      command: [
        "gunicorn",
        "-w",
        "4",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "scorer.asgi:application",
        "-b",
        "0.0.0.0:80",
      ],
      links: [],
      secrets: secrets,
      environment: getEnvironment(envConfig),
      linuxParameters: {
        initProcessEnabled: true,
      },
    },
  };

  if (config.needsVerifier) {
    containers.verifier = {
      name: "verifier",
      image: config.dockerImageVerifier,
      memory: 512,
      links: [],
      portMappings: [
        {
          containerPort: 8001,
          hostPort: 8001,
        },
      ],
      environment: [
        {
          name: "VERIFIER_PORT",
          value: "8001",
        },
      ],
      linuxParameters: {
        initProcessEnabled: true,
      },
    };
  }

  const service = new awsx.ecs.FargateService(name, {
    propagateTags: "TASK_DEFINITION",
    tags: { name: name },
    cluster: config.cluster.arn,
    desiredCount: config.desiredCount ? config.desiredCount : 1,
    networkConfiguration: {
      subnets: config.subnets,
      securityGroups: [config.securityGroup.id],
    },
    loadBalancers: [
      {
        containerName: "scorer",
        containerPort: 80,
        targetGroupArn: config.targetGroup.arn,
      },
    ],
    taskDefinitionArgs: {
      tags: { name: name },
      logGroup: {
        existing: config.logGroup,
      },
      executionRole: {
        roleArn: config.executionRole.arn,
      },
      containers,
    },
  });

  const ecsScorerServiceAutoscalingTarget = new aws.appautoscaling.Target(
    `autoscale-target-${name}`,
    {
      tags: { name: name },
      maxCapacity: config.autoScaleMaxCapacity
        ? config.autoScaleMaxCapacity
        : 20,
      minCapacity: config.autoScaleMinCapacity
        ? config.autoScaleMinCapacity
        : 1,
      resourceId: interpolate`service/${config.cluster.name}/${service.service.name}`,
      scalableDimension: "ecs:service:DesiredCount",
      serviceNamespace: "ecs",
    }
  );

  const ecsScorerServiceAutoscaling = new aws.appautoscaling.Policy(
    `autoscale-policy-${name}`,
    {
      policyType: "TargetTrackingScaling",
      resourceId: ecsScorerServiceAutoscalingTarget.resourceId,
      scalableDimension: ecsScorerServiceAutoscalingTarget.scalableDimension,
      serviceNamespace: ecsScorerServiceAutoscalingTarget.serviceNamespace,
      targetTrackingScalingPolicyConfiguration: {
        predefinedMetricSpecification: {
          predefinedMetricType: "ECSServiceAverageCPUUtilization",
        },
        targetValue: 30,
        scaleInCooldown: 300,
        scaleOutCooldown: 300,
      },
    }
  );

  if (config.alertTopic) {
    const cpuAlarm = new aws.cloudwatch.MetricAlarm(`CPUUtilization-${name}`, {
      tags: { name: name },
      alarmActions: [config.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      dimensions: {
        ClusterName: config.cluster.name,
        ServiceName: service.service.name,
      },
      evaluationPeriods: 1,
      metricName: "CPUUtilization",
      name: `CPUUtilization-${name}`,
      namespace: "AWS/ECS",
      period: 300,
      statistic: "Average",
      threshold: 80,
    });

    const memoryAlarm = new aws.cloudwatch.MetricAlarm(
      `MemoryUtilization-${name}`,
      {
        tags: { name: name },
        alarmActions: [config.alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 1,
        dimensions: {
          ClusterName: config.cluster.name,
          ServiceName: service.service.name,
        },
        evaluationPeriods: 1,
        metricName: "MemoryUtilization",
        name: `MemoryUtilization-${name}`,
        namespace: "AWS/ECS",
        period: 900,
        statistic: "Average",
        threshold: 80,
      }
    );

    const http5xxAlarm = new aws.cloudwatch.MetricAlarm(`HTTP-5xx-${name}`, {
      tags: { name: name },
      alarmActions: [config.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 3,
      dimensions: {
        LoadBalancer: config.alb.name,
        TargetGroup: config.targetGroup.name,
      },
      evaluationPeriods: 5,
      metricName: "HTTPCode_Target_5XX_Count",
      name: `HTTP-5xx-${name}`,
      namespace: "AWS/ApplicationELB",
      period: 60,
      statistic: "Sum",
      treatMissingData: "notBreaching",
    });
  }

  return service;
}

export async function createScoreExportBucketAndDomain(
  domain: string,
  route53Zone: string
) {
  const scoreBucket = new aws.s3.Bucket(domain, {
    bucket: domain,
    website: {
      indexDocument: "registry_score.jsonl",
    },
  });

  new aws.s3.BucketPublicAccessBlock("myBucketPublicAccessBlock", {
    bucket: scoreBucket.bucket.apply((bucket) => bucket),
    blockPublicAcls: false,
    ignorePublicAcls: false,
    blockPublicPolicy: false,
    restrictPublicBuckets: false,
  });

  const serviceAccount = await aws.elb.getServiceAccount({});

  const bucketPolicy = scoreBucket.arn.apply((arn) =>
    JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Principal: "*",
          Action: "s3:GetObject",
          Resource: `${arn}/*`,
        },
        {
          Effect: "Allow",
          Principal: {
            AWS: serviceAccount.arn,
          },
          Action: ["s3:PutObject", "s3:PutObjectAcl"],
          Resource: `${arn}/*`,
        },
      ],
    })
  );

  new aws.s3.BucketPolicy("bucketPolicy", {
    bucket: scoreBucket.bucket.apply((bucket: any) => bucket),
    policy: bucketPolicy,
  });

  const eastRegion = new aws.Provider("east", {
    profile: aws.config.profile,
    region: "us-east-1", // Per AWS, ACM certificate must be in the us-east-1 region.
  });

  const exportCertificate = new aws.acm.Certificate(
    domain,
    {
      domainName: domain,
      validationMethod: "DNS",
    },
    { provider: eastRegion }
  );

  const publicExportCertificateValidationDomain = new aws.route53.Record(
    `${domain}-validation`,
    {
      name: exportCertificate.domainValidationOptions[0].resourceRecordName,
      zoneId: route53Zone,
      type: exportCertificate.domainValidationOptions[0].resourceRecordType,
      records: [
        exportCertificate.domainValidationOptions[0].resourceRecordValue,
      ],
      ttl: 600,
    },
    { provider: eastRegion }
  );

  const publicCertificateValidation = new aws.acm.CertificateValidation(
    "publicCertificateValidation",
    {
      certificateArn: exportCertificate.arn,
      validationRecordFqdns: [
        publicExportCertificateValidationDomain.fqdn.apply((fqdn) => fqdn),
      ],
    },
    {
      provider: eastRegion,
    }
  );

  const cloudFront = new aws.cloudfront.Distribution(
    "publicExportCloudFront",
    {
      origins: [
        {
          originId: scoreBucket.arn.apply((arn) => arn),
          domainName: scoreBucket.websiteEndpoint.apply(
            (domainName) => domainName
          ),
          customOriginConfig: {
            httpPort: 80,
            httpsPort: 443,
            originKeepaliveTimeout: 5,
            originProtocolPolicy: "http-only",
            originReadTimeout: 30,
            originSslProtocols: ["TLSv1.2"],
          },
        },
      ],
      aliases: [domain],
      defaultRootObject: "registry_score.jsonl",
      enabled: true,
      defaultCacheBehavior: {
        targetOriginId: scoreBucket.arn.apply((arn) => arn),
        allowedMethods: ["GET", "HEAD"],
        cachedMethods: ["GET", "HEAD"],
        forwardedValues: {
          queryString: false,
          cookies: { forward: "none" },
        },
        viewerProtocolPolicy: "redirect-to-https",
      },
      customErrorResponses: [
        {
          errorCode: 404,
          responseCode: 200,
          responsePagePath: "/registry_score.jsonl",
        },
      ],
      restrictions: {
        geoRestriction: {
          restrictionType: "none",
        },
      },
      viewerCertificate: {
        acmCertificateArn: publicCertificateValidation.certificateArn.apply(
          (arn) => arn
        ), // Per AWS, ACM certificate must be in the us-east-1 region.
        sslSupportMethod: "sni-only",
      },
    },
    {}
  );

  new aws.route53.Record(domain, {
    name: domain,
    zoneId: route53Zone,
    type: "A",
    aliases: [
      {
        name: cloudFront.domainName,
        zoneId: cloudFront.hostedZoneId,
        evaluateTargetHealth: false,
      },
    ],
  });

  return {
    exportCertificate,
    publicExportCertificateValidationDomain,
    publicCertificateValidation,
    cloudFront,
  };
}

export const dockerGtcStakingIndexerImage = `${process.env["DOCKER_GTC_PASSPORT_INDEXER_IMAGE"]}`;

export function createIndexerService(
  indexerRdsConnectionUrl: Input<string>,
  cluster: Cluster,
  vpc: awsx.ec2.Vpc,
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup,
  workerRole: Role
) {
  const indexerLogGroup = new aws.cloudwatch.LogGroup("scorer-indexer", {
    retentionInDays: 90,
  });

  const indexerSecrets = [
    {
      name: "RPC_URL",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:RPC_URL::`,
    },
  ];

  const indexerEnvironment = [
    {
      name: "DATABASE_URL",
      value: indexerRdsConnectionUrl,
    },
  ];

  new awsx.ecs.FargateService("scorer-staking-indexer", {
    cluster: cluster.arn,
    desiredCount: 1,
    networkConfiguration: {
      subnets: vpc.privateSubnetIds,
      securityGroups: [privateSubnetSecurityGroup.id],
    },
    taskDefinitionArgs: {
      logGroup: {
        existing: indexerLogGroup,
      },
      executionRole: {
        roleArn: workerRole.arn,
      },
      containers: {
        worker1: {
          name: "indexer-process",
          memory: 1024,
          cpu: 1024,
          image: dockerGtcStakingIndexerImage,
          command: ["cargo", "run"],
          portMappings: [],
          secrets: indexerSecrets,
          environment: indexerEnvironment,
          dependsOn: [],
          links: [],
        },
      },
    },
  });
}

export const createSharedLambdaResources = () => {
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

  const lambdaLoggingPolicy = new aws.iam.Policy("lambdaLoggingPolicy", {
    path: "/",
    description: "IAM policy for logging from a lambda",
    policy: lambdaLoggingPolicyDocument.then(
      (lambdaLoggingPolicyDocument) => lambdaLoggingPolicyDocument.json
    ),
  });

  const lambdaEc2Policy = new aws.iam.Policy("lambdaEc2Policy", {
    path: "/",
    description: "IAM policy for interfacing with EC2 network",
    policy: lambdaEc2PolicyDocument.then(
      (lambdaEc2PolicyDocument) => lambdaEc2PolicyDocument.json
    ),
  });

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

  const lambdaRole = new aws.iam.Role("lambdaRole", {
    assumeRolePolicy: assumeRole.then((assumeRole) => assumeRole.json),
  });

  const lambdaLogRoleAttachment = new aws.iam.RolePolicyAttachment(
    "lambdaLogRoleAttachment",
    {
      role: lambdaRole.name,
      policyArn: lambdaLoggingPolicy.arn,
    }
  );

  const lambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment(
    "lambdaEc2RoleAttachment",
    {
      role: lambdaRole.name,
      policyArn: lambdaEc2Policy.arn,
    }
  );

  return {
    lambdaRole,
    lambdaLogRoleAttachment,
    lambdaEc2RoleAttachment,
  };
};

export function buildLambdaFn({
  name,
  httpsListener,
  listenerPriority,
  imageUri,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  environment,
  lambdaRole,
  lambdaLogRoleAttachment,
  lambdaEc2RoleAttachment,
  pathPatterns,
  memorySize,
  dockerCmd,
  httpRequestMethods,
}: {
  name: string;
  httpsListener: Listener;
  listenerPriority: number;
  imageUri: string;
  privateSubnetSecurityGroup: SecurityGroup;
  vpcPrivateSubnetIds: Output<string[]>;
  environment: { name: string; value: Input<string> }[];
  lambdaRole: Role;
  lambdaLogRoleAttachment: RolePolicyAttachment;
  lambdaEc2RoleAttachment: RolePolicyAttachment;
  pathPatterns: string[];
  memorySize: number;
  dockerCmd: string[];
  httpRequestMethods?: string[];
}) {
  const lambdaTargetGroup = new aws.lb.TargetGroup(`l-${name}`, {
    name: `l-${name}`,
    targetType: "lambda",
  });

  const submitPassportFunction = new aws.lambda.Function(
    name,
    {
      name: name,
      imageConfig: {
        commands: dockerCmd,
      },
      vpcConfig: {
        // vpcId: vpc.vpcId,
        securityGroupIds: [privateSubnetSecurityGroup.id], // TODO: shall we create it's own security group ???
        subnetIds: vpcPrivateSubnetIds,
      },
      packageType: "Image",
      role: lambdaRole.arn,
      imageUri,
      timeout: 60,
      memorySize,
      environment: {
        variables: environment.reduce(
          (
            acc: { [key: string]: Input<string> },
            e: { name: string; value: Input<string> }
          ) => {
            acc[e.name] = e.value;
            return acc;
          },
          {}
        ),
      },
      tags: { name: name },
    },
    {
      dependsOn: [lambdaLogRoleAttachment, lambdaEc2RoleAttachment],
    }
  );

  const withLb = new aws.lambda.Permission(`withLb-${name}`, {
    action: "lambda:InvokeFunction",
    function: submitPassportFunction.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: lambdaTargetGroup.arn,
  });

  const lambdaTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    `lambdaTargetGroupAttachment-${name}`,
    {
      targetGroupArn: lambdaTargetGroup.arn,
      targetId: submitPassportFunction.arn,
    },
    {
      dependsOn: [withLb],
    }
  );

  const conditions: any = [
    {
      pathPattern: {
        values: pathPatterns,
      },
    },
  ];

  if (httpRequestMethods) {
    conditions.push({
      httpRequestMethod: {
        values: httpRequestMethods,
      },
    });
  }

  const targetPassportRule = new ListenerRule(`lrule-lambda-${name}`, {
    tags: { name: `lrule-lambda-${name}` },
    listenerArn: httpsListener.arn,
    priority: listenerPriority,
    actions: [
      {
        type: "forward",
        targetGroupArn: lambdaTargetGroup.arn,
      },
    ],
    conditions,
  });
}
