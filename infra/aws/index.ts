import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as cloudflare from "@pulumi/cloudflare";

import {
  ScorerService,
  buildHttpLambdaFn,
  createIndexerService,
  createScorerECSService,
  createTargetGroup,
  createSharedLambdaResources,
  createDeadLetterQueue,
  createRescoreQueue,
  buildQueueLambdaFn,
} from "../lib/scorer/new_service";
import { createLambdaFunction, createLambdaTargetGroup } from "../lib/scorer/routing-utils";
import { configureAllRouting } from "../lib/scorer/routing-rules";
import {
  AlarmConfigurations,
  createLoadBalancerAlarms,
  TargetGroupAlarmsConfiguration,
} from "../lib/scorer/loadBalancer";
import { createScheduledTask, createTask } from "../lib/scorer/scheduledTasks";
import { secretsManager } from "infra-libs";

import * as op from "@1password/op-js";
import { createVerifierService } from "./verifier";
import { createS3InitiatedECSTask } from "../lib/scorer/s3_initiated_ecs_task";
import { stack, defaultTags, StackType } from "../lib/tags";
import { createV2Api } from "./v2/index";
import { createEmbedLambdaFunctions } from "./embed";
import { createAppApiLambdaFunctions } from "./app_api";
import { createPythonLambdaLayer } from "./layer";
import { createMonitoringLambdaFunction } from "./system_tests";

//////////////////////////////////////////////////////////////
// Loading environment variables
//////////////////////////////////////////////////////////////

export const region = aws.getRegion();

const PROVISION_STAGING_FOR_LOADTEST = `${process.env["PROVISION_STAGING_FOR_LOADTEST"]}`.toLowerCase() === "true";
export const DOCKER_IMAGE_TAG = `${process.env.DOCKER_IMAGE_TAG || ""}`;

const route53Zone = op.read.parse(`op://DevOps/passport-scorer-${stack}-env/ci/ROUTE_53_ZONE`);

const legacyRootDomain = op.read.parse(`op://DevOps/passport-scorer-${stack}-env/ci/ROOT_DOMAIN`);

const legacyDomain =
  stack == "production" ? `api.scorer.${legacyRootDomain}` : `api.${stack}.scorer.${legacyRootDomain}`;

const current = aws.getCallerIdentity({});
const regionData = aws.getRegion({});

export const dockerGtcPassportScorerImage = pulumi
  .all([current, regionData])
  .apply(([acc, region]) => `${acc.accountId}.dkr.ecr.${region.id}.amazonaws.com/passport-scorer:${DOCKER_IMAGE_TAG}`);

export const dockerGtcSubmitPassportLambdaImage = pulumi
  .all([current, regionData])
  .apply(
    ([acc, region]) => `${acc.accountId}.dkr.ecr.${region.id}.amazonaws.com/submit-passport-lambdas:${DOCKER_IMAGE_TAG}`
  );

export const dockerGtcStakingIndexerImage = pulumi
  .all([current, regionData])
  .apply(([acc, region]) => `${acc.accountId}.dkr.ecr.${region.id}.amazonaws.com/passport-indexer:${DOCKER_IMAGE_TAG}`);

export const verifierDockerImage = pulumi
  .all([current, regionData])
  .apply(
    ([acc, region]) => `${acc.accountId}.dkr.ecr.${region.id}.amazonaws.com/passport-verifier:${DOCKER_IMAGE_TAG}`
  );

// Rust scorer Lambda zip archive
import * as fs from "fs";
const rustScorerZipPath = "../../rust-scorer-artifact/bootstrap.zip";
const rustScorerZipArchive = fs.existsSync(rustScorerZipPath)
  ? new pulumi.asset.FileArchive(rustScorerZipPath)
  : undefined;

const pagerDutyIntegrationEndpoint = op.read.parse(
  `op://DevOps/passport-scorer-${stack}-env/ci/PAGERDUTY_INTEGRATION_ENDPOINT`
);

const coreInfraStack = new pulumi.StackReference(`passportxyz/core-infra/${stack}`);

const privateAlbHttpListenerArn = coreInfraStack.getOutput("privateAlbHttpListenerArn");
const privatprivateAlbArnSuffixeAlbHttpListenerArn = coreInfraStack.getOutput("privateAlbArnSuffix");

const RDS_SECRET_ARN = coreInfraStack.getOutput("rdsSecretArn");

const vpcID = coreInfraStack.getOutput("vpcId");
const vpcPrivateSubnetIds = coreInfraStack.getOutput("privateSubnetIds");
const vpcPublicSubnetIds = coreInfraStack.getOutput("publicSubnetIds");

const passportXyzDomainName = coreInfraStack.getOutput("passportXyzEnvDomainName");
const passportXyzHostedZoneId = coreInfraStack.getOutput("envPassportXyzZoneId");
const passportXyzCertificateArn = coreInfraStack.getOutput("envPassportXyzCertificateArn");

const noStackPassportXyzCertificateArn = coreInfraStack.getOutput("passportXyzCertificateArn");

const codeBucketId = coreInfraStack.getOutput("codeBucketId");

const passportAdminBucketName = coreInfraStack.getOutput("passportAdminBucketName");
const passportAdminBucketId = coreInfraStack.getOutput("passportAdminBucketId");

const vpcPublicSubnetId1 = vpcPublicSubnetIds.apply((values) => values[0]);

const vpcPublicSubnetId2 = vpcPublicSubnetIds.apply((values) => values[1]);

const redisCacheOpsConnectionUrl = coreInfraStack.getOutput("redisConnectionUrl");

const coreRdsSecretArn = coreInfraStack.getOutput("coreRdsSecretArn");
const coreVpcId = coreInfraStack.getOutput("vpcId");
const corePrivateSubnetIds = coreInfraStack.getOutput("privateSubnetIds");
const rdsSecretArn = coreInfraStack.getOutput("rdsSecretArn");

const albDnsName = coreInfraStack.getOutput("coreAlbDns");
const albHostedZoneId = coreInfraStack.getOutput("coreAlbZoneId");

const alarm5xx = {
  burst: {
    threshold: 0.2,
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    period: 60,
  },
  sustain: {
    threshold: 0.01,
    datapointsToAlarm: 3,
    evaluationPeriods: 4,
    period: 600,
  },
};

const alarm4xx = {
  burst: {
    threshold: 0.85,
    datapointsToAlarm: 4,
    evaluationPeriods: 5,
    period: 60,
  },
  sustain: {
    threshold: 0.5,
    datapointsToAlarm: 3,
    evaluationPeriods: 4,
    period: 600,
  },
};

const alarmResponseTime = {
  burst: {
    threshold: 20,
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    period: 60,
  },
  sustain: {
    threshold: 2,
    datapointsToAlarm: 30,
    evaluationPeriods: 40,
    period: 60,
  },
};

const defaultTargetAlarmConfiguration: TargetGroupAlarmsConfiguration = {
  percentHTTPCodeTarget5XX: alarm5xx,
  percentHTTPCodeTarget4XX: alarm4xx,
  targetResponseTime: alarmResponseTime,
};

const alarmConfigurations: AlarmConfigurations = {
  percentHTTPCodeELB4XX: {
    ...alarm4xx,
    burst: {
      threshold: 0.95,
      datapointsToAlarm: 3,
      evaluationPeriods: 5,
      period: 300,
    },
  },
  percentHTTPCodeELB5XX: alarm5xx,
  indexerErrorThreshold: 2, // threshold for indexer logged errors
  indexerErrorPeriod: 1800, // period for indexer logged errors, set to 30 min for now

  default: defaultTargetAlarmConfiguration,
  "passport-analysis-GET-0": {
    ...defaultTargetAlarmConfiguration,
    targetResponseTime: {
      burst: {
        ...alarmResponseTime.burst,
        threshold: 50,
        datapointsToAlarm: 8,
        evaluationPeriods: 10,
      },
      sustain: {
        ...alarmResponseTime.sustain,
        threshold: 30,
      },
    },
  },
  "cc-v1-score-POST-0": {
    ...defaultTargetAlarmConfiguration,
  },
  "cc-v1-st-bulk-PATCH-0": {
    ...defaultTargetAlarmConfiguration,
    targetResponseTime: {
      ...alarmResponseTime,
      burst: {
        ...alarmResponseTime.burst,
        datapointsToAlarm: 10,
        evaluationPeriods: 15,
      },
    },
  },
  "submit-passport-0": {
    ...defaultTargetAlarmConfiguration,
    targetResponseTime: {
      ...alarmResponseTime,
      burst: {
        ...alarmResponseTime.burst,
        datapointsToAlarm: 10,
        evaluationPeriods: 15,
      },
    },
  },
  "cc-v1-st-bulk-DELETE-0": {
    ...defaultTargetAlarmConfiguration,
    targetResponseTime: {
      ...alarmResponseTime,
      burst: {
        ...alarmResponseTime.burst,
        datapointsToAlarm: 7,
        evaluationPeriods: 10,
      },
    },
  },
  "passport-v2-stamp-score": {
    ...defaultTargetAlarmConfiguration,
    targetResponseTime: {
      sustain: {
        threshold: 4,
        datapointsToAlarm: 30,
        evaluationPeriods: 40,
        period: 60,
      },
      burst: {
        ...alarmResponseTime.burst,
        datapointsToAlarm: 7,
        evaluationPeriods: 10,
      },
    },
  },
  "passport-v2-model-score": {
    ...defaultTargetAlarmConfiguration,
    targetResponseTime: {
      ...alarmResponseTime,
      burst: {
        ...alarmResponseTime.burst,
        datapointsToAlarm: 7,
        evaluationPeriods: 10,
      },
    },
  },
};

type EcsTaskConfigurationType = {
  memory: number;
  cpu: number;
  desiredCount?: number;
};

type EcsServiceNameType =
  | "scorer-api-default-1"
  | "scorer-api-reg-1"
  | "scorer-api-internal-1"
  | "frequent-eth-model-v2-dump-grants";
const ecsTaskConfigurations: Record<EcsServiceNameType, Record<StackType, EcsTaskConfigurationType>> = {
  "scorer-api-default-1": {
    review: {
      memory: 1024,
      cpu: 512,
      desiredCount: 1,
    },
    staging: {
      memory: 1024,
      cpu: 512,
      desiredCount: 1,
    },
    production: {
      memory: 2048,
      cpu: 512,
      desiredCount: 2,
    },
  },
  "scorer-api-reg-1": {
    review: {
      memory: 1024,
      cpu: 512,
      desiredCount: 1,
    },
    staging: {
      memory: 1024,
      cpu: 512,
      desiredCount: 1,
    },
    production: {
      memory: 4096,
      cpu: 2048,
      desiredCount: 2,
    },
  },
  "scorer-api-internal-1": {
    review: {
      memory: 1024,
      cpu: 512,
      desiredCount: 1,
    },
    staging: {
      memory: 1024,
      cpu: 512,
      desiredCount: 1,
    },
    production: {
      memory: 2048,
      cpu: 512,
      desiredCount: 2,
    },
  },
  "frequent-eth-model-v2-dump-grants": {
    review: {
      memory: 1024,
      cpu: 256,
      desiredCount: 1,
    },
    staging: {
      memory: 1024,
      cpu: 256,
      desiredCount: 1,
    },
    production: {
      memory: 4096,
      cpu: 512,
      desiredCount: 2,
    },
  },
};

if (PROVISION_STAGING_FOR_LOADTEST) {
  // If we are provisioning for staging we want to have the same sizing as for production
  // So we copy over the production values to the staging values in ecsTaskConfigurations
  ecsTaskConfigurations["scorer-api-default-1"]["staging"] =
    ecsTaskConfigurations["scorer-api-default-1"]["production"];
  ecsTaskConfigurations["scorer-api-reg-1"]["staging"] = ecsTaskConfigurations["scorer-api-reg-1"]["production"];
  ecsTaskConfigurations["scorer-api-internal-1"]["staging"] =
    ecsTaskConfigurations["scorer-api-internal-1"]["production"];
}

// This matches the default security group that awsx previously created when creating the Cluster.
// https://github.com/pulumi/pulumi-awsx/blob/45136c540f29eb3dc6efa5b4f51cfe05ee75c7d8/awsx-classic/ecs/cluster.ts#L110
const privateSubnetSecurityGroup = new aws.ec2.SecurityGroup("private-subnet-secgrp", {
  description: "Security Group for Web Services",
  vpcId: vpcID,
  ingress: [
    {
      protocol: "TCP",
      fromPort: 22,
      toPort: 22,
      cidrBlocks: ["0.0.0.0/0"],
      description: "allow ssh in from any ipv4 address",
    },
    {
      protocol: "TCP",
      fromPort: 0,
      toPort: 65535,
      cidrBlocks: ["0.0.0.0/0"],
      description: "allow incoming tcp on any port from any ipv4 address",
    },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
      description: "allow output to any ipv4 address using any protocol",
    },
  ],
  tags: {
    ...defaultTags,
    Name: "private-subnet-secgrp",
  },
});

const scorerDbProxyEndpoint = coreInfraStack.getOutput("rdsProxyEndpoint");
const scorerDbProxyEndpointConn = coreInfraStack.getOutput("rdsProxyConnectionUrl");
const readreplica0ConnectionUrl = coreInfraStack.getOutput("readreplica0ConnectionUrl");
const readreplicaAnalyticsConnectionUrl = coreInfraStack.getOutput("readreplicaAnalyticsConnectionUrl");

//////////////////////////////////////////////////////////////
// Set up ALB and ECS cluster
//////////////////////////////////////////////////////////////

const cluster = new aws.ecs.Cluster("scorer", {
  settings: [{ name: "containerInsights", value: "enabled" }],
  tags: {
    ...defaultTags,
    Name: "scorer",
  },
});

export const clusterId = cluster.id;

// Create bucket for access logs
const accessLogsBucket = new aws.s3.Bucket(`gitcoin-scorer-access-logs`, {
  acl: "private",
  forceDestroy: stack == "production" ? false : true,
  tags: {
    ...defaultTags,
    Name: "gitcoin-scorer-access-logs",
  },
});

// Add lifecycle rule to delete objects after 14 days
new aws.s3.BucketLifecycleConfigurationV2(
  `gitcoin-scorer-access-logs`,
  {
    bucket: accessLogsBucket.id,
    rules: [
      {
        id: "expire-logs-after-14-days",
        status: "Enabled",
        expiration: {
          days: 14,
        },
      },
    ],
  },
  {
    dependsOn: [accessLogsBucket],
  }
);

const serviceAccount = aws.elb.getServiceAccount({});

const accessLogsBucketPolicyDocument = aws.iam.getPolicyDocumentOutput({
  statements: serviceAccount.then((serviceAccount) => [
    {
      effect: "Allow",
      principals: [
        {
          type: "AWS",
          identifiers: [pulumi.interpolate`${serviceAccount.arn}`],
        },
      ],
      actions: ["s3:PutObject"],
      resources: [pulumi.interpolate`arn:aws:s3:::${accessLogsBucket.id}/AWSLogs/*`],
    },
    {
      effect: "Allow",
      principals: [
        {
          type: "Service",
          identifiers: ["logdelivery.elb.amazonaws.com"],
        },
      ],
      actions: ["s3:GetBucketAcl"],
      resources: [pulumi.interpolate`arn:aws:s3:::${accessLogsBucket.id}`],
    },
  ]),
});

const accessLogsBucketPolicy = new aws.s3.BucketPolicy(`gitcoin-accessLogs-policy`, {
  bucket: accessLogsBucket.id,
  policy: accessLogsBucketPolicyDocument.apply((accessLogsBucketPolicyDocument) => accessLogsBucketPolicyDocument.json),
});

const albSecGrp = new aws.ec2.SecurityGroup(`scorer-service-alb`, {
  description: "scorer-service-alb",
  vpcId: vpcID,
  ingress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
  egress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
  tags: {
    ...defaultTags,
    Name: "scorer-service-alb",
  },
});

// Creates an ALB associated with our custom VPC.
const alb = new aws.alb.LoadBalancer(`scorer-service`, {
  loadBalancerType: "application",
  internal: false,
  securityGroups: [albSecGrp.id],
  subnets: vpcPublicSubnetIds,
  idleTimeout: 90,
  accessLogs: {
    bucket: accessLogsBucket.bucket,
    enabled: true,
  },
  tags: {
    ...defaultTags,
    Name: "scorer-service",
  },
});
export const scorerALbArn = alb.arn;
// Listen to HTTP traffic on port 80 and redirect to 443
const httpListener = new aws.alb.Listener("scorer-http-listener", {
  loadBalancerArn: alb.arn,
  port: 80,
  protocol: "HTTP",
  defaultActions: [
    {
      type: "redirect",
      redirect: {
        protocol: "HTTPS",
        port: "443",
        statusCode: "HTTP_301",
      },
    },
  ],
  tags: {
    ...defaultTags,
    Name: "scorer-http-listener",
  },
});

//////////////////////////////////////////////////////////////
// Set up the target groups
//////////////////////////////////////////////////////////////

// Target group with the port of the Docker image
const targetGroupDefault = createTargetGroup("scorer-api-default", vpcID);
const targetGroupRegistry = createTargetGroup("scorer-api-reg", vpcID);
const targetGroupInternal = createTargetGroup("scorer-api-internal", vpcID);

//////////////////////////////////////////////////////////////
// Create the HTTPS listener, and set the default target group
//////////////////////////////////////////////////////////////
const httpsAlbCertArn = coreInfraStack.getOutput("gitcoinScorerApiCertificateArn");
const httpsListener = httpsAlbCertArn.apply(
  (certificate) =>
    new aws.alb.Listener("scorer-https-listener", {
      loadBalancerArn: alb.arn,
      protocol: "HTTPS",
      port: 443,
      certificateArn: certificate,
      defaultActions: [
        {
          type: "forward",
          targetGroupArn: targetGroupDefault.arn,
        },
      ],
      tags: {
        ...defaultTags,
        Name: "scorer-https-listener",
      },
    })
);

// Create a DNS record for the load balancer
const www = new aws.route53.Record("scorer", {
  zoneId: route53Zone,
  name: legacyDomain,
  type: "A",
  aliases: [
    {
      name: alb.dnsName,
      zoneId: alb.zoneId,
      evaluateTargetHealth: true,
    },
  ],
});

const scorerSecret = new aws.secretsmanager.Secret("scorer-secret", {
  name: "scorer-secret",
  description: "Scorer Secrets",
  tags: {
    ...defaultTags,
    Name: "scorer-secret",
  },
});

const indexerSecret = new aws.secretsmanager.Secret("indexer-secret", {
  name: "indexer-secret",
  description: "Secrets for passport-scorer indexer",
  tags: {
    ...defaultTags,
    Name: "indexer-secret",
  },
});

const dpoppEcsRole = new aws.iam.Role("dpoppEcsRole", {
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Sid: "",
        Principal: {
          Service: "ecs-tasks.amazonaws.com",
        },
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "allow_exec",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Action: [
              "ssmmessages:CreateControlChannel",
              "ssmmessages:CreateDataChannel",
              "ssmmessages:OpenControlChannel",
              "ssmmessages:OpenDataChannel",
            ],
            Resource: "*",
          },
        ],
      }),
    },
    {
      name: "allow_iam_secrets_access",
      policy: pulumi.jsonStringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: [scorerSecret.arn, indexerSecret.arn],
          },
        ],
      }),
    },
  ],
  managedPolicyArns: ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"],
  tags: {
    ...defaultTags,
    Name: "dpoppEcsRole",
  },
});

const pagerdutyTopic = new aws.sns.Topic("pagerduty", {
  name: "ScorerPagerduty",
  tracingConfig: "PassThrough",
  tags: {
    ...defaultTags,
    Name: "ScorerPagerduty",
  },
});

const PAGERDUTY_INTEGRATION_ENDPOINT = pulumi.secret(pagerDutyIntegrationEndpoint);

const identity = aws.getCallerIdentity();

const pagerdutyTopicPolicy = new aws.sns.TopicPolicy("pagerdutyTopicPolicy", {
  arn: pagerdutyTopic.arn,
  policy: pagerdutyTopic.arn.apply((arn) =>
    identity.then(({ accountId }) =>
      JSON.stringify({
        Id: "__default_policy_ID",
        Statement: [
          {
            Action: [
              "SNS:GetTopicAttributes",
              "SNS:SetTopicAttributes",
              "SNS:AddPermission",
              "SNS:RemovePermission",
              "SNS:DeleteTopic",
              "SNS:Subscribe",
              "SNS:ListSubscriptionsByTopic",
              "SNS:Publish",
            ],
            Condition: {
              StringEquals: { "AWS:SourceOwner": accountId },
            },
            Effect: "Allow",
            Principal: { AWS: "*" },
            Resource: arn,
            Sid: "__default_statement_ID",
          },
        ],
        Version: "2008-10-17",
      })
    )
  ),
});

const pagerdutySubscription =
  stack == "production"
    ? new aws.sns.TopicSubscription("pagerdutySubscription", {
        endpoint: PAGERDUTY_INTEGRATION_ENDPOINT,
        protocol: "https",
        topic: pagerdutyTopic.arn,
      })
    : null;

const deadLetterQueue = createDeadLetterQueue({ alertTopic: pagerdutyTopic });

const rescoreQueue = createRescoreQueue({ deadLetterQueue });

const serviceTaskRole = new aws.iam.Role("scorer-service-task-role", {
  name: "scorer-service-task-role",
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Sid: "",
        Principal: {
          Service: "ecs-tasks.amazonaws.com",
        },
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "ecs_task_role",
      policy: rescoreQueue.arn.apply((rescoreQueueArn) =>
        JSON.stringify({
          Version: "2012-10-17",
          Statement: [
            // SQS permissions
            {
              Effect: "Allow",
              Action: ["sqs:SendMessage"],
              Resource: rescoreQueueArn,
            },
            // S3 permissions
            {
              Effect: "Allow",
              Action: ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:ListObjects"],
              Resource: "*",
            },
            // CloudFront
            {
              Effect: "Allow",
              Action: ["cloudfront:CreateInvalidation"],
              Resource: "*",
            },
          ],
        })
      ),
    },
  ],
  tags: {
    ...defaultTags,
    Name: "scorer-service-task-role",
  },
});

const apiEnvironment = [
  ...secretsManager.getEnvironmentVars({
    vault: "DevOps",
    repo: "passport-scorer",
    env: stack,
    section: "api",
  }),
  // TODO most of these (the static ones) could be moved to the password manager
  {
    name: "DEBUG",
    value: "off",
  },
  {
    name: "CSRF_TRUSTED_ORIGINS",
    value: passportXyzDomainName.apply((passportXyzDomainNameStr) =>
      JSON.stringify([`https://${legacyDomain}`, `https://${passportXyzDomainNameStr}`])
    ),
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
    value: "https://app.passport.xyz/",
  },
  {
    name: "RESCORE_QUEUE_URL",
    value: rescoreQueue.url,
  },
  {
    name: "ALLOWED_HOSTS",
    value: passportXyzDomainName.apply((passportXyzDomainNameStr) =>
      // TODO: geri: investigate if using '*' here is a security risk
      JSON.stringify([legacyDomain, passportXyzDomainNameStr, "*"])
    ),
  },
  {
    name: "VERIFIER_URL",
    value: "http://core-alb.private.gitcoin.co/verifier/verify",
  },
  {
    name: "AWS_STORAGE_BUCKET_NAME",
    value: passportAdminBucketName,
  },
].sort(secretsManager.sortByName);

const apiSecrets = secretsManager.syncSecretsAndGetRefs({
  vault: "DevOps",
  repo: "passport-scorer",
  env: stack,
  section: "api",
  targetSecret: scorerSecret,
  secretVersionName: "scorer-secret-version",
  extraSecretDefinitions: [
    {
      name: "DATABASE_URL",
      value: scorerDbProxyEndpointConn,
    },
    {
      name: "READ_REPLICA_0_URL",
      value: readreplica0ConnectionUrl || scorerDbProxyEndpointConn,
    },
    {
      name: "READ_REPLICA_ANALYTICS_URL",
      value: readreplicaAnalyticsConnectionUrl || scorerDbProxyEndpointConn,
    },
    { name: "CELERY_BROKER_URL", value: redisCacheOpsConnectionUrl },
  ],
});

const indexerEnvironment = [
  ...secretsManager.getEnvironmentVars({
    vault: "DevOps",
    repo: "passport-scorer",
    env: stack,
    section: "indexer",
  }),
  {
    name: "DB_HOST",
    value: scorerDbProxyEndpoint,
  },
  {
    name: "DB_PORT",
    value: String(5432),
  },
  {
    name: "CERT_FILE",
    value: "./ca-certificates/all.pem",
  },
].sort(secretsManager.sortByName);

const indexerSecrets = pulumi
  .all([
    secretsManager.syncSecretsAndGetRefs({
      vault: "DevOps",
      repo: "passport-scorer",
      env: stack,
      section: "indexer",
      targetSecret: indexerSecret,
      secretVersionName: "indexer-secret-version",
    }),
    RDS_SECRET_ARN,
  ])
  .apply(([secretRefs, rdsSecretArn]) =>
    [
      ...secretRefs,
      {
        name: "DB_USER",
        valueFrom: `${rdsSecretArn}:username::`,
      },
      {
        name: "DB_PASSWORD",
        valueFrom: `${rdsSecretArn}:password::`,
      },
      {
        name: "DB_NAME",
        valueFrom: `${rdsSecretArn}:dbname::`,
      },
    ].sort(secretsManager.sortByName)
  );

//////////////////////////////////////////////////////////////
// Set up log groups for API service and worker
//////////////////////////////////////////////////////////////
const serviceLogGroup = new aws.cloudwatch.LogGroup("scorer-service", {
  retentionInDays: stack === "production" ? 14 : 7,
  tags: {
    ...defaultTags,
    Name: `cloudwatch-loggroup-scorer-service`,
  },
});

//////////////////////////////////////////////////////////////
// Set up the Scorer ECS service
//////////////////////////////////////////////////////////////
const baseScorerServiceConfig: ScorerService = {
  cluster,
  alb,
  dockerImageScorer: dockerGtcPassportScorerImage,
  executionRole: dpoppEcsRole,
  taskRole: serviceTaskRole,
  logGroup: serviceLogGroup,
  subnets: vpcPrivateSubnetIds,
  securityGroup: privateSubnetSecurityGroup,
  httpListenerArn: httpsListener.arn,
  targetGroup: targetGroupDefault,
  autoScaleMaxCapacity: 20,
  autoScaleMinCapacity: stack == "production" ? 2 : 1,
  alertTopic: pagerdutyTopic,
};

const scorerServiceDefault = createScorerECSService({
  name: "scorer-api-default-1",
  config: {
    ...baseScorerServiceConfig,
    targetGroup: targetGroupDefault,
    memory: ecsTaskConfigurations["scorer-api-default-1"][stack].memory,
    cpu: ecsTaskConfigurations["scorer-api-default-1"][stack].cpu,
    desiredCount: ecsTaskConfigurations["scorer-api-default-1"][stack].desiredCount,
  },
  environment: apiEnvironment,
  secrets: apiSecrets,
  loadBalancerAlarmThresholds: alarmConfigurations,
});

const scorerServiceRegistry = createScorerECSService({
  name: "scorer-api-reg-1",
  config: {
    ...baseScorerServiceConfig,
    listenerRulePriority: 3000,
    httpListenerRulePaths: [
      {
        pathPattern: {
          values: ["/registry/*"],
        },
      },
    ],

    targetGroup: targetGroupRegistry,
    memory: ecsTaskConfigurations["scorer-api-reg-1"][stack].memory,
    cpu: ecsTaskConfigurations["scorer-api-reg-1"][stack].cpu,
    desiredCount: ecsTaskConfigurations["scorer-api-reg-1"][stack].desiredCount,
  },
  environment: apiEnvironment,
  secrets: apiSecrets,
  loadBalancerAlarmThresholds: alarmConfigurations,
});

const scorerServiceInternal = createScorerECSService({
  name: "scorer-api-internal-1",
  config: {
    ...baseScorerServiceConfig,
    listenerRulePriority: 2202,
    httpListenerArn: privateAlbHttpListenerArn,
    httpListenerRulePaths: [
      {
        pathPattern: {
          values: ["/internal/*"],
        },
      },
    ],
    targetGroup: targetGroupInternal,
    memory: ecsTaskConfigurations["scorer-api-internal-1"][stack].memory,
    cpu: ecsTaskConfigurations["scorer-api-internal-1"][stack].cpu,
    desiredCount: ecsTaskConfigurations["scorer-api-internal-1"][stack].desiredCount,
  },
  environment: apiEnvironment,
  secrets: apiSecrets,
  loadBalancerAlarmThresholds: alarmConfigurations,
});

//////////////////////////////////////////////////////////////
// Set up the worker role
//////////////////////////////////////////////////////////////
const workerRole = new aws.iam.Role("scorer-bkgrnd-worker-role", {
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Sid: "",
        Principal: {
          Service: "ecs-tasks.amazonaws.com",
        },
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "allow_exec",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Action: [
              "ssmmessages:CreateControlChannel",
              "ssmmessages:CreateDataChannel",
              "ssmmessages:OpenControlChannel",
              "ssmmessages:OpenDataChannel",
            ],
            Resource: "*",
          },
        ],
      }),
    },
    {
      name: "allow_iam_secrets_access",
      policy: pulumi.jsonStringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: [scorerSecret.arn, indexerSecret.arn, RDS_SECRET_ARN],
          },
        ],
      }),
    },
  ],
  managedPolicyArns: ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"],
  tags: {
    ...defaultTags,
    Name: "scorer-bkgrnd-worker-role",
  },
});

const secgrp = new aws.ec2.SecurityGroup(`scorer-run-migrations-task`, {
  description: "gitcoin-ecs-task",
  vpcId: vpcID,
  ingress: [
    { protocol: "tcp", fromPort: 22, toPort: 22, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
  tags: {
    ...defaultTags,
    Name: "gitcoin-ecs-task",
  },
});

export const securityGroupForTaskDefinition = secgrp.id;

// Apps: registry,ceramic_cache,account,scorer_weighted,trusta_labs,stake
// Split the data dump by app to avoid having 1 bad app causing the whole dump to fail

const dailyDataDumpApps: string[] = ["registry"];

// Used by the data team
export const dailyDataDumpTaskDefinitionParquetList = dailyDataDumpApps.map((app: string) => {
  const dailyDataDumpTaskDefinitionParquet = createScheduledTask({
    name: `daily-data-dump-parquet-${app}`,
    config: {
      ...baseScorerServiceConfig,
      cpu: 1024,
      memory: 2048,
      securityGroup: secgrp,
      ephemeralStorageSizeInGiB: 100,
      command: [
        "python",
        "manage.py",
        "scorer_dump_data_parquet",
        "--database=read_replica_analytics",
        `--apps=${app}`,
        "--s3-uri=s3://passport-scorer/daily_data_dumps/",
        "--batch-size=20000",
      ].join(" "),
      scheduleExpression: "cron(45 0 ? * * *)", // Run the task daily at 00:30 UTC
      alertTopic: pagerdutyTopic,
    },
    environment: apiEnvironment,
    secrets: apiSecrets,
    alarmPeriodSeconds: 86400, // 24h max period
    enableInvocationAlerts: false,
    scorerSecretManagerArn: scorerSecret.arn,
  });

  return dailyDataDumpTaskDefinitionParquet;
});

// Only for production
if (stack === "production") {
  /*
   * Exporting score data for OSO
   */
  // Used by OSO team : dumps the data in their AWS account
  const dailyScoreExportForOSO = createScheduledTask({
    name: "daily-score-export-for-oso",
    config: {
      ...baseScorerServiceConfig,
      securityGroup: secgrp,
      command: [
        "python",
        "manage.py",
        "scorer_dump_data_parquet_for_oso",
        "--s3-uri=s3://oso-dataset-transfer-bucket/passport/",
        "--filename=scores.parquet",
        "--database=read_replica_analytics",
      ].join(" "),
      scheduleExpression: "cron(30 0 ? * * *)", // Run the task daily at 00:30 UTC
      alertTopic: pagerdutyTopic,
    },
    environment: apiEnvironment,
    secrets: apiSecrets,
    alarmPeriodSeconds: 86400, // 24h max period
    enableInvocationAlerts: false,
    scorerSecretManagerArn: scorerSecret.arn,
  });
  // Used by the grants team
  // dumps the data in their Digital Ocean account
  const frequentAlloScorerDataDumpTaskDefinitionDigitalOcean = pulumi.all([apiSecrets]).apply(([_apiSecrets]) => {
    const digitalOceanS3Endpoint = op.read.parse(
      `op://DevOps/passport-scorer-${stack}-env/api/GRANTS_DIGITAL_OCEAN_S3_ENDPOINT`
    );
    const digitalOceanS3Bucket = op.read.parse(
      `op://DevOps/passport-scorer-${stack}-env/api/GRANTS_DIGITAL_OCEAN_S3_BUCKET`
    );
    return createScheduledTask({
      name: "frequent-allo-scorer-data-dump-grants",
      config: {
        ...baseScorerServiceConfig,
        securityGroup: secgrp,
        command: [
          "python",
          "manage.py",
          "scorer_dump_data",
          "--batch-size=1000",
          "--database=read_replica_analytics",
          "--config",
          "'" +
            JSON.stringify([
              {
                name: "registry.Score",
                filter: { passport__community_id: 335 },
                select_related: ["passport"],
                "extra-args": { ACL: "public-read" },
              },
            ]) +
            "'",
          `--s3-uri=s3://${digitalOceanS3Bucket}`,
          `--s3-endpoint=https://${digitalOceanS3Endpoint}`,
          `--s3-access-key=$GRANTS_DIGITAL_OCEAN_ACCESS_KEY`, // Those are defined in the secrets
          `--s3-secret-access-key=$GRANTS_DIGITAL_OCEAN_SECRET_ACCESS_KEY`, // Those are defined in the secrets
        ].join(" "),
        scheduleExpression: "cron(*/30 * ? * * *)", // Run the task every 30 min
        alertTopic: pagerdutyTopic,
      },
      environment: apiEnvironment,
      secrets: _apiSecrets,
      alarmPeriodSeconds: 3600, // 1h in seconds
      enableInvocationAlerts: true,
      scorerSecretManagerArn: scorerSecret.arn,
    });
  });

  const frequentEthModelV2ScoreDataDumpTaskDefinitionForScorerDigitalOcean = pulumi
    .all([apiSecrets])
    .apply(([_apiSecrets]) => {
      // const digitalOceanAccessKey =  _apiSecrets.find(secret => secret.name === "GRANTS_DIGITAL_OCEAN_ACCESS_KEY")?.valueFrom;
      // const digitalOceanSecretAccessKey =  _apiSecrets.find(secret => secret.name === "GRANTS_DIGITAL_OCEAN_SECRET_ACCESS_KEY")?.valueFrom;
      const digitalOceanS3Endpoint = op.read.parse(
        `op://DevOps/passport-scorer-${stack}-env/api/GRANTS_DIGITAL_OCEAN_S3_ENDPOINT`
      );
      const digitalOceanS3Bucket = op.read.parse(
        `op://DevOps/passport-scorer-${stack}-env/api/GRANTS_DIGITAL_OCEAN_S3_BUCKET`
      );
      return createScheduledTask({
        name: "frequent-eth-model-v2-dump-grants",
        config: {
          ...baseScorerServiceConfig,
          securityGroup: secgrp,
          command: [
            "python",
            "manage.py",
            "scorer_dump_data_model_score",
            `--s3-uri=s3://${digitalOceanS3Bucket}`,
            `--s3-endpoint=https://${digitalOceanS3Endpoint}`,
            `--s3-access-key=$GRANTS_DIGITAL_OCEAN_ACCESS_KEY`, // Those are defined in the secrets
            `--s3-secret-access-key=$GRANTS_DIGITAL_OCEAN_SECRET_ACCESS_KEY`, // Those are defined in the secrets
            "--filename=model_scores.parquet",
            "--format=parquet",
            "--s3-extra-args",
            "'" + JSON.stringify({ ACL: "public-read" }) + "'",
          ].join(" "),
          scheduleExpression: "cron(*/30 * ? * * *)", // Run the task every 30 min
          alertTopic: pagerdutyTopic,
          cpu: ecsTaskConfigurations["frequent-eth-model-v2-dump-grants"][stack].cpu,
          memory: ecsTaskConfigurations["frequent-eth-model-v2-dump-grants"][stack].memory,
        },
        environment: apiEnvironment,
        secrets: _apiSecrets,
        alarmPeriodSeconds: 3600, // 1h in seconds
        enableInvocationAlerts: true,
        scorerSecretManagerArn: scorerSecret.arn,
      });
    });
}

export const coinbaseRevocationCheck = createScheduledTask({
  name: "coinbase-revocation-check",
  config: {
    ...baseScorerServiceConfig,
    securityGroup: secgrp,
    command: ["python", "manage.py", "check_coinbase_revocations"].join(" "),
    scheduleExpression: "cron(0 */6 ? * * *)", // Run the task every 6 hours
    alertTopic: pagerdutyTopic,
  },
  environment: apiEnvironment,
  secrets: apiSecrets,
  alarmPeriodSeconds: 86400, // 24h max period
  enableInvocationAlerts: true,
  scorerSecretManagerArn: scorerSecret.arn,
});

createIndexerService(
  {
    cluster,
    workerRole,
    privateSubnetIds: vpcPrivateSubnetIds,
    privateSubnetSecurityGroup,
    alertTopic: pagerdutyTopic,
    secretReferences: indexerSecrets,
    environment: indexerEnvironment,
    indexerImage: dockerGtcStakingIndexerImage,
  },
  alarmConfigurations
);

const { httpLambdaRole, queueLambdaRole, httpRoleAttachments, queueRoleAttachments } = createSharedLambdaResources({
  rescoreQueue,
});

const lambdaSettings = {
  httpsListener,
  packageType: "Image" as const,
  imageUri: dockerGtcSubmitPassportLambdaImage,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  environment: [
    ...apiEnvironment,
    {
      name: "FF_API_ANALYTICS",
      value: "on",
    },
    {
      name: "SCORER_SERVER_SSM_ARN",
      value: scorerSecret.arn,
    },
    {
      name: "VERIFIER_URL",
      value: "http://core-alb.private.gitcoin.co/verifier/verify",
    },
  ].sort(secretsManager.sortByName),
  roleAttachments: httpRoleAttachments,
  role: httpLambdaRole,
  alertTopic: pagerdutyTopic,
  alb: alb,
};

// Create alarms for the load balancer
createLoadBalancerAlarms("scorer-service", alb.arnSuffix, alarmConfigurations, pagerdutyTopic);

// Get default VPC ID for target groups
const vpcId = pulumi.output(aws.ec2.getVpc({ default: true })).apply((vpc) => vpc.id);

// Manage Lambda services - Refactored to new pattern

// Submit Passport Lambda
const submitPassportLambda = createLambdaFunction({
  name: "submit-passport-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.submit_passport.submit_passport.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 1024,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const submitPassportTargetGroup = createLambdaTargetGroup({
  name: "l-submit-passport",
  lambda: submitPassportLambda,
  vpcId: vpcId,
});

// Ceramic Cache Stamps Bulk POST Lambda
const ccStampsBulkPostLambda = createLambdaFunction({
  name: "cc-v1-st-bulk-POST-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_POST.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccStampsBulkPostTargetGroup = createLambdaTargetGroup({
  name: "l-cc-st-bulk-POST-0",
  lambda: ccStampsBulkPostLambda,
  vpcId: vpcId,
});

// Ceramic Cache Stamps Bulk PATCH Lambda
const ccStampsBulkPatchLambda = createLambdaFunction({
  name: "cc-v1-st-bulk-PATCH-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_PATCH.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccStampsBulkPatchTargetGroup = createLambdaTargetGroup({
  name: "l-cc-st-bulk-PATCH-0",
  lambda: ccStampsBulkPatchLambda,
  vpcId: vpcId,
});

// Ceramic Cache Stamps Bulk DELETE Lambda
const ccStampsBulkDeleteLambda = createLambdaFunction({
  name: "cc-v1-st-bulk-DELETE-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_DELETE.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccStampsBulkDeleteTargetGroup = createLambdaTargetGroup({
  name: "l-cc-st-bulk-DEL-0",
  lambda: ccStampsBulkDeleteLambda,
  vpcId: vpcId,
});

// Ceramic Cache Score POST Lambda
const ccScorePostLambda = createLambdaFunction({
  name: "cc-v1-score-POST-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.score_POST.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccScorePostTargetGroup = createLambdaTargetGroup({
  name: "l-cc-v1-score-POST-0",
  lambda: ccScorePostLambda,
  vpcId: vpcId,
});

// Ceramic Cache Score GET Lambda
const ccScoreGetLambda = createLambdaFunction({
  name: "cc-v1-score-GET-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.score_GET.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccScoreGetTargetGroup = createLambdaTargetGroup({
  name: "l-cc-v1-score-GET-0",
  lambda: ccScoreGetLambda,
  vpcId: vpcId,
});

// Ceramic Cache Weights GET Lambda
const ccWeightsGetLambda = createLambdaFunction({
  name: "cc-weights-GET-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.weights_GET.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccWeightsGetTargetGroup = createLambdaTargetGroup({
  name: "l-cc-weights-GET-0",
  lambda: ccWeightsGetLambda,
  vpcId: vpcId,
});

// Ceramic Cache Stamp GET Lambda
const ccStampGetLambda = createLambdaFunction({
  name: "cc-v1-st-GET-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.scorer_api_passport.v1.stamp_GET.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 512,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const ccStampGetTargetGroup = createLambdaTargetGroup({
  name: "l-cc-v1-st-GET-0",
  lambda: ccStampGetLambda,
  vpcId: vpcId,
});

// Passport Analysis GET Lambda
const passportAnalysisLambda = createLambdaFunction({
  name: "passport-analysis-GET-0",
  dockerImage: dockerGtcSubmitPassportLambdaImage,
  dockerCommand: ["aws_lambdas.passport.analysis_GET.handler"],
  environment: lambdaSettings.environment.reduce(
    (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
      acc[e.name] = e.value;
      return acc;
    },
    {}
  ),
  memorySize: 256,
  timeout: 30,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

const passportAnalysisTargetGroup = createLambdaTargetGroup({
  name: "l-pp-anlys-GET-0",
  lambda: passportAnalysisLambda,
  vpcId: vpcId,
});

// Note: passport-analysis-GET-0 Lambda already created above

buildQueueLambdaFn({
  ...lambdaSettings,
  name: "rescore-0",
  memorySize: 1024,
  dockerCmd: ["aws_lambdas.rescore.handler"],
  roleAttachments: queueRoleAttachments,
  role: queueLambdaRole,
  queue: rescoreQueue,
});

// VERIFIER
const verifier = pulumi.all([verifierDockerImage]).apply(([_verifierDockerImage]) =>
  createVerifierService({
    vpcId: vpcID as pulumi.Output<string>,
    albListenerArn: privateAlbHttpListenerArn as pulumi.Output<string>,
    privateAlbArnSuffix: privatprivateAlbArnSuffixeAlbHttpListenerArn as pulumi.Output<string>,
    albPriorityRule: 1011,
    pathPatterns: ["/verifier/*"],
    clusterArn: cluster.arn,
    clusterName: cluster.name,
    dockerImage: _verifierDockerImage,
    vpcPrivateSubnets: vpcPrivateSubnetIds as pulumi.Output<string[]>,
    snsTopicArn: pagerdutyTopic.arn,
  })
);

export const verifierTaskArn = verifier.task.arn;

const createdTask = createTask({
  name: "batch-score-mbd-data",
  config: {
    ...baseScorerServiceConfig,
    securityGroup: secgrp,
    command: ["python", "manage.py", "process_batch_model_address_upload"].join(" "),
    scheduleExpression: "",
    alertTopic: pagerdutyTopic,
    cpu: 2048,
    memory: 4096,
  },
  environment: apiEnvironment,
  secrets: apiSecrets,
  scorerSecretManagerArn: scorerSecret.arn,
});

export const s3TriggeredECSTask = pulumi
  .all([passportAdminBucketId, passportAdminBucketName])
  .apply(([bucketId, bucketName]) => {
    return createS3InitiatedECSTask({
      bucketId,
      bucketName,
      legacyBucketName: `bulk-score-requests-${stack}`,
      clusterArn: cluster.arn,
      taskDefinitionArn: createdTask.task.arn,
      subnetIds: vpcPrivateSubnetIds,
      securityGroupIds: [secgrp.id],
      eventsStsAssumeRoleArn: createdTask.eventsStsAssumeRole.arn,
      containerName: createdTask.containerName,
    });
  });

const CLOUDFLARE_ZONE_ID = op.read.parse(`op://DevOps/passport-scorer-${stack}-secrets/interface/CLOUDFLARE_ZONE_ID`);

// Create a DNS record for the load balancer
pulumi.all([passportXyzDomainName]).apply((passportXyzDomainNameStr) => {
  const apiDomain = `api.${passportXyzDomainNameStr}`;
  const apiDomainRecord = new aws.route53.Record(apiDomain, {
    zoneId: passportXyzHostedZoneId,
    name: "api",
    type: "CNAME",
    ttl: 300,
    records: [alb.dnsName],
  });

  // CloudFlare Record
  const cloudflareApiRecord =
    stack === "production"
      ? new cloudflare.Record(`api-passport-xyz-record`, {
          name: `api`,
          zoneId: CLOUDFLARE_ZONE_ID,
          type: "CNAME",
          content: alb.dnsName,
          allowOverwrite: true,
          comment: `Points to API service running on AWS ECS task`,
        })
      : "";
});

const coreAlbPassportXyz = new aws.lb.ListenerCertificate(
  "core-alb-passport-xyz",
  {
    listenerArn: httpsListener.arn,
    certificateArn: passportXyzCertificateArn,
  },
  {}
);

if (stack === "production") {
  const coreAlbPassportXyzApi = new aws.lb.ListenerCertificate(
    "core-alb-passport-xyz-api",
    {
      listenerArn: httpsListener.arn,
      certificateArn: noStackPassportXyzCertificateArn,
    },
    {}
  );
}

const v2ApiResult = createV2Api({
  httpsListener,
  dockerLambdaImage: dockerGtcSubmitPassportLambdaImage,
  rustScorerZipArchive: rustScorerZipArchive,
  alarmConfigurations: alarmConfigurations,
  httpLambdaRole: httpLambdaRole,
  alb: alb,
  httpRoleAttachments: httpRoleAttachments,
  pagerdutyTopic: pagerdutyTopic,
  privateSubnetSecurityGroup: privateSubnetSecurityGroup,
  scorerSecret: scorerSecret,
  vpcPrivateSubnetIds: vpcPrivateSubnetIds,
  targetGroupRegistry: targetGroupRegistry,
  privateAlbHttpListenerArn: privateAlbHttpListenerArn,
});

const pythonLambdaLayer = createPythonLambdaLayer({
  name: "python",
  bucketId: codeBucketId,
});

const appApiResult = createAppApiLambdaFunctions({
  vpcId: vpcID,
  snsAlertsTopicArn: pagerdutyTopic.arn,
  httpsListenerArn: httpsListener.arn,
  scorerSecret: scorerSecret,
  privateSubnetSecurityGroup: privateSubnetSecurityGroup,
  vpcPrivateSubnetIds: vpcPrivateSubnetIds,
  lambdaLayerArn: pythonLambdaLayer.arn,
  bucketId: codeBucketId,
});

const embedResult = createEmbedLambdaFunctions({
  vpcId: vpcID,
  snsAlertsTopicArn: pagerdutyTopic.arn,
  httpsListenerArn: privateAlbHttpListenerArn,
  scorerSecret: scorerSecret,
  privateSubnetSecurityGroup: privateSubnetSecurityGroup,
  vpcPrivateSubnetIds: vpcPrivateSubnetIds,
  lambdaLayerArn: pythonLambdaLayer.arn,
  bucketId: codeBucketId,
});

createMonitoringLambdaFunction({
  vpcId: vpcID,
  snsAlertsTopicArn: pagerdutyTopic.arn,
  httpsListenerArn: privateAlbHttpListenerArn,
  privateSubnetSecurityGroup: privateSubnetSecurityGroup,
  vpcPrivateSubnetIds: vpcPrivateSubnetIds,
  lambdaLayerArn: pythonLambdaLayer.arn,
  bucketId: codeBucketId,
  scorerDbProxyEndpointConn: scorerDbProxyEndpointConn,
});

// Wire up centralized routing for all endpoints
// This must be done after all Lambda target groups are created
configureAllRouting({
  publicListener: httpsListener,
  internalListener: privateAlbHttpListenerArn ?
    pulumi.output(privateAlbHttpListenerArn).apply(
      (arn) => aws.lb.Listener.get("internal-alb-listener", arn)
    ) : undefined,
  targetGroups: {
    // V2 API target groups (includes Rust scorer if created)
    ...v2ApiResult?.targetGroups,

    // Ceramic cache target groups (refactored above)
    pythonSubmitPassport: submitPassportTargetGroup,
    pythonCeramicCacheBulkPost: ccStampsBulkPostTargetGroup,
    pythonCeramicCacheBulkPatch: ccStampsBulkPatchTargetGroup,
    pythonCeramicCacheBulkDelete: ccStampsBulkDeleteTargetGroup,
    pythonCeramicCacheScorePost: ccScorePostTargetGroup,
    pythonCeramicCacheScoreGet: ccScoreGetTargetGroup,
    pythonCeramicCacheWeights: ccWeightsGetTargetGroup,
    pythonCeramicCacheStamp: ccStampGetTargetGroup,
    pythonPassportAnalysis: passportAnalysisTargetGroup,

    // Registry fallback for all other routes
    pythonRegistry: targetGroupRegistry,

    // Embed target groups - mapping to expected names
    pythonEmbedAddStamps: embedResult?.targetGroups?.embedStTargetGroup,
    pythonEmbedValidateKey: embedResult?.targetGroups?.embedRlTargetGroup,
    pythonEmbedGetScore: embedResult?.targetGroups?.embedGsTargetGroup,

    // App API target groups
    pythonAppApiNonce: appApiResult?.targetGroups?.ccNonceTargetGroup,
    pythonAppApiAuthenticate: appApiResult?.targetGroups?.ccAuthTargetGroup,
  },
  stack,
  envName: stack,
});
