import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { createLambdaFunction } from "../lib/lambda";

export const stack = pulumi.getStack(); // values : review, staging & production

export const coreInfraOutputs = new pulumi.StackReference(
  `passportxyz/core-infra/${stack}`
);

export const coreRdsSecretArn = coreInfraOutputs.getOutput("coreRdsSecretArn");
export const coreVpcId = coreInfraOutputs.getOutput("vpcId");
export const corePrivateSubnetIds =
  coreInfraOutputs.getOutput("privateSubnetIds");

export const rdsSecretArn = coreInfraOutputs.getOutput("rdsSecretArn");

const dockerImageTag = process.env.DOCKER_IMAGE_TAG;
const awsAccNo = aws.getCallerIdentity().then((caller) => caller.accountId);

const dockerCmd = ["v2.aws_lambdas.showmigrations_GET.handler"];

const { lambdaFunction, lambdaFunctionUrl } = pulumi
  .all([coreVpcId, corePrivateSubnetIds, awsAccNo, rdsSecretArn])
  .apply(([vpcId, subnetIds, _awsAccNo, _rdsSecretArn]) => {
    const dockerImageUri = `${_awsAccNo}.dkr.ecr.us-west-2.amazonaws.com/submit-passport-lambdas:${dockerImageTag}`;
    return createLambdaFunction([_rdsSecretArn], vpcId, subnetIds, {
      name: "showmigrations",
      description: "Run showmigrations cmd",
      packageType: "Image",
      imageUri: dockerImageUri,
      imageConfig: { commands: dockerCmd },
      vpcConfig: {
        securityGroupIds: [],
        subnetIds,
      },
      environment: {
        variables: {
          CORE_SECRET_ARN: _rdsSecretArn,
          SECRET_KEY: "1234",
        },
      },
    });
  });
export const lambdaUrl = lambdaFunctionUrl.functionUrl.apply((url) => url);
