import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { buildHttpLambdaFn } from "../../lib/scorer/new_service";
import { secretsManager } from "infra-libs";
import { stack, defaultTags } from "../../lib/tags";
import { getRoutingPercentages } from "../../lib/scorer/routing-utils";

// Get current AWS region for OTEL Lambda layer ARN
const regionData = aws.getRegion({});

export function createRustScorerLambda({
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
}: {
  httpsListener: pulumi.Output<aws.alb.Listener>;
  rustScorerZipArchive: pulumi.asset.FileArchive;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcPrivateSubnetIds: pulumi.Output<any>;
  scorerSecret: aws.secretsmanager.Secret;
  pagerdutyTopic: aws.sns.Topic;
  httpRoleAttachments: aws.iam.RolePolicyAttachment[];
  httpLambdaRole: aws.iam.Role;
  alb: aws.alb.LoadBalancer;
  alarmConfigurations: any;
  internalHttpsListener: pulumi.Output<aws.alb.Listener>;
}) {
  // Get routing percentages based on environment
  const routingPercentages = getRoutingPercentages(stack);
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
    {
      name: "HUMAN_POINTS_ENABLED",
      value: "true",
    },
    {
      name: "HUMAN_POINTS_START_TIMESTAMP",
      value: "0",
    },
    {
      name: "HUMAN_POINTS_MTA_ENABLED",
      value: "true",
    },
    {
      name: "SCORER_SERVER_SSM_ARN",
      value: scorerSecret.arn,
    },
    // OpenTelemetry configuration for AWS X-Ray
    {
      name: "ENVIRONMENT",
      value: stack,
    },
    {
      name: "OTEL_ENABLED",
      value: "true",
    },
    {
      name: "OPENTELEMETRY_COLLECTOR_CONFIG_URI",
      value: "/var/task/collector.yaml", // Path to ADOT collector configuration
    },
    {
      name: "OTEL_SERVICE_NAME",
      value: "rust-scorer", // Service name for traces
    },
    {
      name: "AWS_LAMBDA_EXEC_WRAPPER",
      value: "/opt/otel-instrument", // Enable X-Ray auto-instrumentation
    },
  ].sort(secretsManager.sortByName);

  // Create Rust scorer Lambda function
  const rustScorerLambda = new aws.lambda.Function(
    "passport-v2-rust-scorer",
    {
      name: "passport-v2-rust-scorer",
      vpcConfig: {
        securityGroupIds: [privateSubnetSecurityGroup.id],
        subnetIds: vpcPrivateSubnetIds,
      },
      role: httpLambdaRole.arn,
      timeout: 30,
      memorySize: 256,
      environment: {
        variables: apiEnvironment.reduce(
          (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
            acc[e.name] = e.value;
            return acc;
          },
          {}
        ),
      },
      tags: { ...defaultTags, Name: "passport-v2-rust-scorer" },

      // Zip-based deployment
      packageType: "Zip",
      code: rustScorerZipArchive,
      handler: "bootstrap", // Rust custom runtime handler
      runtime: aws.lambda.Runtime.CustomAL2023,
      architectures: ["arm64"], // Required for ARM64 binaries and OTEL layer compatibility

      // AWS OTEL Lambda Layer for X-Ray integration (ARM64)
      // Official AWS ADOT account: 901920570463 (verified at aws-otel.github.io)
      // Latest version: aws-otel-collector-arm64-ver-0-117-0
      // See: https://aws-otel.github.io/docs/getting-started/lambda/lambda-go/
      layers: [
        pulumi
          .output(regionData)
          .apply((region) => `arn:aws:lambda:${region.name}:901920570463:layer:aws-otel-collector-arm64-ver-0-117-0:1`),
      ],
    },
    {
      dependsOn: httpRoleAttachments,
    }
  );

  // Create Lambda target group for public ALB (v2 and ceramic-cache endpoints)
  const rustScorerTargetGroup = new aws.lb.TargetGroup("l-passport-v2-rust-scorer", {
    name: "l-passport-v2-rust-scorer",
    targetType: "lambda",
    tags: { ...defaultTags, Name: "l-passport-v2-rust-scorer" },
  });

  // Grant ALB permission to invoke the Lambda
  const rustScorerLambdaPermission = new aws.lambda.Permission("withLb-passport-v2-rust-scorer", {
    action: "lambda:InvokeFunction",
    function: rustScorerLambda.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: rustScorerTargetGroup.arn,
  });

  // Attach Lambda to target group
  const rustScorerTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    "lambdaTargetGroupAttachment-passport-v2-rust-scorer",
    {
      targetGroupArn: rustScorerTargetGroup.arn,
      targetId: rustScorerLambda.arn,
    },
    {
      dependsOn: [rustScorerLambdaPermission],
    }
  );

  // Create internal target group (required for embed endpoints)
  if (!internalHttpsListener) {
    throw new Error("Internal HTTPS listener is required for Rust scorer (needed for embed endpoints)");
  }

  const internalTargetGroup = new aws.lb.TargetGroup("l-passport-v2-rust-scorer-int", {
    name: "l-passport-v2-rust-scorer-int",
    targetType: "lambda",
    tags: { ...defaultTags, Name: "l-passport-v2-rust-scorer-int" },
  });

  // Grant internal ALB permission to invoke the Lambda
  const rustScorerInternalLambdaPermission = new aws.lambda.Permission("withLb-passport-v2-rust-scorer-int", {
    action: "lambda:InvokeFunction",
    function: rustScorerLambda.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: internalTargetGroup.arn,
  });

  // Attach Lambda to internal target group
  const rustScorerInternalTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    "lambdaTargetGroupAttachment-passport-v2-rust-scorer-int",
    {
      targetGroupArn: internalTargetGroup.arn,
      targetId: rustScorerLambda.arn,
    },
    {
      dependsOn: [rustScorerInternalLambdaPermission],
    }
  );

  // IMPORTANT: Listener rules are now created centrally in routing-rules.ts
  // This file only creates the Lambda and target groups, then exports them

  // Return the target groups for use in centralized routing
  return {
    targetGroups: {
      rustScorer: rustScorerTargetGroup,
      rustScorerInternal: internalTargetGroup,
    },
  };
}
