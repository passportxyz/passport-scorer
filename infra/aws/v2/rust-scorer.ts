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
      name: "OTEL_EXPORTER_OTLP_ENDPOINT",
      value: "http://localhost:4318", // AWS ADOT collector endpoint (HTTP)
    },
    {
      name: "AWS_LAMBDA_EXEC_WRAPPER",
      value: "/opt/otel-instrument", // Enable X-Ray auto-instrumentation
    },
  ].sort(secretsManager.sortByName);

  // Deploy Rust scorer with zip-based deployment and OTEL layer
  buildHttpLambdaFn(
    {
      httpsListener,
      privateSubnetSecurityGroup,
      vpcPrivateSubnetIds,
      environment: apiEnvironment,
      roleAttachments: httpRoleAttachments,
      role: httpLambdaRole,
      alertTopic: pagerdutyTopic,
      alb: alb,
      name: "passport-v2-rust-scorer",
      memorySize: 256,
      timeout: 30,

      // Zip-based deployment
      packageType: "Zip",
      code: rustScorerZipArchive,
      handler: "bootstrap", // Rust custom runtime handler
      runtime: aws.lambda.Runtime.CustomAL2023,

      // AWS OTEL Lambda Layer for X-Ray integration (ARM64)
      // Official AWS ADOT account: 901920570463 (verified at aws-otel.github.io)
      // Latest version: aws-otel-collector-arm64-ver-0-117-0
      // See: https://aws-otel.github.io/docs/getting-started/lambda/lambda-go/
      layers: [
        pulumi.output(regionData).apply((region) =>
          `arn:aws:lambda:${region.name}:901920570463:layer:aws-otel-collector-arm64-ver-0-117-0:1`
        ),
      ],

      // Header-based routing - only route to Rust when X-Use-Rust-Scorer header is present
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
        {
          httpHeader: {
            httpHeaderName: "X-Use-Rust-Scorer",
            values: ["true"],
          },
        },
      ],
      // Higher priority (lower number) to catch before Python Lambda
      listenerPriority: 99,
    },
    alarmConfigurations
  );

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
