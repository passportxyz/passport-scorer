import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { getScorerContainers} from './utils';
import { manageEcsService } from './ecs';
import { createScorerEcsIamRole } from './iam';
import {
    ROUTE53_DOMAIN, ROUTE53_ZONE, 
    SCORER_SERVER_SSM_ARN,
    coreInfraStack,
  } from './envs';

//////////////////////////////////////////////////////////////
// Loading environment variables
//////////////////////////////////////////////////////////////


//////////////////////////////////////////////////////////////
// Loading Core Infra variables 
//////////////////////////////////////////////////////////////
const vpcId = coreInfraStack.getOutput("vpcId");
const vpcCidr = coreInfraStack.getOutput("vpcCidr");
const vpcPrivateSubnets = coreInfraStack.getOutput("privateSubnetIds");

// ALB Data 
const ALB_DNS_NAME = coreInfraStack.getOutput("coreAlbDns");
const ALB_NAME = coreInfraStack.getOutput("coreAlbName");
const ALB_ZONE_ID = coreInfraStack.getOutput("coreAlbZoneId");
const albHttpsListenerArn = coreInfraStack.getOutput("coreAlbHttpsListenerArn");

// SNS Topic for Alerts
const snsAlertsTopicArn = coreInfraStack.getOutput("snsAlertsTopicArn");

//////////////////////////////////////////////////////////////
// Constant Variables
//////////////////////////////////////////////////////////////

export const stack = pulumi.getStack();
export const region = aws.getRegion({});

const logsRetention = Object({
    "review-alpha": 1,
    "review": 1,
    "staging": 7,
    "production": 90
});

const scorerApiResources = Object({ 
    // TODO: 
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


const scorerApiRegResources = Object({ 
    // TODO: 
    "review-alpha": {
        memory: 512, // 512 MiB
        cpu: 256 // 0.25 vCPU
    }, 
    "staging": {
        memory: 512, // 512 MiB
        cpu: 256 // 0.25 vCPU
    },
    "production": {
        // TODO: isn't it too much?
        memory: 4096, // 4GB
        cpu: 2048 // 2 vCPU 
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
// Scorer API ECS
//////////////////////////////////////////////////////////////

const ecsExecutionRole = createScorerEcsIamRole([SCORER_SERVER_SSM_ARN], defaultTags);

const scorerApiDefault = manageEcsService(
    `scorer-api-default`,
    logsRetention[stack],
    {
        vpcId: vpcId,
        vpcCidr: vpcCidr,
        subnets: vpcPrivateSubnets,
    },
    getScorerContainers(`scorer-api-default`, scorerApiResources[stack]),
    ecsExecutionRole.arn,
    scorerApiResources[stack],
    cluster,
    2,
    {
        name: ALB_NAME, 
        ruleName: `scorer-default-https`,
        listenerArn: albHttpsListenerArn,
        hostHeaders: [ROUTE53_DOMAIN],
        pathPattern: ["/*"],
        rulePriority: 5000
    },
    {
        maxCapacity: 20,
        minCapacity: 2,
    },
    snsAlertsTopicArn,
    defaultTags,
)

const scorerServiceRegistry = manageEcsService(
    `scorer-api-reg`,
    logsRetention[stack],
    {
        vpcId: vpcId,
        vpcCidr: vpcCidr,
        subnets: vpcPrivateSubnets,
    },
    getScorerContainers(`scorer-api-reg`, scorerApiRegResources[stack]),
    ecsExecutionRole.arn,
    scorerApiRegResources[stack],
    cluster,
    2,
    {
        name: ALB_NAME, 
        ruleName: `scorer-reg-https`,
        listenerArn: albHttpsListenerArn,
        hostHeaders: [ROUTE53_DOMAIN],
        pathPattern: ["/registry/*"],
        rulePriority: 3000
    },
    {
        maxCapacity: 20,
        minCapacity: 2,
    },
    snsAlertsTopicArn,
    defaultTags,
)

//////////////////////////////////////////////////////////////
// ROUTE 53 - Scorer
//////////////////////////////////////////////////////////////

const scorerRecord = new aws.route53.Record("scorer", {
    name: ROUTE53_DOMAIN,
    zoneId: ROUTE53_ZONE,
    type: "A",
    aliases: [{
        name: ALB_DNS_NAME,
        zoneId: ALB_ZONE_ID,
        evaluateTargetHealth: true
    }]
});
