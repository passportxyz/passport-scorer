import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import { ListenerRule } from "@pulumi/aws/lb";
import { Listener } from "@pulumi/aws/alb";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../../lib/tags";

import { createLambdaFunction } from "../../lib/lambda";
import { createEmbedLambdaGeneric } from "./lambda_generic";

export function createEmbedLambdaFunctions(config: {
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
  createEmbedLambdaGeneric({
    ...config,
    name: "embed-st",
    description: "Submit stamps & score passport",
    lbRuleConditions: [
      {
        pathPattern: {
          values: ["/embed/stamps/*"],
        },
      },
      {
        httpRequestMethod: {
          values: ["POST"],
        },
      },
    ],
    lbRulePriority: 2100,
    lambdaHandler: "embed.lambda_fn.lambda_handler_save_stamps",
  });
  createEmbedLambdaGeneric({
    ...config,
    description: "Retreive the rate limit for an API key",
    name: "embed-rl",
    lbRuleConditions: [
      {
        pathPattern: {
          values: ["/embed/validate-api-key"],
        },
      },
      {
        httpRequestMethod: {
          values: ["GET"],
        },
      },
    ],
    lbRulePriority: 2101,
    lambdaHandler: "embed.lambda_fn.lambda_handler_get_rate_limit",
  });
}
