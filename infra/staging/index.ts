import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsx from "@pulumi/awsx";

import {
  ScorerEnvironmentConfig,
  ScorerService,
  buildHttpLambdaFn,
  createIndexerService,
  createScoreExportBucketAndDomain,
  createScorerECSService,
  createTargetGroup,
  getEnvironment,
  createSharedLambdaResources,
  createDeadLetterQueue,
  createRescoreQueue,
  buildQueueLambdaFn,
} from "../lib/scorer/service";

// The following vars are not allowed to be undefined, hence the `${...}` magic

//////////////////////////////////////////////////////////////
// Loading environment variables
//////////////////////////////////////////////////////////////
const route53Zone = `${process.env["ROUTE_53_ZONE"]}`;
const route53ZoneForPublicData = `${process.env["ROUTE_53_ZONE_FOR_PUBLIC_DATA"]}`;
export const domain = `api.staging.scorer.${process.env["DOMAIN"]}`;
export const publicDataDomain = `public.staging.scorer.${process.env["DOMAIN"]}`;
export const publicServiceUrl = `https://${domain}`;
const rootDomain = process.env["DOMAIN"];

const SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;
const RDS_SECRET_ARN = `${process.env["SCORER_RDS_SECRET_ARN"]}`;
const dbUsername = `${process.env["DB_USER"]}`;
const dbPassword = pulumi.secret(`${process.env["DB_PASSWORD"]}`);
const dbName = `${process.env["DB_NAME"]}`;
const flowerUser = `${process.env["FLOWER_USER"]}`;
const flowerPassword = `${process.env["FLOWER_PASSWORD"]}`;

export const dockerGtcPassportScorerImage = `${process.env["DOCKER_GTC_PASSPORT_SCORER_IMAGE"]}`;
export const dockerGtcPassportVerifierImage = `${process.env["DOCKER_GTC_PASSPORT_VERIFIER_IMAGE"]}`;

export const dockerGtcSubmitPassportLambdaImage = `${process.env["DOCKER_GTC_SUBMIT_PASSPORT_LAMBDA_IMAGE"]}`;
const trustedIAMIssuers = `${process.env["TRUSTED_IAM_ISSUERS"]}`;

const redashDbUsername = `${process.env["REDASH_DB_USER"]}`;
const redashDbPassword = pulumi.secret(`${process.env["REDASH_DB_PASSWORD"]}`);
const redashDbName = `${process.env["REDASH_DB_NAME"]}`;
const redashSecretKey = pulumi.secret(`${process.env["REDASH_SECRET_KEY"]}`);
const redashMailUsername = `${process.env["REDASH_MAIL_USERNAME"]}`;
const redashMailPassword = pulumi.secret(
  `${process.env["REDASH_MAIL_PASSWORD"]}`
);

//////////////////////////////////////////////////////////////
// Set up VPC
//////////////////////////////////////////////////////////////

const vpc = new awsx.ec2.Vpc("scorer", {
  subnetSpecs: [{ type: "Public" }, { type: "Private" }],
  numberOfAvailabilityZones: 2,
});

export const vpcID = vpc.vpcId;
export const vpcPrivateSubnetIds = vpc.privateSubnetIds;
export const vpcPublicSubnetIds = vpc.publicSubnetIds;
export const vpcPrivateSubnetId1 = vpcPrivateSubnetIds.apply(
  (values) => values[0]
);
export const vpcPublicSubnetId1 = vpcPublicSubnetIds.apply(
  (values) => values[0]
);
export const vpcPrivateSubnetId2 = vpcPrivateSubnetIds.apply(
  (values) => values[1]
);
export const vpcPublicSubnetId2 = vpcPublicSubnetIds.apply(
  (values) => values[1]
);

export const vpcPublicSubnet1 = vpcPublicSubnetIds.apply((subnets) => {
  return subnets[0];
});

// This matches the default security group that awsx previously created when creating the Cluster.
// https://github.com/pulumi/pulumi-awsx/blob/45136c540f29eb3dc6efa5b4f51cfe05ee75c7d8/awsx-classic/ecs/cluster.ts#L110
const privateSubnetSecurityGroup = new aws.ec2.SecurityGroup(
  "private-subnet-secgrp",
  {
    description: "Security Group for Web Services",
    vpcId: vpc.vpcId,
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
  }
);

//////////////////////////////////////////////////////////////
// Set up RDS instance
//////////////////////////////////////////////////////////////
let dbSubnetGroup = new aws.rds.SubnetGroup(`scorer-db-subnet`, {
  subnetIds: vpcPrivateSubnetIds,
});

const db_secgrp = new aws.ec2.SecurityGroup(`scorer-db-secgrp`, {
  description: "Security Group for DB",
  vpcId: vpc.vpcId,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 5432,
      toPort: 5432,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
});

const postgresql = new aws.rds.Instance(
  `scorer-db`,
  {
    allocatedStorage: 20,
    maxAllocatedStorage: 100,
    engine: "postgres",
    // engineVersion: "5.7",
    instanceClass: "db.t3.small",
    dbName: dbName,
    password: dbPassword,
    username: dbUsername,
    skipFinalSnapshot: true,
    dbSubnetGroupName: dbSubnetGroup.id,
    vpcSecurityGroupIds: [db_secgrp.id],
    backupRetentionPeriod: 5,
    performanceInsightsEnabled: true,
  },
  { protect: true }
);

//////////////////////////////////////////////////////////////
// Setup RDS PROXY
//////////////////////////////////////////////////////////////

const rdsProxyRole = new aws.iam.Role("scorer-proxy-role", {
  name: "scorer-proxy-role",
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Sid: "AllowRDSProxy",
        Effect: "Allow",
        Principal: {
          Service: "rds.amazonaws.com",
        },
        Action: "sts:AssumeRole",
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "rds-proxy-policy",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Sid: "GetSecretValue",
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: [RDS_SECRET_ARN],
          },
          {
            Sid: "DecryptSecretValue",
            Action: ["kms:Decrypt"],
            Effect: "Allow",
            Resource: ["*"],
            Condition: {
              StringEquals: {
                kmsViaService: "secretsmanager.us-west-2.amazonaws.com",
              },
            },
          },
        ],
      }),
    },
  ],
});

const scorerDbProxy = new aws.rds.Proxy("scorer-db-proxy", {
  auths: [
    {
      authScheme: "SECRETS",
      description: "SecretAccess",
      iamAuth: "DISABLED",
      secretArn: RDS_SECRET_ARN,
    },
  ],
  engineFamily: "POSTGRESQL",
  roleArn: rdsProxyRole.arn,
  vpcSubnetIds: vpcPrivateSubnetIds,
  debugLogging: false,
  idleClientTimeout: 600, // 10 minutes
  name: "scorer-db-proxy",
  requireTls: false,
  vpcSecurityGroupIds: [db_secgrp.id],
});

const scorerDbProxyDefaultTargetGroup = new aws.rds.ProxyDefaultTargetGroup(
  "scorer-default-tg",
  {
    dbProxyName: scorerDbProxy.name,
    connectionPoolConfig: {
      // connectionBorrowTimeout: 120,
      // Just leave some connections for edge cases, when we connect directly to DB
      maxConnectionsPercent: 98,
      // maxIdleConnectionsPercent: 50
    },
  }
);

const scorerDefaultProxyTarget = new aws.rds.ProxyTarget(
  "scorer-default-target",
  {
    dbInstanceIdentifier: postgresql.identifier,
    dbProxyName: scorerDbProxy.name,
    targetGroupName: scorerDbProxyDefaultTargetGroup.name,
  }
);

export const scorerDbProxyEndpoint = scorerDbProxy.endpoint;
export const rdsEndpoint = postgresql.endpoint;
export const rdsArn = postgresql.arn;
export const rdsConnectionUrl = pulumi.secret(
  pulumi.interpolate`psql://${dbUsername}:${dbPassword}@${scorerDbProxyEndpoint}/${dbName}`
);

export const rdsId = postgresql.id;

//////////////////////////////////////////////////////////////
// Set up Redis
//////////////////////////////////////////////////////////////

const redisSubnetGroup = new aws.elasticache.SubnetGroup(
  "scorer-redis-subnet",
  {
    subnetIds: vpcPrivateSubnetIds,
  }
);

const secgrp_redis = new aws.ec2.SecurityGroup("scorer-redis-secgrp", {
  description: "scorer-redis-secgrp",
  vpcId: vpc.vpcId,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 6379,
      toPort: 6379,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
});

const redis = new aws.elasticache.Cluster("scorer-redis", {
  engine: "redis",
  engineVersion: "4.0.10",
  nodeType: "cache.m5.large",
  numCacheNodes: 1,
  port: 6379,
  subnetGroupName: redisSubnetGroup.name,
  securityGroupIds: [secgrp_redis.id],
});

export const redisPrimaryNode = redis.cacheNodes[0];
// export const redisConnectionUrl = pulumi.interpolate`rediscache://${redisPrimaryNode.address}:${redisPrimaryNode.port}/0?client_class=django_redis.client.DefaultClient`
export const redisCacheOpsConnectionUrl = pulumi.interpolate`redis://${redisPrimaryNode.address}:${redisPrimaryNode.port}/0`;

//////////////////////////////////////////////////////////////
// Set up ALB and ECS cluster
//////////////////////////////////////////////////////////////

const cluster = new aws.ecs.Cluster("scorer");
// export const clusterInstance = cluster;
export const clusterId = cluster.id;

// Generate an SSL certificate
const certificate = new aws.acm.Certificate("cert", {
  domainName: domain,
  tags: {
    Environment: "staging",
  },
  validationMethod: "DNS",
});

const certificateValidationDomain = new aws.route53.Record(
  `${domain}-validation`,
  {
    name: certificate.domainValidationOptions[0].resourceRecordName,
    zoneId: route53Zone,
    type: certificate.domainValidationOptions[0].resourceRecordType,
    records: [certificate.domainValidationOptions[0].resourceRecordValue],
    ttl: 600,
  }
);

const certificateValidation = new aws.acm.CertificateValidation(
  "certificateValidation",
  {
    certificateArn: certificate.arn,
    validationRecordFqdns: [certificateValidationDomain.fqdn],
  },
  { customTimeouts: { create: "30s", update: "30s" } }
);

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
});

// Creates an ALB associated with our custom VPC.
const alb = new aws.alb.LoadBalancer(`scorer-service`, {
  loadBalancerType: "application",
  internal: false,
  securityGroups: [albSecGrp.id],
  subnets: vpcPublicSubnetIds,
  tags: {
    name: "lb-scorer-service",
  },
});

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
});

//////////////////////////////////////////////////////////////
// Set up the target groups
//////////////////////////////////////////////////////////////
// Target group with the port of the Docker image
const targetGroupDefault = createTargetGroup("scorer-api-default", vpcID);
const targetGroupPassport = createTargetGroup("scorer-api-passport", vpcID);
const targetGroupRegistry = createTargetGroup("scorer-api-reg", vpcID);
const targetGroupRegistrySubmitPassport = createTargetGroup(
  "scorer-api-reg-sp",
  vpcID
);

//////////////////////////////////////////////////////////////
// Create the HTTPS listener, and set the default target group
//////////////////////////////////////////////////////////////
const httpsListener = new aws.alb.Listener("scorer-https-listener", {
  loadBalancerArn: alb.arn,
  protocol: "HTTPS",
  port: 443,
  certificateArn: certificateValidation.certificateArn,
  defaultActions: [
    {
      type: "forward",
      targetGroupArn: targetGroupDefault.arn,
    },
  ],
});

// Create a DNS record for the load balancer
const www = new aws.route53.Record("scorer", {
  zoneId: route53Zone,
  name: domain,
  type: "A",
  aliases: [
    {
      name: alb.dnsName,
      zoneId: alb.zoneId,
      evaluateTargetHealth: true,
    },
  ],
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
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: SCORER_SERVER_SSM_ARN,
          },
        ],
      }),
    },
  ],
  managedPolicyArns: [
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  ],
  tags: {
    dpopp: "",
  },
});

const deadLetterQueue = createDeadLetterQueue({});

const rescoreQueue = createRescoreQueue({ deadLetterQueue });

const serviceTaskRole = new aws.iam.Role("scorer-service-execution-role", {
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
      name: "allow_write_sqs",
      policy: rescoreQueue.arn.apply((rescoreQueueArn) =>
        JSON.stringify({
          Version: "2012-10-17",
          Statement: [
            {
              Effect: "Allow",
              Action: ["sqs:SendMessage"],
              Resource: rescoreQueueArn,
            },
          ],
        })
      ),
    },
  ],
});

const envConfig: ScorerEnvironmentConfig = {
  allowedHosts: JSON.stringify([domain, "*"]),
  domain: domain,
  csrfTrustedOrigins: JSON.stringify([`https://${domain}`]),
  rdsConnectionUrl: rdsConnectionUrl,
  redisCacheOpsConnectionUrl: redisCacheOpsConnectionUrl,
  uiDomains: JSON.stringify([
    "scorer." + rootDomain,
    "www.scorer." + rootDomain,
  ]),
  debug: "off",
  passportPublicUrl: "https://staging.passport.gitcoin.co/",
  rescoreQueueUrl: rescoreQueue.url,
};
const environment = getEnvironment(envConfig);

//////////////////////////////////////////////////////////////
// Set up log groups for API service and worker
//////////////////////////////////////////////////////////////
const serviceLogGroup = new aws.cloudwatch.LogGroup("scorer-service", {
  retentionInDays: 90,
});
const workerLogGroup = new aws.cloudwatch.LogGroup("scorer-worker", {
  retentionInDays: 90,
});

//////////////////////////////////////////////////////////////
// Set up the Scorer ECS service
//////////////////////////////////////////////////////////////
const baseScorerServiceConfig: ScorerService = {
  cluster,
  alb,
  dockerImageScorer: dockerGtcPassportScorerImage,
  dockerImageVerifier: dockerGtcPassportVerifierImage,
  executionRole: dpoppEcsRole,
  taskRole: serviceTaskRole,
  logGroup: serviceLogGroup,
  subnets: vpc.privateSubnetIds,
  securityGroup: privateSubnetSecurityGroup,
  needsVerifier: false,
  httpListenerArn: httpsListener.arn,
  targetGroup: targetGroupDefault,
  autoScaleMinCapacity: 1,
  autoScaleMaxCapacity: 2,
  cpu: 512,
  memory: 1024,
};

const scorerServiceDefault = createScorerECSService(
  "scorer-api-default",
  {
    ...baseScorerServiceConfig,
    targetGroup: targetGroupDefault,
    memory: 2048,
    cpu: 1024,
  },
  envConfig
);

const scorerServiceRegistry = createScorerECSService(
  "scorer-api-reg",
  {
    ...baseScorerServiceConfig,
    listenerRulePriority: 3000,
    httpListenerRulePaths: ["/registry/*"],
    targetGroup: targetGroupRegistry,
    memory: 4096,
    cpu: 2048,
  },
  envConfig
);

const {
  httpLambdaRole,
  queueLambdaRole,
  httpRoleAttachments,
  queueRoleAttachments,
} = createSharedLambdaResources({
  rescoreQueue,
});

const lambdaSettings = {
  httpsListener,
  imageUri: dockerGtcSubmitPassportLambdaImage,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  environment: [
    ...environment,
    {
      name: "TRUSTED_IAM_ISSUERS",
      value: trustedIAMIssuers,
    },
    {
      name: "CERAMIC_CACHE_SCORER_ID",
      value: "14",
    },
    {
      name: "SCORER_SERVER_SSM_ARN",
      value: SCORER_SERVER_SSM_ARN,
    },
  ],
  roleAttachments: httpRoleAttachments,
  role: httpLambdaRole,
};

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "submit-passport",
  memorySize: 1024,
  dockerCmd: ["aws_lambdas.submit_passport.submit_passport.handler"],
  pathPatterns: ["/registry/submit-passport", "/registry/v2/submit-passport"],
  listenerPriority: 2001,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-bulk-POST",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_POST.handler"],
  pathPatterns: ["/ceramic-cache/stamps/bulk"],
  httpRequestMethods: ["POST"],
  listenerPriority: 2002,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-bulk-PATCH",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_PATCH.handler"],
  pathPatterns: ["/ceramic-cache/stamps/bulk"],
  httpRequestMethods: ["PATCH"],
  listenerPriority: 2003,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-bulk-DELETE",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_DELETE.handler"],
  pathPatterns: ["/ceramic-cache/stamps/bulk"],
  httpRequestMethods: ["DELETE"],
  listenerPriority: 2004,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-auhenticate",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.authenticate_POST.handler"],
  pathPatterns: [
    "/ceramic-cache/authenticate",
    "/ceramic-cache/v2/authenticate",
  ],
  httpRequestMethods: ["POST"],
  listenerPriority: 2005,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-score-POST",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.score_POST.handler"],
  pathPatterns: ["/ceramic-cache/score/*", "/ceramic-cache/v2/score/*"],
  httpRequestMethods: ["POST"],
  listenerPriority: 2006,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-score-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.score_GET.handler"],
  pathPatterns: ["/ceramic-cache/score/*", "/ceramic-cache/v2/score/*"],
  httpRequestMethods: ["GET"],
  listenerPriority: 2007,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-weights-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.weights_GET.handler"],
  pathPatterns: ["/ceramic-cache/weights", "/ceramic-cache/v2/weights"],
  httpRequestMethods: ["GET"],
  listenerPriority: 2015,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamp_GET.handler"],
  pathPatterns: ["/ceramic-cache/stamp"],
  httpRequestMethods: ["GET"],
  listenerPriority: 2010,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v2-st-bulk-POST",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v2.stamps.bulk_POST.handler"],
  pathPatterns: ["/ceramic-cache/v2/stamps/bulk"],
  httpRequestMethods: ["POST"],
  listenerPriority: 2011,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v2-st-bulk-PATCH",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v2.stamps.bulk_PATCH.handler"],
  pathPatterns: ["/ceramic-cache/v2/stamps/bulk"],
  httpRequestMethods: ["PATCH"],
  listenerPriority: 2012,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v2-st-bulk-DELETE",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v2.stamps.bulk_DELETE.handler"],
  pathPatterns: ["/ceramic-cache/v2/stamps/bulk"],
  httpRequestMethods: ["DELETE"],
  listenerPriority: 2013,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v2-st-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v2.stamp_GET.handler"],
  pathPatterns: ["/ceramic-cache/v2/stamp"],
  httpRequestMethods: ["GET"],
  listenerPriority: 2014,
});

buildQueueLambdaFn({
  ...lambdaSettings,
  name: "rescore",
  memorySize: 1024,
  dockerCmd: ["aws_lambdas.rescore.handler"],
  roleAttachments: queueRoleAttachments,
  role: queueLambdaRole,
  queue: rescoreQueue,
});

//////////////////////////////////////////////////////////////
// Set up the Celery Worker Service
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
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: SCORER_SERVER_SSM_ARN,
          },
        ],
      }),
    },
  ],
  managedPolicyArns: [
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  ],
  tags: {
    dpopp: "",
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
});

export const securityGroupForTaskDefinition = secgrp.id;

//////////////////////////////////////////////////////////////
// Set up EC2 instance
//      - it is intended to be used for troubleshooting
//////////////////////////////////////////////////////////////

const ubuntu = aws.ec2.getAmi({
  mostRecent: true,
  filters: [
    {
      name: "name",
      values: ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"],
    },
    {
      name: "virtualization-type",
      values: ["hvm"],
    },
  ],
  owners: ["099720109477"],
});

// Script to install docker in ec2 instance
const ec2InitScript = `#!/bin/bash

# Installing docker in ubuntu
# Instructions taken from here: https://docs.docker.com/engine/install/ubuntu/

mkdir /var/log/gitcoin
echo $(date) "Starting installation of docker" >> /var/log/gitcoin/init.log
apt-get remove docker docker-engine docker.io containerd runc

apt-get update

apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io awscli
mkdir /var/log/gitcoin
echo $(date) "Finished installation of docker" >> /var/log/gitcoin/init.log

`;

const web = new aws.ec2.Instance("Web", {
  ami: ubuntu.then((ubuntu) => ubuntu.id),
  associatePublicIpAddress: true,
  instanceType: "t3.small",
  subnetId: vpcPublicSubnetId1,
  vpcSecurityGroupIds: [secgrp.id],
  rootBlockDevice: {
    volumeSize: 50,
  },
  tags: {
    name: "Passport Scorer - troubleshooting instance",
  },
  userData: ec2InitScript,
});

export const ec2PublicIp = web.publicIp;
export const dockrRunCmd = pulumi.secret(
  pulumi.interpolate`docker run -it -e CERAMIC_CACHE_SCORER_ID=1 -e 'DATABASE_URL=${rdsConnectionUrl}' -e 'CELERY_BROKER_URL=${redisCacheOpsConnectionUrl}' '${dockerGtcPassportScorerImage}' bash`
);

///////////////////////
// Redash instance
///////////////////////

const redashDbSecgrp = new aws.ec2.SecurityGroup(`redashDbSecgrp`, {
  description: "Security Group for DB",
  vpcId: vpcID,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 5432,
      toPort: 5432,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
});

// Create an RDS instance
const redashDb = new aws.rds.Instance(
  "redash-db",
  {
    allocatedStorage: 20,
    maxAllocatedStorage: 20,
    engine: "postgres",
    engineVersion: "13.10",
    instanceClass: "db.t3.micro",
    dbName: redashDbName,
    password: redashDbPassword,
    username: redashDbUsername,
    skipFinalSnapshot: true,
    dbSubnetGroupName: dbSubnetGroup.id,
    vpcSecurityGroupIds: [redashDbSecgrp.id],
    backupRetentionPeriod: 5,
    performanceInsightsEnabled: true,
  },
  { protect: true }
);

const dbUrl = redashDb.endpoint;
export const redashDbUrl = pulumi.secret(
  pulumi.interpolate`postgresql://${redashDbUsername}:${redashDbPassword}@${dbUrl}/${redashDbName}`
);

const redashSecurityGroup = new aws.ec2.SecurityGroup(
  "redashServerSecurityGroup",
  {
    vpcId: vpcID,
    ingress: [
      {
        protocol: "tcp",
        fromPort: 443,
        toPort: 443,
        cidrBlocks: ["0.0.0.0/0"],
      }, // IPv4 HTTPS
      { protocol: "tcp", fromPort: 443, toPort: 443, ipv6CidrBlocks: ["::/0"] }, // IPv6 HTTPS
      { protocol: "tcp", fromPort: 22, toPort: 22, cidrBlocks: ["0.0.0.0/0"] }, // IPv4 SSH
      { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] }, // IPv4 HTTP
      { protocol: "tcp", fromPort: 80, toPort: 80, ipv6CidrBlocks: ["::/0"] }, // IPv6 HTTP
      {
        protocol: "tcp",
        fromPort: 5000,
        toPort: 5000,
        cidrBlocks: ["0.0.0.0/0"],
      }, // IPv4 Custom TCP 5000
      {
        protocol: "tcp",
        fromPort: 5000,
        toPort: 5000,
        ipv6CidrBlocks: ["::/0"],
      }, // IPv6 Custom TCP 5000
    ],
    egress: [
      {
        protocol: "-1",
        fromPort: 0,
        toPort: 0,
        cidrBlocks: ["0.0.0.0/0"],
      },
    ],
  }
);

const redashInitScript = redashDbUrl.apply((url) =>
  redashSecretKey.apply((secretKey) =>
    redashDbPassword.apply((dbPassword) =>
      redashMailPassword.apply(
        (mailPassword) =>
          `#!/bin/bash

          echo "Install docker-compose ..."
          curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
          chmod +x /usr/local/bin/docker-compose

          echo "Setting environment variables..."
          export POSTGRES_PASSWORD="${dbPassword}"
          export REDASH_DATABASE_URL="${url}"
          export REDASH_SECRET_KEY="${secretKey}"
          export REDASH_MAIL_USERNAME="${redashMailUsername}"
          export REDASH_MAIL_PASSWORD="${mailPassword}"
          export REDASH_HOST="https://redash.api.staging.scorer.gitcoin.co"
          export REDASH_MAIL_DEFAULT_SENDER="passport+redash_staging@gitcoin.co"

          echo "Try to pull from git repo or clone the repo if it was not cloned before ..."
          git pull /passport-redash || git clone https://github.com/gitcoinco/passport-redash.git /passport-redash
          
          echo "Changing directory and setting permissions..."
          cd /passport-redash
          
          chmod +x ./setup.sh
          ./setup.sh

          cd data
          sudo docker-compose up -d
          `
      )
    )
  )
);

const redashinstance = new aws.ec2.Instance("redashinstance", {
  ami: ubuntu.then((ubuntu) => ubuntu.id),
  associatePublicIpAddress: true,
  instanceType: "t3.small",
  subnetId: vpcPublicSubnetId2,
  rootBlockDevice: {
    volumeSize: 50,
  },
  tags: {
    name: "Redash Analytics",
  },
  userData: redashInitScript,
  vpcSecurityGroupIds: [redashSecurityGroup.id],
});

// Generate an SSL certificate
const redashCertificate = new aws.acm.Certificate("redash", {
  domainName: "redash." + domain,
  tags: {
    Environment: "staging",
  },
  validationMethod: "DNS",
});

const redashCertificateValidationDomain = new aws.route53.Record(
  `redash.${domain}-validation`,
  {
    name: redashCertificate.domainValidationOptions[0].resourceRecordName,
    zoneId: route53Zone,
    type: redashCertificate.domainValidationOptions[0].resourceRecordType,
    records: [redashCertificate.domainValidationOptions[0].resourceRecordValue],
    ttl: 600,
  }
);

const redashCertificateValidation = new aws.acm.CertificateValidation(
  "redashCertificateValidation",
  {
    certificateArn: redashCertificate.arn,
    validationRecordFqdns: [redashCertificateValidationDomain.fqdn],
  },
  { customTimeouts: { create: "30s", update: "30s" } }
);

const redashAlbSecGrp = new aws.ec2.SecurityGroup(`redash-service-alb`, {
  description: "redash-service-alb",
  vpcId: vpcID,
  ingress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
  egress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
});

// Creates an ALB associated with our custom VPC.
const redashAlb = new aws.alb.LoadBalancer(`redash-service`, {
  loadBalancerType: "application",
  internal: false,
  securityGroups: [redashAlbSecGrp.id],
  subnets: vpcPublicSubnetIds,
  tags: {
    name: "lb-redash-service",
  },
});

// Listen to HTTP traffic on port 80 and redirect to 443
const redashHttpListener = new aws.alb.Listener("redash-http-listener", {
  loadBalancerArn: redashAlb.arn,
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
});

// Target group with the port of the UI
const redashTarget = new aws.alb.TargetGroup("redash-target", {
  vpcId: vpcID,
  targetType: "ip",
  port: 80,
  protocol: "HTTP",
  healthCheck: { path: "/ping", unhealthyThreshold: 5 },
});

// Listen to traffic on port 443 & route it through the target group
const redashHttpsListener = new aws.alb.Listener("redash-https-listener", {
  loadBalancerArn: redashAlb.arn,
  protocol: "HTTPS",
  port: 443,
  certificateArn: redashCertificate.arn,
  defaultActions: [
    {
      type: "forward",
      targetGroupArn: redashTarget.arn,
    },
  ],
});

const redashRecord = new aws.route53.Record("redash", {
  zoneId: route53Zone,
  name: "redash." + domain,
  type: "A",
  aliases: [
    {
      name: redashAlb.dnsName,
      zoneId: redashAlb.zoneId,
      evaluateTargetHealth: true,
    },
  ],
});

new aws.lb.TargetGroupAttachment("redashTargetAttachment", {
  targetId: redashinstance.privateIp,
  targetGroupArn: redashTarget.arn,
});

// export const weeklyDataDumpTaskDefinition = createScheduledTask(
//   "weekly-data-dump",
//   {
//     ...baseScorerServiceConfig,
//     securityGroup: secgrp,
//     command: "python manage.py dump_stamp_data",
//     scheduleExpression: "cron(30 23 ? * FRI *)", // Run the task every friday at 23:30 UTC
//   },
//   envConfig
// );

// export const frequentAlloScorerDataDumpTaskDefinition = createScheduledTask(
//   "frequent-allo-scorer-data-dump",
//   {
//     ...baseScorerServiceConfig,
//     securityGroup: secgrp,
//     command: [
//       "python",
//       "manage.py",
//       "scorer_dump_data",
//       "--config",
//       JSON.stringify([
//         {
//           name: "registry.Score",
//           filter: { community_id: 14 },
//           select_related: ["passport"],
//         },
//       ]),

//       `--s3-uri=s3://public.${domain}`,
//       "--summary-extra-args",
//       JSON.stringify({ ACL: "public-read" }),
//     ].join(" "),

//     scheduleExpression: "cron(*/30 * ? * * *)", // Run the task every 30 min
//   },
//   envConfig
// );

const exportVals = createScoreExportBucketAndDomain(
  publicDataDomain,
  route53ZoneForPublicData
);

const pagerdutyTopic = new aws.sns.Topic("pagerduty", {
  name: "Pagerduty",
  tracingConfig: "PassThrough",
});

const rdsConnectionConfig = {
  dbUsername,
  dbPassword,
  dbName,
  dbHost: scorerDbProxyEndpoint,
  dbPort: String(5432),
};

createIndexerService({
  rdsConnectionConfig,
  cluster,
  vpc,
  privateSubnetSecurityGroup,
  workerRole,
  alertTopic: pagerdutyTopic,
});
