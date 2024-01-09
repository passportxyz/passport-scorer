import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { ScorerEnvironmentConfig, getScorerEnvs, getScorerSecrets } from './utils';
import { manageEcsService } from './ecs';
import { resolve } from "path";

//////////////////////////////////////////////////////////////
// Loading environment variables
//////////////////////////////////////////////////////////////
export const SCORER_SERVER_SSM_ARN =  `arn:aws:secretsmanager:us-west-2:025742772000:secret:scorer-service-zyD2Uo` //`${process.env["SCORER_SERVER_SSM_ARN"]}`;
export const dockerGtcPassportScorerImage = `public.ecr.aws/i8r3d4s6/passport-scorer:af9097c` // `${process.env["DOCKER_GTC_PASSPORT_SCORER_IMAGE"]}`;



// TODO: clarify this
const route53Domain = 'alpha.api.review.scorer.gitcoin.co' // `${process.env["ROUTE_53_DOMAIN"]}`;
const route53Zone = 'Z0918732DTS4QJE3PZY' // `${process.env["ROUTE_53_ZONE"]}`;
const rootDomain = 'gitcoin.co' // `${process.env["DOMAIN"]}`;

//////////////////////////////////////////////////////////////
// Loading Core Infra variables 
//////////////////////////////////////////////////////////////
// TODO: change this back !!!
const coreInfraStack = new pulumi.StackReference(`gitcoin/core-infra/review`); // new pulumi.StackReference(`gitcoin/core-infra/${stack}`);
// VPC
const vpcId = coreInfraStack.getOutput("vpcId");
const vpcCidr = coreInfraStack.getOutput("vpcCidr");
const vpcPrivateSubnets = coreInfraStack.getOutput("privateSubnetIds");

// ALB Data 
const albDnsName = coreInfraStack.getOutput("coreAlbDns");
const albName = coreInfraStack.getOutput("coreAlbName");
const albZoneId = coreInfraStack.getOutput("coreAlbZoneId");
const albHttpsListenerArn = coreInfraStack.getOutput("coreAlbHttpsListenerArn");
// SNS Topic for Alerts
const snsAlertsTopicArn = coreInfraStack.getOutput("snsAlertsTopicArn");

// DB 
const redisConnectionUrl = pulumi.interpolate`${coreInfraStack.getOutput("staticRedisConnectionUrl")}`;
const rdsConnectionUrl = pulumi.interpolate`${coreInfraStack.getOutput("staticRdsConnectionUrl")}`;
const rdsReadReplica0ConnectionUrl =pulumi.interpolate`${coreInfraStack.getOutput("staticRdsReadReplica0ConnectionUrl")}`;
// export const rdsConnectionUrl = pulumi.secret(
//     pulumi.interpolate`psql://${dbUsername}:${dbPassword}@${scorerDbProxyEndpoint}/${dbName}`
// );
  
// export const readreplica0ConnectionUrl = pulumi.secret(
//     pulumi.interpolate`psql://${dbUsername}:${dbPassword}@${readreplica0.endpoint}/${dbName}`
// );

// TODO: @Geri is access log for ALB required ? 

//////////////////////////////////////////////////////////////
// Constant Variables
//////////////////////////////////////////////////////////////

const stack = pulumi.getStack();
export const region = aws.getRegion({});

const logsRetention = Object({
    "review-alpha": 1,
    "review": 1,
    "staging": 7,
    "production": 90
});


const scorerApiResources = Object({ // TODO: 
    "review-alpha": {
      memory: 512, // 512 MiB
      cpu: 256 // 0.25 vCPU
    }, 
    "staging": {
      memory: 512, // 512 MiB
      cpu: 256 // 0.25 vCPU
    },
    "production": {
      memory: 1024, // 1GB
      cpu: 512 // 0.5 vCPU
    }
});

const defaultTags = {
    ManagedBy: "pulumi",
    PulumiStack: stack,
    Project: "scorer"
};

//////////////////////////////////////////////////////////////
// ECS resources
//////////////////////////////////////////////////////////////

const cluster = new aws.ecs.Cluster("scorer", {
    name: `scorer`,
    settings: [{ name: "containerInsights", value: "enabled" }],
    tags: {
        ...defaultTags,
        Name: `scorer`
    }
});

//////////////////////////////////////////////////////////////
// Scorer API Default
//////////////////////////////////////////////////////////////

const envConfig: ScorerEnvironmentConfig = {
    allowedHosts: JSON.stringify([route53Domain, "*"]),
    domain: route53Domain,
    csrfTrustedOrigins: JSON.stringify([`https://${route53Domain}`]),
    rdsConnectionUrl: rdsConnectionUrl,
    readReplicaConnectionUrl: rdsReadReplica0ConnectionUrl,
    redisCacheOpsConnectionUrl: redisConnectionUrl,
    uiDomains: JSON.stringify([
        "scorer." + rootDomain,
        "www.scorer." + rootDomain,
    ]),
    debug: "off",
    passportPublicUrl: "https://passport.gitcoin.co/",
};

const envs = getScorerEnvs(envConfig);

const scorerApiDefault = manageEcsService(
   `scorer-api-default`,
    {
        logsRetention: logsRetention[stack],
        networking: {
            vpcId: vpcId,
            subnets: vpcPrivateSubnets,
            securityGroup: [{ // ingress rules only 
                fromPort: 80,
                toPort: 80,
                protocol: "tcp",
                cidrBlocks: ["0.0.0.0/0"] // [vpcCidr.apply(s => s)], // ["0.0.0.0/0"] // [vpcCidr,]
            }]
        }, 
        role: {
            managedPolicyArns: ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"],
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
        },
        containers: pulumi.all([redisConnectionUrl]).apply(([_redisConnectionUrl]) => {
            return JSON.stringify([{
                name: `scorer`,
                image: dockerGtcPassportScorerImage,
                cpu: scorerApiResources[stack]["cpu"],
                memory: scorerApiResources[stack]["memory"],
                links: [],
                essential: true,
                portMappings: [{
                    containerPort: 80,
                    hostPort: 80,
                    protocol: "tcp"
                }],
                environment: envs, 
                logConfiguration: {
                    logDriver: "awslogs",
                    options: {
                        "awslogs-group": "scorer-api-default", // `${serviceLogGroup.name}`,
                        "awslogs-region": "us-west-2", // `${regionId}`,
                        "awslogs-create-group": "true",
                        "awslogs-stream-prefix": "iam"
                    }
                },
                secrets: getScorerSecrets(SCORER_SERVER_SSM_ARN),
                mountPoints: [],
                volumesFrom: []
            }])
        }),
        resources: {
            cpu: scorerApiResources[stack]["cpu"],
            memory: scorerApiResources[stack]["memory"],
        },
        cluster: {
            arn: pulumi.all([cluster]).apply(([_cluster]) => cluster.arn),
            name: pulumi.all([cluster]).apply(([_cluster]) => cluster.name),
        },
        targetGroup: {
            healthCheck: {
                enabled: true,
                healthyThreshold: 3,
                interval: 30,
                matcher: "200",
                path: "/health",
                port: "traffic-port",
                protocol: "HTTP",
                timeout: 5,
                unhealthyThreshold: 5
            },
            port: 80,
            protocol: "HTTP",
            targetType: "ip",
        },
        service: {
            desiredCount: 2,
            loadBalancers: [{
                containerName: `scorer`,
                containerPort: 80,
            }]
        },
        lbRule: {
            lbName: albName, 
            name: `scorer-default-https`,
            listenerArn: albHttpsListenerArn,
            hostHeaders: [route53Domain]
        },
        asg: {
            maxCapacity: 20,
            minCapacity: 2,
        },
        alertTopicArn: snsAlertsTopicArn
    },
    {
        ...defaultTags,
        EcsService: `scorer-api-default`,
        EcsCluster: `scorer`
    }
);


//
// const workerLogGroup = new aws.cloudwatch.LogGroup("scorer-worker", {
//     retentionInDays: logsRetention[stack],
//     tags: {
//       name: `cloudwatch-loggroup-scorer-worker`,
//     },
// });



// Scorer API Default


// const scorerServiceRegistry





// // TODO: clarify how this should be managed !!!!
// const targetGroupRegistry = new aws.lb.TargetGroup(`scorer-api-reg`, {
//     name: `scorer-api-reg`,
//     vpcId: vpcId,
//     healthCheck: {
//         enabled: true,
//         healthyThreshold: 3,
//         interval: 30,
//         matcher: "200",
//         path: "/health",
//         port: "traffic-port",
//         protocol: "HTTP",
//         timeout: 5,
//         unhealthyThreshold: 5
//     },
//     port: 80,
//     protocol: "HTTP",
//     targetType: "ip",
//     tags: {
//         ...defaultTags,
//         Name: `scorer-api-reg`
//     }
// });



//////////////////////////////////////////////////////////////
// ROUTE 53 - Scorer
//////////////////////////////////////////////////////////////

const scorerRecord = new aws.route53.Record("scorer", {
    name: route53Domain,
    zoneId: route53Zone,
    type: "A",
    aliases: [{
        name: albDnsName,
        zoneId: albZoneId,
        evaluateTargetHealth: true
    }]
});
