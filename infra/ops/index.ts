import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { createLambdaFunction } from "./lambda";
import { stack, coreVpcId, corePrivateSubnetIds, rdsSecretArn } from "./config";

const dockerImageTag = process.env.DOCKER_IMAGE_TAG;
const awsAccNo = aws.getCallerIdentity().then((caller) => caller.accountId);

const dockerCmd = ["v2.aws_lambdas.showmigrations_GET.handler"];

const { lambdaFunction, lambdaFunctionUrl } = pulumi
  .all([coreVpcId, corePrivateSubnetIds, awsAccNo, rdsSecretArn])
  .apply(([vpcId, subnetIds, _awsAccNo, _rdsSecretArn]) => {
    const dockerImageUri = `${_awsAccNo}.dkr.ecr.us-west-2.amazonaws.com/submit-passport-lambdas:${dockerImageTag}`;
    console.log("_rdsSecretArn", _rdsSecretArn);
    return createLambdaFunction(
      "showmigrations",
      "Run showmigrations cmd",
      dockerImageUri,
      dockerCmd,
      vpcId,
      subnetIds,
      [_rdsSecretArn],
      {
        CORE_SECRET_ARN: _rdsSecretArn,
      }
    );
  });
export const lambdaUrl = lambdaFunctionUrl.functionUrl.apply((url) => url);
