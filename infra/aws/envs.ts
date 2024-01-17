import * as pulumi from "@pulumi/pulumi";

export const ROUTE53_DOMAIN =`${process.env["ROUTE_53_DOMAIN"]}`
export const ROUTE53_ZONE = `${process.env["ROUTE_53_ZONE"]}`;
export const ROOT_DOMAIN = `${process.env["DOMAIN"]}`;

export const SCORER_DOCKER_IMG = `${process.env["DOCKER_GTC_PASSPORT_SCORER_IMAGE"]}`;
export const SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;


export const coreInfraStack = new pulumi.StackReference(`gitcoin/core-infra/review`); // new pulumi.StackReference(`gitcoin/core-infra/${stack}`);
// VPC 
export const vpcId = coreInfraStack.getOutput("vpcId");
export const vpcCidr = coreInfraStack.getOutput("vpcCidr");
export const vpcPrivateSubnets = coreInfraStack.getOutput("privateSubnetIds");

// DB connections
export const REDIS_URL = pulumi.interpolate`${coreInfraStack.getOutput("staticRedisConnectionUrl")}`;
export const RDS_URL = pulumi.interpolate`${coreInfraStack.getOutput("staticRdsConnectionUrl")}`;
export const RDS_RR_URL = pulumi.interpolate`${coreInfraStack.getOutput("staticRdsReadReplica0ConnectionUrl")}`;

export const AWS_REGION = "us-west-2"