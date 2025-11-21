import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { TargetGroup, ListenerRule } from "@pulumi/aws/lb";

import { stack, defaultTags } from "../../lib/tags";
import { secretsManager } from "infra-libs";
import { AlarmConfigurations } from "../../lib/scorer/loadBalancer";
import { createRustScorerLambda } from "./rust-scorer";
import { createLambdaFunction, createLambdaTargetGroup } from "../../lib/scorer/routing-utils";

/// This function will create the infra for the V2 API
/// For now this will:
///   - reuse the lambda image passed in (which is the same used everywhere)
///   - reuse the registry service that is also used by the v1 API and others
export function createV2Api({
  httpsListener,
  dockerLambdaImage,
  rustScorerZipArchive,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  scorerSecret,
  pagerdutyTopic,
  httpRoleAttachments,
  httpLambdaRole,
  alb,
  alarmConfigurations,
  targetGroupRegistry,
  privateAlbHttpListenerArn,
}: {
  httpsListener: pulumi.Output<aws.alb.Listener>;
  dockerLambdaImage: pulumi.Output<string>;
  rustScorerZipArchive?: pulumi.asset.FileArchive;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcPrivateSubnetIds: pulumi.Output<any>;
  scorerSecret: aws.secretsmanager.Secret;
  pagerdutyTopic: aws.sns.Topic;
  httpRoleAttachments: aws.iam.RolePolicyAttachment[];
  httpLambdaRole: aws.iam.Role;
  alb: aws.alb.LoadBalancer;
  alarmConfigurations: AlarmConfigurations;
  targetGroupRegistry: TargetGroup;
  privateAlbHttpListenerArn?: pulumi.Input<string>;
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
    packageType: "Image" as const,
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

  // Create V2 Model Score Lambda and target group (Python only)
  const v2ModelScoreLambda = createLambdaFunction({
    name: "passport-v2-model-score",
    dockerImage: dockerLambdaImage,
    dockerCommand: ["v2.aws_lambdas.models_score_GET.handler"],
    environment: lambdaSettings.environment,
    memorySize: 256,
    timeout: 90,
    roleArn: httpLambdaRole.arn,
    securityGroupIds: [privateSubnetSecurityGroup.id],
    subnetIds: vpcPrivateSubnetIds,
  });

  const v2ModelScoreTargetGroup = createLambdaTargetGroup({
    name: "l-passport-v2-model-score",
    lambda: v2ModelScoreLambda,
    vpcId: pulumi.output(aws.ec2.getVpc({ default: true })).apply((vpc) => vpc.id),
  });

  // Create V2 Stamp Score Lambda and target group (DUAL - Python/Rust)
  const v2StampScoreLambda = createLambdaFunction({
    name: "passport-v2-stamp-score",
    dockerImage: dockerLambdaImage,
    dockerCommand: ["v2.aws_lambdas.stamp_score_GET.handler"],
    environment: lambdaSettings.environment,
    memorySize: 256,
    timeout: 60,
    roleArn: httpLambdaRole.arn,
    securityGroupIds: [privateSubnetSecurityGroup.id],
    subnetIds: vpcPrivateSubnetIds,
  });

  const v2StampScoreTargetGroup = createLambdaTargetGroup({
    name: "l-passport-v2-stamp-score",
    lambda: v2StampScoreLambda,
    vpcId: pulumi.output(aws.ec2.getVpc({ default: true })).apply((vpc) => vpc.id),
  });

  // Keep the history rule here (it uses the registry target group, not a Lambda)
  const targetPassportRuleHistory = new ListenerRule(`passport-v2-lrule-history`, {
    tags: { ...defaultTags, Name: "passport-v2-lrule-history" },
    listenerArn: httpsListener.arn,
    priority: 2022,
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
          values: ["/v2/stamps/*/score/*/history"],
        },
      },
      {
        httpRequestMethod: {
          values: ["GET"],
        },
      },
    ],
  });

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

  // Deploy Rust scorer Lambda if zip archive is provided
  if (rustScorerZipArchive) {
    // Convert privateAlbHttpListenerArn to Listener if provided
    const internalHttpsListener = privateAlbHttpListenerArn
      ? pulumi.output(privateAlbHttpListenerArn).apply(
          (arn) => aws.lb.Listener.get("internal-alb-listener", arn)
        )
      : undefined;

    createRustScorerLambda({
      httpsListener,
      rustScorerZipArchive,
      privateSubnetSecurityGroup,
      vpcPrivateSubnetIds,
      scorerSecret,
      pagerdutyTopic,
      httpRoleAttachments,
      httpLambdaRole,
      alb,
      alarmConfigurations,
      internalHttpsListener,
    });
  }

  // Return target groups for centralized routing
  return {
    pythonV2StampScore: v2StampScoreTargetGroup,
    pythonV2ModelScore: v2ModelScoreTargetGroup,
  };
}
