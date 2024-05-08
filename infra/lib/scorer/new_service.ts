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
import { LoadBalancerAlarmThresholds } from "./loadBalancer";

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;

export type ScorerService = {
  dockerImageScorer: Input<string>;
  dockerImageVerifier: Input<string>;
  securityGroup: aws.ec2.SecurityGroup;
  executionRole: Role;
  taskRole: Role;
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
  rescoreQueueUrl: Input<string>;
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
    name: "TRUSTED_IAM_ISSUERS",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:TRUSTED_IAM_ISSUERS::`,
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
  // This contains the connection string for the database used in the 'Passport-Data-Science'
  // which is managed by the data team.
  // These are read-only credentials as the model & the db is not managed by the scorer project
  // This is only used for exporting data from that DB
  {
    name: "DATA_MODEL_DATABASE_URL",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:DATA_MODEL_DATABASE_URL::`,
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
    {
      name: "RESCORE_QUEUE_URL",
      value: config.rescoreQueueUrl,
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
  envConfig: ScorerEnvironmentConfig,
  loadBalancerAlarmThresholds: LoadBalancerAlarmThresholds
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
      taskRole: {
        roleArn: config.taskRole.arn,
      },
      containers,
    },
  });

  function getAutoScaleMinCapacity() {
    return config.autoScaleMinCapacity ? config.autoScaleMinCapacity : 2;
  }

  function getAutoScaleMaxCapacity() {
    return config.autoScaleMaxCapacity ? config.autoScaleMaxCapacity : 20;
  }

  const ecsScorerServiceAutoscalingTarget = new aws.appautoscaling.Target(
    `autoscale-target-${name}`,
    {
      tags: { name: name },
      maxCapacity: getAutoScaleMaxCapacity(),
      minCapacity: getAutoScaleMinCapacity(),
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
        targetValue: 50,
        scaleInCooldown: 300,
        scaleOutCooldown: 300,
      },
    }
  );

  if (config.alertTopic) {
    // We want an alarm when the number of running tasks reaches 75% of the configured maximum
    const runningTaskCountAlarm = new aws.cloudwatch.MetricAlarm(
      `RunningTaskCount-${name}`,
      {
        tags: { name: `RunningTaskCount-${name}` },
        alarmActions: [config.alertTopic.arn],
        okActions: [config.alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 1,
        dimensions: {
          ClusterName: config.cluster.name,
          ServiceName: service.service.name,
        },
        evaluationPeriods: 1,
        metricName: "RunningTaskCount",
        name: `RunningTaskCount-${name}`,
        namespace: "AWS/ECS",
        period: 300,
        statistic: "Sum",
        threshold: getAutoScaleMaxCapacity() * 0.75,
      }
    );

    // High memory consumption might indicate an issue with the provisioned memory size, and
    // we should probably increase the size of allocated memory
    const memoryAlarm = new aws.cloudwatch.MetricAlarm(
      `MemoryUtilization-${name}`,
      {
        tags: { name: `MemoryUtilization-${name}` },
        alarmActions: [config.alertTopic.arn],
        okActions: [config.alertTopic.arn],
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

    // We want alarm to monitor:
    // - 5xx errors in individual targets
    // - 4xx errors in individual targets
    // - 5xx errors in elb
    // - 4xx errors in elb
    // - target response time

    const metricNamespace = "AWS/ApplicationELB";
    /*
     * Alarm for monitoring target 5XX errors
     */
    const http5xxTargetAlarm = new aws.cloudwatch.MetricAlarm(
      `HTTP-Target-5XX-${name}`,
      {
        tags: { name: `HTTP-Target-5XX-${name}` },
        name: `HTTP-Target-5XX-${name}`,
        alarmActions: [config.alertTopic.arn],
        okActions: [config.alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        evaluationPeriods: 5,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCountPerTarget",
              dimensions: {
                LoadBalancer: config.alb.name,
                TargetGroup: config.targetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_5XX_Count",
              dimensions: {
                LoadBalancer: config.alb.name,
                TargetGroup: config.targetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 5XX errors",
            returnData: true,
          },
        ],
        threshold: loadBalancerAlarmThresholds.percentHTTPCodeTarget5XX,
      }
    );

    /*
     * Alarm for monitoring target 4XX errors
     */
    const http4xxTargetAlarm = new aws.cloudwatch.MetricAlarm(
      `HTTP-Target-4XX-${name}`,
      {
        tags: { name: `HTTP-Target-4XX-${name}` },
        name: `HTTP-Target-4XX-${name}`,
        alarmActions: [config.alertTopic.arn],
        okActions: [config.alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        evaluationPeriods: 5,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCountPerTarget",
              dimensions: {
                LoadBalancer: config.alb.name,
                TargetGroup: config.targetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_4XX_Count",
              dimensions: {
                LoadBalancer: config.alb.name,
                TargetGroup: config.targetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 4XX errors",
            returnData: true,
          },
        ],
        threshold: loadBalancerAlarmThresholds.percentHTTPCodeTarget4XX,
      }
    );

    // We want an alarm to monitor for the average response time
    const targetResponseTimeAlarm = new aws.cloudwatch.MetricAlarm(
      `TargetResponseTime-${name}`,
      {
        tags: { name: `TargetResponseTime-${name}` },
        alarmActions: [config.alertTopic.arn],
        okActions: [config.alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        dimensions: {
          LoadBalancer: config.alb.name,
          TargetGroup: config.targetGroup.name,
        },
        evaluationPeriods: 5,
        metricName: "TargetResponseTime",
        name: `TargetResponseTime-${name}`,
        namespace: "AWS/ApplicationELB",
        period: 60,
        statistic: "Average",
        treatMissingData: "notBreaching",
        threshold: loadBalancerAlarmThresholds.targetResponseTime,
        unit: "Seconds",
      }
    );
  }

  return service;
}

export async function createScoreExportBucketAndDomain(
  bucketName: string,
  domain: string,
  route53Zone: string
) {
  const scoreBucket = new aws.s3.Bucket(domain, {
    bucket: bucketName,
    website: {
      indexDocument: "registry_score.jsonl",
    },
    tags: { name: `s3-domain` },
  });

  new aws.s3.BucketPublicAccessBlock(
    "myBucketPublicAccessBlock",
    {
      bucket: scoreBucket.bucket.apply((bucket) => bucket),
      blockPublicAcls: false,
      ignorePublicAcls: false,
      blockPublicPolicy: false,
      restrictPublicBuckets: false,
    },
    { dependsOn: [scoreBucket] }
  );

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

  new aws.s3.BucketPolicy(
    "bucketPolicy",
    {
      bucket: scoreBucket.bucket.apply((bucket: any) => bucket),
      policy: bucketPolicy,
    },
    { dependsOn: [scoreBucket] }
  );

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
      tags: { name: "publicExportCloudFront" },
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

type IndexerServiceParams = {
  rdsConnectionConfig: {
    dbHost: Output<any>;
    dbPort: string;
  };
  rdsSecretArn: Output<any>;
  cluster: Cluster;
  vpc: Output<any>;
  privateSubnetIds: Output<any>;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  workerRole: Role;
  alertTopic: aws.sns.Topic;
};

export function createIndexerService({
  rdsConnectionConfig,
  rdsSecretArn,
  cluster,
  vpc,
  privateSubnetIds,
  privateSubnetSecurityGroup,
  workerRole,
  alertTopic,
}: IndexerServiceParams) {
  const indexerLogGroup = new aws.cloudwatch.LogGroup("scorer-indexer", {
    retentionInDays: 90,
  });

  const indexerSecrets = rdsSecretArn.apply((rdsSecret) => [
    {
      name: "DB_USER",
      valueFrom: `${rdsSecret}:username::`,
    },
    {
      name: "DB_PASSWORD",
      valueFrom: `${rdsSecret}:password::`,
    },
    {
      name: "DB_NAME",
      valueFrom: `${rdsSecret}:dbname::`,
    },
    {
      name: "INDEXER_ETHEREUM_RPC_URL",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_ETHEREUM_RPC_URL::`,
    },
    {
      name: "INDEXER_OPTIMISM_RPC_URL",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_OPTIMISM_RPC_URL::`,
    },
    {
      name: "INDEXER_ETHEREUM_ENABLED",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_ETHEREUM_ENABLED::`,
    },
    {
      name: "INDEXER_OPTIMISM_ENABLED",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_OPTIMISM_ENABLED::`,
    },
    {
      name: "INDEXER_ETHEREUM_START_BLOCK",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_ETHEREUM_START_BLOCK::`,
    },
    {
      name: "INDEXER_OPTIMISM_START_BLOCK",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_OPTIMISM_START_BLOCK::`,
    },
    {
      name: "INDEXER_LEGACY_ENABLED",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:INDEXER_LEGACY_ENABLED::`,
    },
    {
      name: "STAKING_CONTRACT_ADDRESS_ETH_MAINNET",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:STAKING_CONTRACT_ADDRESS_ETH_MAINNET::`,
    },
    {
      name: "STAKING_CONTRACT_ADDRESS_OP_MAINNET",
      valueFrom: `${SCORER_SERVER_SSM_ARN}:STAKING_CONTRACT_ADDRESS_OP_MAINNET::`,
    },
  ]);

  const indexerEnvironment: { name: string; value: Input<string> }[] = [
    {
      name: "DB_HOST",
      value: rdsConnectionConfig.dbHost,
    },
    {
      name: "DB_PORT",
      value: rdsConnectionConfig.dbPort,
    },
  ];

  new awsx.ecs.FargateService("scorer-staking-indexer", {
    propagateTags: "TASK_DEFINITION",
    cluster: cluster.arn,
    desiredCount: 1,
    networkConfiguration: {
      subnets: privateSubnetIds,
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
          cpu: 512,
          image: dockerGtcStakingIndexerImage,
          // command: ["cargo", "run"],
          portMappings: [],
          secrets: indexerSecrets,
          environment: indexerEnvironment,
          dependsOn: [],
          links: [],
        },
      },
      tags: { name: "scorer-staking-indexer" },
    },
    tags: {
      name: "scorer-staking-indexer",
    },
  });

  const indexerErrorsMetric = new aws.cloudwatch.LogMetricFilter(
    "indexerErrorsMetric",
    {
      logGroupName: indexerLogGroup.name,
      metricTransformation: {
        defaultValue: "0",
        name: "indexerError",
        namespace: "/scorer/indexer",
        unit: "Count",
        value: "1",
      },
      name: "Indexer Errors",
      pattern: '"Error - Failed"',
    }
  );

  const indexerErrorsAlarm = new aws.cloudwatch.MetricAlarm(
    "indexerErrorsAlarm",
    {
      alarmActions: [alertTopic.arn],
      comparisonOperator: "GreaterThanOrEqualToThreshold",
      datapointsToAlarm: 1,
      evaluationPeriods: 1,
      insufficientDataActions: [],
      metricName: "indexerError",
      name: "Indexer Errors",
      namespace: "/scorer/indexer",
      okActions: [],
      period: 3600,
      statistic: "Sum",
      threshold: 1,
      treatMissingData: "notBreaching",
      tags: { name: "indexerErrorsAlarm" },
    }
  );
}

export const createSharedLambdaResources = ({
  rescoreQueue,
}: {
  rescoreQueue: aws.sqs.Queue;
}) => {
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

  const lambdaSecretsManagerPolicy = new aws.iam.Policy(
    "lambdaSecretManagerPolicy",
    {
      path: "/",
      description: "IAM policy for interfacing with SecretManager network",
      policy: lambdaSecretsManagerPolicyDocument.then(
        (lambdaSecretsManagerPolicyDocument) =>
          lambdaSecretsManagerPolicyDocument.json
      ),
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

  const httpLambdaRole = new aws.iam.Role("lambdaRole", {
    assumeRolePolicy: assumeRole.then((assumeRole) => assumeRole.json),
  });

  const lambdaLogRoleAttachment = new aws.iam.RolePolicyAttachment(
    "lambdaLogRoleAttachment",
    {
      role: httpLambdaRole.name,
      policyArn: lambdaLoggingPolicy.arn,
    }
  );

  const lambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment(
    "lambdaEc2RoleAttachment",
    {
      role: httpLambdaRole.name,
      policyArn: lambdaEc2Policy.arn,
    }
  );

  const lambdaSecretsManagerRoleAttachment = new aws.iam.RolePolicyAttachment(
    "lambdaSecretManagerRoleAttachment",
    {
      role: httpLambdaRole.name,
      policyArn: lambdaSecretsManagerPolicy.arn,
    }
  );

  const queueLambdaRole = new aws.iam.Role("queueLambdaRole", {
    assumeRolePolicy: assumeRole.then((assumeRole) => assumeRole.json),
  });

  const readSqsPolicyDocument = rescoreQueue.arn.apply((rescoreQueueArn) =>
    aws.iam.getPolicyDocument({
      statements: [
        {
          effect: "Allow",
          actions: [
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:ChangeMessageVisibility",
          ],
          resources: [rescoreQueueArn],
        },
      ],
    })
  );

  const readSqsPolicy = new aws.iam.Policy("readSqsPolicy", {
    path: "/",
    description: "IAM policy for reading from SQS",
    policy: readSqsPolicyDocument.apply(
      (readSqsPolicyDocument) => readSqsPolicyDocument.json
    ),
  });

  const queueLambdaSqsRoleAttachment = new aws.iam.RolePolicyAttachment(
    "queueLambdaSqsRoleAttachment",
    {
      role: queueLambdaRole.name,
      policyArn: readSqsPolicy.arn,
    }
  );

  const queueLambdaLogRoleAttachment = new aws.iam.RolePolicyAttachment(
    "queueLambdaLogRoleAttachment",
    {
      role: queueLambdaRole.name,
      policyArn: lambdaLoggingPolicy.arn,
    }
  );

  const queueLambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment(
    "queueLambdaEc2RoleAttachment",
    {
      role: queueLambdaRole.name,
      policyArn: lambdaEc2Policy.arn,
    }
  );

  const queueLambdaSecretsManagerRoleAttachment =
    new aws.iam.RolePolicyAttachment("queueLambdaSecretManagerRoleAttachment", {
      role: queueLambdaRole.name,
      policyArn: lambdaSecretsManagerPolicy.arn,
    });

  return {
    httpLambdaRole,
    httpRoleAttachments: [
      lambdaLogRoleAttachment,
      lambdaEc2RoleAttachment,
      lambdaSecretsManagerRoleAttachment,
    ],
    queueLambdaRole,
    queueRoleAttachments: [
      queueLambdaLogRoleAttachment,
      queueLambdaSqsRoleAttachment,
      queueLambdaSecretsManagerRoleAttachment,
      queueLambdaEc2RoleAttachment,
    ],
  };
};

type BuildLambdaFnBaseParams = {
  name: string;
  imageUri: string;
  privateSubnetSecurityGroup: SecurityGroup;
  vpcPrivateSubnetIds: Output<any>;
  environment: { name: string; value: Input<string> }[];
  role: Role;
  roleAttachments: RolePolicyAttachment[];
  memorySize: number;
  dockerCmd: string[];
  alertTopic?: Topic;
  alb: aws.lb.LoadBalancer;
};

export function buildHttpLambdaFn(
  args: BuildLambdaFnBaseParams & {
    httpsListener: Output<Listener>;
    listenerPriority: number;
    pathPatterns: string[];
    httpRequestMethods?: string[];
  },
  loadBalancerAlarmThresholds: LoadBalancerAlarmThresholds
) {
  const lambdaFunction = buildLambdaFn(args);

  const {
    httpsListener,
    listenerPriority,
    pathPatterns,
    httpRequestMethods,
    name,
    alertTopic,
    alb,
  } = args;

  const lambdaTargetGroup = new aws.lb.TargetGroup(`l-${name}`, {
    name: `l-${name}`,
    targetType: "lambda",
  });

  const withLb = new aws.lambda.Permission(`withLb-${name}`, {
    action: "lambda:InvokeFunction",
    function: lambdaFunction.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: lambdaTargetGroup.arn,
  });

  const lambdaTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    `lambdaTargetGroupAttachment-${name}`,
    {
      targetGroupArn: lambdaTargetGroup.arn,
      targetId: lambdaFunction.arn,
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

  if (alertTopic) {
    // We want alarm to monitor:
    // - 5xx errors in individual targets
    // - 4xx errors in individual targets
    // - 5xx errors in elb
    // - 4xx errors in elb
    // - target response time

    const metricNamespace = "AWS/ApplicationELB";
    /*
     * Alarm for monitoring target 5XX errors
     */
    const http5xxTargetAlarm = new aws.cloudwatch.MetricAlarm(
      `HTTP-Target-5XX-${name}`,
      {
        tags: { name: `HTTP-Target-5XX-${name}` },
        name: `HTTP-Target-5XX-${name}`,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        evaluationPeriods: 5,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCountPerTarget",
              dimensions: {
                LoadBalancer: alb.name,
                TargetGroup: lambdaTargetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_5XX_Count",
              dimensions: {
                LoadBalancer: alb.name,
                TargetGroup: lambdaTargetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 5XX errors",
            returnData: true,
          },
        ],
        threshold: loadBalancerAlarmThresholds.percentHTTPCodeTarget5XX,
      }
    );

    /*
     * Alarm for monitoring target 4XX errors
     */
    const http4xxTargetAlarm = new aws.cloudwatch.MetricAlarm(
      `HTTP-Target-4XX-${name}`,
      {
        tags: { name: `HTTP-Target-4XX-${name}` },
        name: `HTTP-Target-4XX-${name}`,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        evaluationPeriods: 5,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCountPerTarget",
              dimensions: {
                LoadBalancer: alb.name,
                TargetGroup: lambdaTargetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_4XX_Count",
              dimensions: {
                LoadBalancer: alb.name,
                TargetGroup: lambdaTargetGroup.name,
              },
              namespace: metricNamespace,
              period: 60,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 4XX errors",
            returnData: true,
          },
        ],
        threshold: loadBalancerAlarmThresholds.percentHTTPCodeTarget4XX,
      }
    );

    // We want an alarm to monitor for the average response time
    const targetResponseTimeAlarm = new aws.cloudwatch.MetricAlarm(
      `TargetResponseTime-${name}`,
      {
        tags: { name: `TargetResponseTime-${name}` },
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 3,
        dimensions: {
          LoadBalancer: alb.name,
          TargetGroup: lambdaTargetGroup.name,
        },
        evaluationPeriods: 5,
        metricName: "TargetResponseTime",
        name: `TargetResponseTime-${name}`,
        namespace: metricNamespace,
        period: 60,
        statistic: "Average",
        treatMissingData: "notBreaching",
        threshold: loadBalancerAlarmThresholds.targetResponseTime,
        unit: "Seconds",
      }
    );
  }
}

export function buildQueueLambdaFn(
  args: BuildLambdaFnBaseParams & {
    queue: aws.sqs.Queue;
  }
) {
  const lambdaFunction = buildLambdaFn(args);

  const { queue, name } = args;

  const queueLambdaTrigger = new aws.lambda.EventSourceMapping(
    `queueLambdaTrigger-${name}`,
    {
      batchSize: 10,
      eventSourceArn: queue.arn,
      functionName: lambdaFunction.arn,
    }
  );
}

function buildLambdaFn({
  name,
  imageUri,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  environment,
  role,
  roleAttachments,
  memorySize,
  dockerCmd,
}: BuildLambdaFnBaseParams): aws.lambda.Function {
  const lambdaFunction = new aws.lambda.Function(
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
      role: role.arn,
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
      dependsOn: roleAttachments,
    }
  );

  return lambdaFunction;
}

export const createDeadLetterQueue = ({
  alertTopic,
}: {
  alertTopic?: Topic;
}): aws.sqs.Queue => {
  const deadLetterQueue = new aws.sqs.Queue("scorer-dead-letter-queue");

  if (alertTopic) {
    const newMessageDeadLetterQueueAlarm = new aws.cloudwatch.MetricAlarm(
      "newMessageDeadLetterQueueAlarm",
      {
        alarmActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 1,
        evaluationPeriods: 1,
        metricQueries: [
          {
            id: "m1",
            metric: {
              dimensions: {
                QueueName: deadLetterQueue.name,
              },
              metricName: "ApproximateNumberOfMessagesVisible",
              namespace: "AWS/SQS",
              period: 300,
              stat: "Maximum",
            },
          },
          {
            id: "m10",
            metric: {
              dimensions: {
                QueueName: deadLetterQueue.name,
              },
              metricName: "ApproximateNumberOfMessagesVisible",
              namespace: "AWS/SQS",
              period: 300,
              stat: "Minimum",
            },
          },
          {
            expression: "m1 - m10",
            id: "e1",
            label: "NumNewMessagesDeadLetterQueue",
            returnData: true,
          },
        ],
        name: "NewMessageDeadLetterQueueAlarm",
        treatMissingData: "notBreaching",
      }
    );
  }

  return deadLetterQueue;
};

export const createRescoreQueue = ({
  deadLetterQueue,
}: {
  deadLetterQueue: aws.sqs.Queue;
}): aws.sqs.Queue => {
  const fourHoursInSeconds = 60 * 60 * 4;

  return new aws.sqs.Queue("rescore-queue", {
    delaySeconds: 0,
    maxMessageSize: 2048,
    messageRetentionSeconds: 86400,
    receiveWaitTimeSeconds: 10,
    visibilityTimeoutSeconds: fourHoursInSeconds,
    redrivePolicy: deadLetterQueue.arn.apply((arn) =>
      JSON.stringify({
        deadLetterTargetArn: arn,
        maxReceiveCount: 4,
      })
    ),
  });
};
