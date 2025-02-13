import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

import { createAppLambdaGeneric } from "./lambda_generic";

export function createAppApiLambdaFunctions(config: {
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListenerArn: pulumi.Input<string>;
  ceramicCacheScorerId: number;
  scorerSecret: aws.secretsmanager.Secret;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcId: pulumi.Input<string>;
  vpcPrivateSubnetIds: pulumi.Input<any>;
  lambdaLayerArn: pulumi.Input<string>;
  bucketId: pulumi.Input<string>;
}) {
  createAppLambdaGeneric({
    ...config,
    name: "cc-nonce",
    description: "Get nonce for authentication from app",
    lbRuleConditions: [
      {
        pathPattern: {
          values: ["/account/nonce"],
        },
      },
      {
        httpRequestMethod: {
          values: ["GET", "OPTIONS"],
        },
      },
    ],
    lbRulePriority: 5010,
    lambdaHandler: "app_api.lambda_fn.lambda_handler_account_nonce",
  });
  createAppLambdaGeneric({
    ...config,
    name: "cc-auth",
    description: "Authenticate a user and return JWT",
    lbRuleConditions: [
      {
        pathPattern: {
          values: ["/ceramic-cache/authenticate"],
        },
      },
      {
        httpRequestMethod: {
          values: ["POST", "OPTIONS"],
        },
      },
    ],
    lbRulePriority: 5020,
    lambdaHandler: "app_api.lambda_fn.lambda_handler_authenticate",
  });
}
