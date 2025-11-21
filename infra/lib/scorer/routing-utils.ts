import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { AlarmConfigurations, TargetGroupAlarmsConfiguration } from "./loadBalancer";
import { defaultTags } from "../tags";

/**
 * Helper function to create a Lambda function without any ALB integration
 * This is the "pure" Lambda creation, extracted from buildHttpLambdaFn
 */
export function createLambdaFunction(args: {
  name: string;
  dockerImage: pulumi.Input<string>;
  dockerCommand?: pulumi.Input<string[]>;
  environment?: pulumi.Input<{ [key: string]: pulumi.Input<string> }>;
  memorySize?: number;
  timeout?: number;
  roleArn: pulumi.Input<string>;
  securityGroupIds: pulumi.Input<string>[];
  subnetIds: pulumi.Input<string[]> | pulumi.Output<any>;  // Accept both formats
  architectures?: string[];
  ephemeralStorageSize?: number;
  tracingConfig?: aws.types.input.lambda.FunctionTracingConfig;
}): aws.lambda.Function {
  return new aws.lambda.Function(args.name, {
    packageType: "Image",
    imageUri: args.dockerImage,
    imageConfig: args.dockerCommand ? { commands: args.dockerCommand } : undefined,
    role: args.roleArn,
    timeout: args.timeout || 60,
    memorySize: args.memorySize || 512,
    architectures: args.architectures || ["x86_64"],
    environment: args.environment ? { variables: args.environment } : undefined,
    vpcConfig: {
      securityGroupIds: args.securityGroupIds,
      subnetIds: args.subnetIds,
    },
    ephemeralStorage: args.ephemeralStorageSize
      ? { size: args.ephemeralStorageSize }
      : undefined,
    tracingConfig: args.tracingConfig,
    publish: false,
  });
}

/**
 * Create a target group for a Lambda function and attach it
 * This handles the permission grant and attachment
 */
export function createLambdaTargetGroup(args: {
  name: string;
  lambda: aws.lambda.Function;
  vpcId: pulumi.Input<string>;
  healthCheck?: {
    enabled: boolean;
    path?: string;
    matcher?: string;
    interval?: number;
    timeout?: number;
  };
}): aws.lb.TargetGroup {
  // Create the target group
  const targetGroup = new aws.lb.TargetGroup(`${args.name}-tg`, {
    targetType: "lambda",
    vpcId: args.vpcId,
    healthCheck: args.healthCheck || {
      enabled: true,
      path: "/health",
      matcher: "200",
      interval: 30,
      timeout: 5,
    },
  });

  // Grant permission for ALB to invoke the Lambda
  const permission = new aws.lambda.Permission(`${args.name}-permission`, {
    action: "lambda:InvokeFunction",
    function: args.lambda.arn,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: targetGroup.arn,
  });

  // Attach the Lambda to the target group
  const attachment = new aws.lb.TargetGroupAttachment(`${args.name}-attachment`, {
    targetGroupArn: targetGroup.arn,
    targetId: args.lambda.arn,
  }, { dependsOn: [permission] });

  return targetGroup;
}

/**
 * Create a simple listener rule for single-target routing
 * Used for Python-only endpoints
 */
export function createListenerRule(args: {
  name: string;
  listenerArn: pulumi.Output<string>;
  priority: number;
  targetGroupArn: pulumi.Output<string>;
  conditions: aws.types.input.lb.ListenerRuleCondition[];
}): aws.lb.ListenerRule {
  return new aws.lb.ListenerRule(args.name, {
    listenerArn: args.listenerArn,
    priority: args.priority,
    conditions: args.conditions,
    actions: [
      {
        type: "forward",
        targetGroupArn: args.targetGroupArn,
      },
    ],
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
 */
export function getRoutingPercentages(stack: string): { rust: number; python: number } {
  // Match the logic from rust-scorer.ts
  if (stack === "staging" || stack === "review") {
    return { rust: 100, python: 0 };
  }
  // Production and all other environments default to Python-only for safety
  return { rust: 0, python: 100 };
}

/**
 * Check if Rust is enabled for the current stack
 */
export function isRustEnabled(stack: string): boolean {
  const percentages = getRoutingPercentages(stack);
  return percentages.rust > 0;
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