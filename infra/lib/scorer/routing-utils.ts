import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { AlarmConfigurations, TargetGroupAlarmsConfiguration } from "./loadBalancer";
import { defaultTags } from "../tags";

/**
 * Create a target group for a Lambda function and attach it
 * This handles the permission grant and attachment
 */
export function createLambdaTargetGroup(args: {
  name: string;
  lambda: aws.lambda.Function;
  vpcId: pulumi.Input<string>;
}): aws.lb.TargetGroup {
  // Create the target group
  // Note: Lambda target groups don't support health checks
  const targetGroup = new aws.lb.TargetGroup(`${args.name}-tg`, {
    targetType: "lambda",
    vpcId: args.vpcId,
  });

  // Grant permission for ALB to invoke the Lambda
  const permission = new aws.lambda.Permission(`${args.name}-permission`, {
    action: "lambda:InvokeFunction",
    function: args.lambda.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: targetGroup.arn,
  });

  // Attach the Lambda to the target group
  const attachment = new aws.lb.TargetGroupAttachment(
    `${args.name}-attachment`,
    {
      targetGroupArn: targetGroup.arn,
      targetId: args.lambda.arn,
    },
    { dependsOn: [permission] }
  );

  return targetGroup;
}

/**
 * Create a simple listener rule for single-target routing
 * Used for Python-only endpoints
 * Supports optional fixedResponse for blocking rules (e.g., blocking gitcoin.co)
 */
export function createListenerRule(args: {
  name: string;
  listenerArn: pulumi.Output<string>;
  priority: number;
  targetGroupArn?: pulumi.Output<string>;
  conditions: aws.types.input.lb.ListenerRuleCondition[];
  fixedResponse?: {
    contentType: string;
    messageBody: string;
    statusCode: string;
  };
}): aws.lb.ListenerRule {
  // If fixedResponse is provided, use it; otherwise use forward action
  const actions: aws.types.input.lb.ListenerRuleAction[] = args.fixedResponse
    ? [
        {
          type: "fixed-response",
          fixedResponse: {
            contentType: args.fixedResponse.contentType,
            messageBody: args.fixedResponse.messageBody,
            statusCode: args.fixedResponse.statusCode,
          },
        },
      ]
    : [
        {
          type: "forward",
          targetGroupArn: args.targetGroupArn!,
        },
      ];

  return new aws.lb.ListenerRule(args.name, {
    listenerArn: args.listenerArn,
    priority: args.priority,
    conditions: args.conditions,
    actions,
  });
}

/**
 * Create a weighted listener rule for multi-target routing
 * Used for dual Python/Rust implementations
 */
export function createWeightedListenerRule(args: {
  name: string;
  listenerArn: pulumi.Output<string>;
  priority: number;
  targetGroups: Array<{
    arn: pulumi.Output<string>;
    weight: number;
  }>;
  conditions: aws.types.input.lb.ListenerRuleCondition[];
  stickinessEnabled?: boolean;
  stickinessDuration?: number;
}): aws.lb.ListenerRule {
  return new aws.lb.ListenerRule(args.name, {
    listenerArn: args.listenerArn,
    priority: args.priority,
    conditions: args.conditions,
    actions: [
      {
        type: "forward",
        forward: {
          targetGroups: args.targetGroups.map((tg) => ({
            arn: tg.arn,
            weight: tg.weight,
          })),
          stickiness: {
            enabled: args.stickinessEnabled !== false,
            duration: args.stickinessDuration || 3600, // 1 hour default
          },
        },
      },
    ],
  });
}

/**
 * Get routing percentages based on environment
 *
 * Can be overridden via environment variables:
 *   RUST_ROUTING_PERCENT_PRODUCTION=50
 *   RUST_ROUTING_PERCENT_STAGING=100
 *   RUST_ROUTING_PERCENT_REVIEW=100
 *
 * Values should be integers 0-100 representing the percentage of traffic to route to Rust.
 */
export function getRoutingPercentages(stack: string): { rust: number; python: number } {
  // Default Rust percentages per environment (Python = 100 - rust)
  const defaultPercentages: { [key: string]: number } = {
    staging: 100, // 100% to Rust in staging
    review: 100, // 100% to Rust in review
    production: 0, // 0% to Rust in production (safe default)
  };

  // Check for environment variable override
  const envVarName = `RUST_ROUTING_PERCENT_${stack.toUpperCase()}`;
  const envValue = process.env[envVarName];

  let rustPercentage: number;
  if (envValue !== undefined) {
    const parsed = parseInt(envValue, 10);
    if (isNaN(parsed) || parsed < 0 || parsed > 100) {
      console.warn(`Invalid value for ${envVarName}: "${envValue}". Must be integer 0-100. Using default.`);
      rustPercentage = defaultPercentages[stack] ?? 0;
    } else {
      rustPercentage = parsed;
    }
  } else {
    rustPercentage = defaultPercentages[stack] ?? 0; // Default to 0% Rust for unknown envs
  }

  return {
    rust: rustPercentage,
    python: 100 - rustPercentage,
  };
}

/**
 * Helper to create path pattern conditions
 */
export function pathCondition(pattern: string): aws.types.input.lb.ListenerRuleCondition {
  return {
    pathPattern: {
      values: [pattern],
    },
  };
}

/**
 * Helper to create HTTP method conditions
 */
export function methodCondition(...methods: string[]): aws.types.input.lb.ListenerRuleCondition {
  return {
    httpRequestMethod: {
      values: methods,
    },
  };
}

/**
 * Helper to create host header conditions
 */
export function hostCondition(host: string): aws.types.input.lb.ListenerRuleCondition {
  return {
    hostHeader: {
      values: [host],
    },
  };
}

/**
 * Create CloudWatch alarms for a target group
 * Matches the alarm creation logic from buildHttpLambdaFn in new_service.ts
 */
export function createTargetGroupAlarms(args: {
  name: string;
  targetGroup: aws.lb.TargetGroup;
  alb: aws.lb.LoadBalancer;
  alertTopic: aws.sns.Topic;
  alarmConfigurations: AlarmConfigurations;
}): void {
  const metricNamespace = "AWS/ApplicationELB";

  // Get alarm configuration for this specific target group or use default
  const alarmConfig =
    (args.alarmConfigurations as any as Record<string, TargetGroupAlarmsConfiguration>)[args.name] ||
    args.alarmConfigurations.default;

  // 5XX error alarms
  [
    {
      name: `HTTP-Target-5XX-${args.name}-burst`,
      ...alarmConfig.percentHTTPCodeTarget5XX.burst,
    },
    {
      name: `HTTP-Target-5XX-${args.name}-sustain`,
      ...alarmConfig.percentHTTPCodeTarget5XX.sustain,
    },
  ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
    new aws.cloudwatch.MetricAlarm(name, {
      tags: { ...defaultTags, Name: name },
      name,
      alarmActions: [args.alertTopic.arn],
      okActions: [args.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm,
      evaluationPeriods,
      metricQueries: [
        {
          id: "m1",
          metric: {
            metricName: "RequestCount",
            dimensions: {
              LoadBalancer: args.alb.arnSuffix,
              TargetGroup: args.targetGroup.arnSuffix,
            },
            namespace: metricNamespace,
            period,
            stat: "Sum",
          },
          returnData: false,
        },
        {
          id: "m2",
          metric: {
            metricName: "HTTPCode_Target_5XX_Count",
            dimensions: {
              LoadBalancer: args.alb.arnSuffix,
              TargetGroup: args.targetGroup.arnSuffix,
            },
            namespace: metricNamespace,
            period,
            stat: "Sum",
          },
          returnData: false,
        },
        {
          expression: "m2 / m1",
          id: "e1",
          label: "Percent of target 5XX errors",
          returnData: true,
        },
      ],
      threshold,
      treatMissingData: "missing",
    });
  });

  // 4XX error alarms
  [
    {
      name: `HTTP-Target-4XX-${args.name}-burst`,
      ...alarmConfig.percentHTTPCodeTarget4XX.burst,
    },
    {
      name: `HTTP-Target-4XX-${args.name}-sustain`,
      ...alarmConfig.percentHTTPCodeTarget4XX.sustain,
    },
  ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
    new aws.cloudwatch.MetricAlarm(name, {
      tags: { ...defaultTags, Name: name },
      name,
      alarmActions: [args.alertTopic.arn],
      okActions: [args.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm,
      evaluationPeriods,
      metricQueries: [
        {
          id: "m1",
          metric: {
            metricName: "RequestCount",
            dimensions: {
              LoadBalancer: args.alb.arnSuffix,
              TargetGroup: args.targetGroup.arnSuffix,
            },
            namespace: metricNamespace,
            period,
            stat: "Sum",
          },
          returnData: false,
        },
        {
          id: "m2",
          metric: {
            metricName: "HTTPCode_Target_4XX_Count",
            dimensions: {
              LoadBalancer: args.alb.arnSuffix,
              TargetGroup: args.targetGroup.arnSuffix,
            },
            namespace: metricNamespace,
            period,
            stat: "Sum",
          },
          returnData: false,
        },
        {
          expression: "m2 / m1",
          id: "e1",
          label: "Percent of target 4XX errors",
          returnData: true,
        },
      ],
      threshold,
      treatMissingData: "missing",
    });
  });

  // Response time alarms
  [
    {
      name: `TargetResponseTime-${args.name}-burst`,
      ...alarmConfig.targetResponseTime.burst,
    },
    {
      name: `TargetResponseTime-${args.name}-sustain`,
      ...alarmConfig.targetResponseTime.sustain,
    },
  ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
    new aws.cloudwatch.MetricAlarm(name, {
      tags: { ...defaultTags, Name: name },
      name,
      alarmActions: [args.alertTopic.arn],
      okActions: [args.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm,
      evaluationPeriods,
      dimensions: {
        LoadBalancer: args.alb.arnSuffix,
        TargetGroup: args.targetGroup.arnSuffix,
      },
      metricName: "TargetResponseTime",
      namespace: metricNamespace,
      period,
      statistic: "Average",
      treatMissingData: "notBreaching",
      threshold,
      unit: "Seconds",
    });
  });
}
