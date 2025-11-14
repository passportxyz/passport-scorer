import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { buildHttpLambdaFn } from "../../lib/scorer/new_service";
import { secretsManager } from "infra-libs";
import { stack, defaultTags } from "../../lib/tags";

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
  internalHttpsListener?: pulumi.Output<aws.alb.Listener>;
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

  // Create Lambda target group (reused for all routes)
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

  // Create listener rules for all Rust scorer endpoints

  // 1. Main v2 scoring endpoint (header-based routing)
  new aws.lb.ListenerRule("lrule-rust-v2-stamps-score", {
    tags: { ...defaultTags, Name: "lrule-rust-v2-stamps-score" },
    listenerArn: httpsListener.arn,
    priority: 99,
    actions: [
      {
        type: "forward",
        targetGroupArn: rustScorerTargetGroup.arn,
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
          values: ["/v2/stamps/*/score/*"],
        },
      },
      {
        httpRequestMethod: {
          values: ["GET"],
        },
      },
      {
        httpHeader: {
          httpHeaderName: "X-Use-Rust-Scorer",
          values: ["true"],
        },
      },
    ],
  });

  // 2. Ceramic-cache endpoints (header-based routing on public ALB)
  new aws.lb.ListenerRule("lrule-rust-ceramic-cache-stamps-bulk", {
    tags: { ...defaultTags, Name: "lrule-rust-ceramic-cache-stamps-bulk" },
    listenerArn: httpsListener.arn,
    priority: 5030,
    actions: [
      {
        type: "forward",
        targetGroupArn: rustScorerTargetGroup.arn,
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
          values: ["/ceramic-cache/stamps/bulk"],
        },
      },
      {
        httpRequestMethod: {
          values: ["POST"],
        },
      },
      {
        httpHeader: {
          httpHeaderName: "X-Use-Rust-Scorer",
          values: ["true"],
        },
      },
    ],
  });

  new aws.lb.ListenerRule("lrule-rust-ceramic-cache-score", {
    tags: { ...defaultTags, Name: "lrule-rust-ceramic-cache-score" },
    listenerArn: httpsListener.arn,
    priority: 5040,
    actions: [
      {
        type: "forward",
        targetGroupArn: rustScorerTargetGroup.arn,
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
          values: ["/ceramic-cache/score/*"],
        },
      },
      {
        httpRequestMethod: {
          values: ["GET"],
        },
      },
      {
        httpHeader: {
          httpHeaderName: "X-Use-Rust-Scorer",
          values: ["true"],
        },
      },
    ],
  });

  // 3. Embed endpoints (header-based routing on internal ALB if available)
  // Note: Using priorities 2090-2093 (LOWER than Python's 2100-2103) so these more specific
  // rules (with X-Use-Rust-Scorer header) are evaluated first
  if (internalHttpsListener) {
    new aws.lb.ListenerRule("lrule-rust-embed-stamps", {
      tags: { ...defaultTags, Name: "lrule-rust-embed-stamps" },
      listenerArn: internalHttpsListener.arn,
      priority: 2090,
      actions: [
        {
          type: "forward",
          targetGroupArn: rustScorerTargetGroup.arn,
        },
      ],
      conditions: [
        {
          pathPattern: {
            values: ["/internal/embed/stamps/*"],
          },
        },
        {
          httpRequestMethod: {
            values: ["POST"],
          },
        },
        {
          httpHeader: {
            httpHeaderName: "X-Use-Rust-Scorer",
            values: ["true"],
          },
        },
      ],
    });

    new aws.lb.ListenerRule("lrule-rust-embed-validate-api-key", {
      tags: { ...defaultTags, Name: "lrule-rust-embed-validate-api-key" },
      listenerArn: internalHttpsListener.arn,
      priority: 2091,
      actions: [
        {
          type: "forward",
          targetGroupArn: rustScorerTargetGroup.arn,
        },
      ],
      conditions: [
        {
          pathPattern: {
            values: ["/internal/embed/validate-api-key"],
          },
        },
        {
          httpRequestMethod: {
            values: ["GET"],
          },
        },
        {
          httpHeader: {
            httpHeaderName: "X-Use-Rust-Scorer",
            values: ["true"],
          },
        },
      ],
    });

    new aws.lb.ListenerRule("lrule-rust-embed-score", {
      tags: { ...defaultTags, Name: "lrule-rust-embed-score" },
      listenerArn: internalHttpsListener.arn,
      priority: 2093,
      actions: [
        {
          type: "forward",
          targetGroupArn: rustScorerTargetGroup.arn,
        },
      ],
      conditions: [
        {
          pathPattern: {
            values: ["/internal/embed/score/*/*"],
          },
        },
        {
          httpRequestMethod: {
            values: ["GET"],
          },
        },
        {
          httpHeader: {
            httpHeaderName: "X-Use-Rust-Scorer",
            values: ["true"],
          },
        },
      ],
    });
  }

  /*
   * Future: Weighted Target Group Routing
   * ----------------------------------------
   * Instead of header-based routing, you can use ALB weighted routing
   * to gradually roll out the Rust implementation:
   *
   * const rustTargetGroup = new aws.lb.TargetGroup("rust-scorer-tg", {
   *   name: "rust-scorer-tg",
   *   targetType: "lambda",
   *   tags: { ...defaultTags, Name: "rust-scorer-tg" },
   * });
   *
   * const pythonTargetGroup = // existing Python Lambda target group
   *
   * new aws.lb.ListenerRule("scorer-weighted-rule", {
   *   listenerArn: httpsListener.arn,
   *   priority: 100,
   *   actions: [{
   *     type: "forward",
   *     forward: {
   *       targetGroups: [
   *         { arn: pythonTargetGroup.arn, weight: 95 },  // 95% to Python
   *         { arn: rustTargetGroup.arn, weight: 5 }       // 5% to Rust
   *       ],
   *       stickiness: {
   *         enabled: true,
   *         duration: 3600,  // 1 hour session affinity
   *       }
   *     }
   *   }],
   *   conditions: [
   *     { pathPattern: { values: ["/v2/stamps/*\/score/*"] }},
   *     { httpRequestMethod: { values: ["GET"] }}
   *   ],
   *   tags: { ...defaultTags, Name: "scorer-weighted-rule" },
   * });
   *
   * This allows gradual rollout:
   * - Start with 5% traffic to Rust
   * - Monitor metrics and error rates
   * - Gradually increase: 5% → 10% → 25% → 50% → 100%
   * - Session affinity ensures users get consistent experience
   */
}
