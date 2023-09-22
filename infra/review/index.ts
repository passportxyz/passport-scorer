import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsx from "@pulumi/awsx";

import {
  createScoreExportBucketAndDomain,
  createTargetGroup,
  ScorerEnvironmentConfig,
} from "../lib/scorer/service";
import { createScheduledTask } from "../lib/scorer/scheduledTasks";

// The following vars are not allowed to be undefined, hence the `${...}` magic

let route53Zone = `${process.env["ROUTE_53_ZONE"]}`;
export const domain = `api.review.scorer.${process.env["DOMAIN"]}`;
export const publicServiceUrl = `https://${domain}`;

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;
let dbUsername = `${process.env["DB_USER"]}`;
let dbPassword = pulumi.secret(`${process.env["DB_PASSWORD"]}`);
let dbName = `${process.env["DB_NAME"]}`;

export const dockerGtcPassportScorerImage = `${process.env["DOCKER_GTC_PASSPORT_SCORER_IMAGE"]}`;
export const dockerGtcPassportVerifierImage = `${process.env["DOCKER_GTC_PASSPORT_VERIFIER_IMAGE"]}`;

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

const postgresql = new aws.rds.Instance(
  `scorer-db`,
  {
    allocatedStorage: 12,
    engine: "postgres",
    // engineVersion: "5.7",
    instanceClass: "db.t3.micro",
    dbName: dbName,
    password: dbPassword,
    username: dbUsername,
    skipFinalSnapshot: true,
    dbSubnetGroupName: dbSubnetGroup.id,
    vpcSecurityGroupIds: [db_secgrp.id],
    backupRetentionPeriod: 5,
  },
  { protect: true }
);

export const rdsEndpoint = postgresql.endpoint;
export const rdsArn = postgresql.arn;
export const rdsConnectionUrl = pulumi.secret(
  pulumi.interpolate`psql://${dbUsername}:${dbPassword}@${rdsEndpoint}/${dbName}`
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
    Environment: "review",
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

// Target group with the port of the Docker image
const targetGroupDefault = createTargetGroup("scorer-api-default", vpcID);

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

const secrets = [
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
const environment = [
  {
    name: "DEBUG",
    value: "on",
  },
  {
    name: "DATABASE_URL",
    value: rdsConnectionUrl,
  },
  {
    name: "READ_REPLICA_0_URL",
    value: rdsConnectionUrl,
  },
  {
    name: "UI_DOMAINS",
    value: JSON.stringify([
      "scorer." + process.env["DOMAIN"],
      "www.scorer." + process.env["DOMAIN"],
    ]),
  },
  {
    name: "ALLOWED_HOSTS",
    value: JSON.stringify([domain, "*"]),
  },
  {
    name: "CSRF_TRUSTED_ORIGINS",
    value: JSON.stringify([`https://${domain}`]),
  },
  {
    name: "CELERY_BROKER_URL",
    value: redisCacheOpsConnectionUrl,
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
    value: "https://review.passport.gitcoin.co/",
  },
];

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
const service = new awsx.ecs.FargateService("scorer", {
  cluster: cluster.arn,
  desiredCount: 1,
  networkConfiguration: {
    subnets: vpc.privateSubnetIds,
    securityGroups: [privateSubnetSecurityGroup.id],
  },
  loadBalancers: [
    {
      containerName: "scorer",
      containerPort: 80,
      targetGroupArn: targetGroupDefault.arn,
    },
  ],
  taskDefinitionArgs: {
    logGroup: {
      existing: serviceLogGroup,
    },
    executionRole: {
      roleArn: dpoppEcsRole.arn,
    },
    containers: {
      scorer: {
        name: "scorer",
        image: dockerGtcPassportScorerImage,
        memory: 1024,
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
        environment: environment,
        linuxParameters: {
          initProcessEnabled: true,
        },
      },
      verifier: {
        name: "verifier",
        image: dockerGtcPassportVerifierImage,
        memory: 512,
        links: [],
        portMappings: [
          {
            containerPort: 8001,
            hostPort: 8001,
          },
        ],
        linuxParameters: {
          initProcessEnabled: true,
        },
      },
    },
  },
});

//////////////////////////////////////////////////////////////
// Set up the Celery Worker Secrvice
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

const celery1 = new awsx.ecs.FargateService("scorer-bkgrnd-worker-registry", {
  cluster: cluster.arn,
  desiredCount: 0,
  networkConfiguration: {
    subnets: vpc.privateSubnetIds,
    securityGroups: [privateSubnetSecurityGroup.id],
  },
  taskDefinitionArgs: {
    logGroup: {
      existing: workerLogGroup,
    },
    executionRole: {
      roleArn: workerRole.arn,
    },
    cpu: "1vCPU",
    memory: "2GB",
    containers: {
      worker1: {
        name: "worker1",
        image: dockerGtcPassportScorerImage,
        command: [
          "celery",
          "-A",
          "scorer",
          "worker",
          "-Q",
          "score_registry_passport",
          "-l",
          "DEBUG",
          "-c",
          "2",
        ],
        portMappings: [],
        secrets: secrets,
        environment: environment,
        dependsOn: [],
        links: [],
      },
    },
  },
});

const ecsScorerWorker1AutoscalingTarget = new aws.appautoscaling.Target(
  "scorer-worker1-autoscaling-target",
  {
    maxCapacity: 4,
    minCapacity: 0,
    resourceId: pulumi.interpolate`service/${cluster.name}/${celery1.service.name}`,
    scalableDimension: "ecs:service:DesiredCount",
    serviceNamespace: "ecs",
  }
);

const ecsScorerWorker1Autoscaling = new aws.appautoscaling.Policy(
  "scorer-worker1-autoscaling-policy",
  {
    policyType: "TargetTrackingScaling",
    resourceId: ecsScorerWorker1AutoscalingTarget.resourceId,
    scalableDimension: ecsScorerWorker1AutoscalingTarget.scalableDimension,
    serviceNamespace: ecsScorerWorker1AutoscalingTarget.serviceNamespace,
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

const celery2 = new awsx.ecs.FargateService("scorer-bkgrnd-worker-passport", {
  cluster: cluster.arn,
  desiredCount: 1,
  networkConfiguration: {
    subnets: vpc.privateSubnetIds,
    securityGroups: [privateSubnetSecurityGroup.id],
  },
  taskDefinitionArgs: {
    executionRole: {
      roleArn: workerRole.arn,
    },
    containers: {
      worker2: {
        name: "worker2",
        image: dockerGtcPassportScorerImage,
        command: [
          "celery",
          "-A",
          "scorer",
          "worker",
          "-Q",
          "score_passport_passport",
          "-l",
          "DEBUG",
        ],
        memory: 1024,
        cpu: 1024,
        portMappings: [],
        secrets: secrets,
        environment: environment,
        dependsOn: [],
        links: [],
      },
    },
  },
});

const ecsScorerWorker2AutoscalingTarget = new aws.appautoscaling.Target(
  "scorer-worker2-autoscaling-target",
  {
    maxCapacity: 2,
    minCapacity: 1,
    resourceId: pulumi.interpolate`service/${cluster.name}/${celery2.service.name}`,
    scalableDimension: "ecs:service:DesiredCount",
    serviceNamespace: "ecs",
  }
);

const ecsScorerWorker2Autoscaling = new aws.appautoscaling.Policy(
  "scorer-worker2-autoscaling-policy",
  {
    policyType: "TargetTrackingScaling",
    resourceId: ecsScorerWorker2AutoscalingTarget.resourceId,
    scalableDimension: ecsScorerWorker2AutoscalingTarget.scalableDimension,
    serviceNamespace: ecsScorerWorker2AutoscalingTarget.serviceNamespace,
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
    Name: "Passport Scorer - troubleshooting instance",
  },
  userData: ec2InitScript,
});

export const ec2PublicIp = web.publicIp;

export const dockrRunCmd = pulumi.secret(
  pulumi.interpolate`docker run -it -e 'DATABASE_URL=${rdsConnectionUrl}' -e 'CELERY_BROKER_URL=${redisCacheOpsConnectionUrl}' '${dockerGtcPassportScorerImage}' bash`
);

const envConfig: ScorerEnvironmentConfig = {
  allowedHosts: JSON.stringify([domain, "*"]),
  domain: domain,
  csrfTrustedOrigins: JSON.stringify([`https://${domain}`]),
  rdsConnectionUrl: rdsConnectionUrl,
  redisCacheOpsConnectionUrl: redisCacheOpsConnectionUrl,
  uiDomains: JSON.stringify([
    "scorer." + process.env["DOMAIN"],
    "www.scorer." + process.env["DOMAIN"],
  ]),
  debug: "off",
  passportPublicUrl: "https://staging.passport.gitcoin.co/",
};
