import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { buildHttpLambdaFn } from "../scorer/new_service";
import { TargetGroup, ListenerRule } from "@pulumi/aws/lb";

import { stack, defaultTags } from "../tags";
import { secretsManager } from "infra-libs";
import { AlarmConfigurations } from "../../lib/scorer/loadBalancer";

/// This function will create the infra for the V2 API
/// For now this will:
///   - reuse the lambda image passed in (which is the same used everywhere)
///   - reuse the registry service that is also used by the v1 API and others
export function createV2Api({
  httpsListener,
  dockerLambdaImage,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  ceramicCacheScorerId,
  scorerSecret,
  pagerdutyTopic,
  httpRoleAttachments,
  httpLambdaRole,
  alb,
  alarmConfigurations,
  targetGroupRegistry,
}: {
  httpsListener: pulumi.Output<aws.alb.Listener>;
  dockerLambdaImage: pulumi.Output<string>;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcPrivateSubnetIds: pulumi.Output<any>;
  ceramicCacheScorerId: number;
  scorerSecret: aws.secretsmanager.Secret;
  pagerdutyTopic: aws.sns.Topic;
  httpRoleAttachments: aws.iam.RolePolicyAttachment[];
  httpLambdaRole: aws.iam.Role;
  alb: aws.alb.LoadBalancer;
  alarmConfigurations: AlarmConfigurations;
  targetGroupRegistry: TargetGroup;
}) {
  const apiEnvironment = [
    ...secretsManager.getEnvironmentVars({
      vault: "DevOps",
      repo: "passport-scorer",
      env: stack,
      section: "api",
    }),
    {
      name: "DEBUG",
      value: "off",
    },
    {
      name: "LOGGING_STRATEGY",
      value: "structlog_json",
    },
  ].sort(secretsManager.sortByName);
  const lambdaSettings = {
    httpsListener,
    imageUri: dockerLambdaImage,
    privateSubnetSecurityGroup,
    vpcPrivateSubnetIds,
    environment: [
      ...apiEnvironment,
      {
        name: "FF_API_ANALYTICS",
        value: "on",
      },
      {
        name: "CERAMIC_CACHE_SCORER_ID",
        value: `${ceramicCacheScorerId}`,
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

  buildHttpLambdaFn(
    {
      ...lambdaSettings,
      name: "passport-v2-model-score",
      memorySize: 256,
      dockerCmd: ["v2.aws_lambdas.models_score_GET.handler"],
      httpListenerRulePaths: [
        {
          hostHeader: {
            values: ["*.passport.xyz"],
          },
        },
        {
          pathPattern: {
            values: ["/v2/models/score/*"],
          },
        },
        {
          httpRequestMethod: {
            values: ["GET"],
          },
        },
      ],
      listenerPriority: 2021,
    },
    alarmConfigurations
  );

  buildHttpLambdaFn(
    {
      ...lambdaSettings,
      name: "passport-v2-stamp-score",
      memorySize: 256,
      dockerCmd: ["v2.aws_lambdas.stamp_score_GET.handler"],
      httpListenerRulePaths: [
        {
          hostHeader: {
            values: ["*.passport.xyz"],
          },
        },
        {
          pathPattern: {
            values: ["/v2/stamps/*/score/*"],
          },
        },
        {
          httpRequestMethod: {
            values: ["GET"],
          },
        },
      ],
      listenerPriority: 2022,
    },
    alarmConfigurations
  );

  const targetPassportRule = new ListenerRule(`passport-v2-lrule`, {
    tags: { ...defaultTags, Name: "passport-v2-lrule" },
    listenerArn: httpsListener.arn,
    priority: 2060,
    actions: [
      {
        type: "forward",
        targetGroupArn: targetGroupRegistry.arn,
      },
    ],
    conditions: [
      {
        hostHeader: {
          values: ["*.passport.xyz"],
        },
      },
      {
        pathPattern: {
          values: ["/v2/*"],
        },
      },
    ],
  });
  const targetOnlyPassportDomainRule = new ListenerRule(`lrule-no-gitcoin-v2`, {
    tags: { ...defaultTags, Name: `lrule-no-gitcoin-v2` },
    listenerArn: httpsListener.arn,
    priority: 2000,
    actions: [
      {
        type: "fixed-response",
        fixedResponse: {
          contentType: "application/json",
          messageBody: JSON.stringify({
            msg: "This service is not available for requests to the `*.gitcoin.co` domain",
          }),
          statusCode: "400",
        },
      },
    ],
    conditions: [
      {
        hostHeader: {
          values: ["*.gitcoin.co"],
        },
      },
      {
        pathPattern: {
          values: ["/v2/*"],
        },
      },
    ],
  });
}
