import { LogGroup } from "@pulumi/aws/cloudwatch/logGroup";
import { Role } from "@pulumi/aws/iam/role";
import { Input, Output, interpolate } from "@pulumi/pulumi";
import { TargetGroup, ListenerRule } from "@pulumi/aws/lb";
import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

import { Cluster } from "@pulumi/aws/ecs";
import { Topic } from "@pulumi/aws/sns";
import { Listener } from "@pulumi/aws/alb";
import { SecurityGroup } from "@pulumi/aws/ec2";
import { RolePolicyAttachment } from "@pulumi/aws/iam";
import { secretsManager } from "infra-libs";
import { AlarmConfigurations, TargetGroupAlarmsConfiguration } from "./loadBalancer";

import { defaultTags, stack } from "../tags";

export type ScorerService = {
  dockerImageScorer: Input<string>;
  securityGroup: aws.ec2.SecurityGroup;
  executionRole: Role;
  taskRole: Role;
  cluster: Cluster;
  logGroup: LogGroup;
  subnets: Input<Input<string>[]>;
  httpListenerArn: Input<string>;
  httpListenerRulePaths?: Input<Input<aws.types.input.lb.ListenerRuleCondition>[]>;
  listenerRulePriority?: Input<number>;
  targetGroup: TargetGroup;
  autoScaleMaxCapacity?: number;
  autoScaleMinCapacity?: number;
  alb: aws.lb.LoadBalancer;
  alertTopic: Topic;
  cpu?: number;
  memory?: number;
  desiredCount?: number;
};

export function createTargetGroup(name: string, vpcId: Input<string>): TargetGroup {
  return new TargetGroup(name, {
    tags: {
      ...defaultTags,
      Name: name,
    },
    port: 80,
    protocol: "HTTP",
    vpcId: vpcId,
    targetType: "ip",
    healthCheck: { path: "/health/", unhealthyThreshold: 5 },
  });
}

export function createScorerECSService({
  name,
  config,
  environment,
  secrets,
  loadBalancerAlarmThresholds,
}: {
  name: string;
  config: ScorerService;
  environment: secretsManager.EnvironmentVar[];
  secrets: pulumi.Output<secretsManager.SecretRef[]>;
  loadBalancerAlarmThresholds: AlarmConfigurations;
}): aws.ecs.Service | undefined {
  //////////////////////////////////////////////////////////////
  // Create target group and load balancer rules
  //////////////////////////////////////////////////////////////

  if (config.httpListenerRulePaths) {
    const targetPassportRule = new ListenerRule(`lrule-${name}`, {
      tags: { ...defaultTags, Name: name },
      listenerArn: config.httpListenerArn,
      priority: config.listenerRulePriority,
      actions: [
        {
          type: "forward",
          targetGroupArn: config.targetGroup.arn,
        },
      ],
      conditions: config.httpListenerRulePaths,
    });
  }

  //////////////////////////////////////////////////////////////
  // Create the task definition and the service
  //////////////////////////////////////////////////////////////

  const containerDefinitions = pulumi
    .all([config.dockerImageScorer, secrets, environment, config.logGroup.name, aws.config.region])
    .apply(([scorerImage, secrets, environment, logGroupName, logGroupRegion]) => {
      return JSON.stringify([
        {
          name: "scorer",
          image: scorerImage,
          memory: config.memory ? config.memory : 4096,
          cpu: config.cpu ? config.cpu : 4096,
          portMappings: [{ containerPort: 80, hostPort: 80, protocol: "tcp" }],
          command: [
            "gunicorn",
            "-w",
            "4",
            "-k",
            "uvicorn.workers.UvicornWorker",
            "scorer.asgi:application",
            "-b",
            "0.0.0.0:80",
          ],
          linuxParameters: {
            initProcessEnabled: true,
          },
          environment,
          secrets,
          logConfiguration: {
            logDriver: "awslogs",
            options: {
              "awslogs-group": logGroupName,
              "awslogs-region": logGroupRegion,
              "awslogs-stream-prefix": name,
            },
          },
        },
      ]);
    });

  const taskDefinition = new aws.ecs.TaskDefinition(name, {
    family: name,
    cpu: String(config.cpu ? config.cpu : 4096),
    memory: String(config.memory ? config.memory : 4096),
    networkMode: "awsvpc",
    requiresCompatibilities: ["FARGATE"],
    executionRoleArn: config.executionRole.arn,
    taskRoleArn: config.taskRole.arn,
    containerDefinitions,
    tags: { ...defaultTags, Name: name },
  });

  const service = new aws.ecs.Service(
    name,
    {
      name: name,
      cluster: config.cluster.arn,
      taskDefinition: taskDefinition.arn,
      desiredCount: config.desiredCount ? config.desiredCount : 1,
      launchType: "FARGATE",
      propagateTags: "TASK_DEFINITION",
      networkConfiguration: {
        subnets: config.subnets,
        securityGroups: [config.securityGroup.id],
        assignPublicIp: false,
      },
      loadBalancers: [
        {
          targetGroupArn: config.targetGroup.arn,
          containerName: "scorer",
          containerPort: 80,
        },
      ],
      tags: { ...defaultTags, Name: name },
    },
    {
      ignoreChanges: ["desiredCount"],
    }
  );

  function getAutoScaleMinCapacity() {
    return config.autoScaleMinCapacity ? config.autoScaleMinCapacity : 2;
  }

  function getAutoScaleMaxCapacity() {
    return config.autoScaleMaxCapacity ? config.autoScaleMaxCapacity : 20;
  }

  const ecsScorerServiceAutoscalingTarget = new aws.appautoscaling.Target(`autoscale-target-${name}`, {
    tags: { ...defaultTags, Name: name },
    maxCapacity: getAutoScaleMaxCapacity(),
    minCapacity: getAutoScaleMinCapacity(),
    resourceId: interpolate`service/${config.cluster.name}/${service.name}`,
    scalableDimension: "ecs:service:DesiredCount",
    serviceNamespace: "ecs",
  });

  const ecsScorerServiceAutoscaling = new aws.appautoscaling.Policy(`autoscale-policy-${name}`, {
    policyType: "TargetTrackingScaling",
    resourceId: ecsScorerServiceAutoscalingTarget.resourceId,
    scalableDimension: ecsScorerServiceAutoscalingTarget.scalableDimension,
    serviceNamespace: ecsScorerServiceAutoscalingTarget.serviceNamespace,
    targetTrackingScalingPolicyConfiguration: {
      predefinedMetricSpecification: {
        predefinedMetricType: "ECSServiceAverageCPUUtilization",
      },
      targetValue: 50,
      scaleInCooldown: 300,
      scaleOutCooldown: 300,
    },
  });

  if (config.alertTopic) {
    // We want an alarm when the number of running tasks reaches 75% of the configured maximum
    const runningTaskCountAlarm = new aws.cloudwatch.MetricAlarm(`RunningTaskCount-${name}`, {
      tags: { ...defaultTags, Name: `RunningTaskCount-${name}` },
      alarmActions: [config.alertTopic.arn],
      okActions: [config.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      dimensions: {
        ClusterName: config.cluster.name,
        ServiceName: service.name,
      },
      evaluationPeriods: 1,
      metricName: "RunningTaskCount",
      name: `RunningTaskCount-${name}`,
      namespace: "ECS/ContainerInsights",
      period: 300,
      statistic: "Average",
      threshold: getAutoScaleMaxCapacity() * 0.75,
    });

    // High memory consumption might indicate an issue with the provisioned memory size, and
    // we should probably increase the size of allocated memory
    const memoryAlarm = new aws.cloudwatch.MetricAlarm(`MemoryUtilization-${name}`, {
      tags: { ...defaultTags, Name: `MemoryUtilization-${name}` },
      alarmActions: [config.alertTopic.arn],
      okActions: [config.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      dimensions: {
        ClusterName: config.cluster.name,
        ServiceName: service.name,
      },
      evaluationPeriods: 1,
      metricName: "MemoryUtilization",
      name: `MemoryUtilization-${name}`,
      namespace: "AWS/ECS",
      period: 900,
      statistic: "Average",
      threshold: 80,
    });

    // We want alarm to monitor:
    // - 5xx errors in individual targets
    // - 4xx errors in individual targets
    // - 5xx errors in elb
    // - 4xx errors in elb
    // - target response time

    const metricNamespace = "AWS/ApplicationELB";
    /*
     * Alarm for monitoring target 5XX errors
     */
    const alarmConfig =
      (loadBalancerAlarmThresholds as any as Record<string, TargetGroupAlarmsConfiguration>)[name] ||
      loadBalancerAlarmThresholds.default;

    [
      {
        name: `HTTP-Target-5XX-${name}-burst`,
        ...alarmConfig.percentHTTPCodeTarget5XX.burst,
      },
      {
        name: `HTTP-Target-5XX-${name}-sustain`,
        ...alarmConfig.percentHTTPCodeTarget5XX.sustain,
      },
    ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
      new aws.cloudwatch.MetricAlarm(name, {
        tags: { ...defaultTags, Name: name },
        name,
        alarmActions: [config.alertTopic.arn],
        okActions: [config.alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm,
        evaluationPeriods,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: config.alb.arnSuffix,
                TargetGroup: config.targetGroup.arnSuffix,
              },
              namespace: metricNamespace,
              period,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_5XX_Count",
              dimensions: {
                LoadBalancer: config.alb.arnSuffix,
                TargetGroup: config.targetGroup.arnSuffix,
              },
              namespace: metricNamespace,
              period,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 5XX errors",
            returnData: true,
          },
        ],
        threshold,
      });
    });

    /*
     * Alarm for monitoring target 4XX errors
     */
    [
      {
        name: `HTTP-Target-4XX-${name}-burst`,
        ...alarmConfig.percentHTTPCodeTarget4XX.burst,
      },
      {
        name: `HTTP-Target-4XX-${name}-sustain`,
        ...alarmConfig.percentHTTPCodeTarget4XX.sustain,
      },
    ].forEach(
      ({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) =>
        new aws.cloudwatch.MetricAlarm(name, {
          tags: { ...defaultTags, Name: name },
          name,
          alarmActions: [config.alertTopic.arn],
          okActions: [config.alertTopic.arn],
          comparisonOperator: "GreaterThanThreshold",
          /*
           * We want to monitor the 4xx errors for 10 periods of 1 minute
           * and trigger the alarm if 8 / 10 of those periods the threshold was crossed
           */
          datapointsToAlarm,
          evaluationPeriods,
          metricQueries: [
            {
              id: "m1",
              metric: {
                metricName: "RequestCount",
                dimensions: {
                  LoadBalancer: config.alb.arnSuffix,
                  TargetGroup: config.targetGroup.arnSuffix,
                },
                namespace: metricNamespace,
                period,
                stat: "Sum",
              },
            },
            {
              id: "m2",
              metric: {
                metricName: "HTTPCode_Target_4XX_Count",
                dimensions: {
                  LoadBalancer: config.alb.arnSuffix,
                  TargetGroup: config.targetGroup.arnSuffix,
                },
                namespace: metricNamespace,
                period,
                stat: "Sum",
              },
            },
            {
              expression: "m2 / m1",
              id: "e1",
              label: "Percent of target 4XX errors",
              returnData: true,
            },
          ],
          threshold,
        })
    );

    // We want an alarm to monitor for the average response time
    [
      {
        name: `TargetResponseTime-${name}-burst`,
        ...alarmConfig.targetResponseTime.burst,
      },
      {
        name: `TargetResponseTime-${name}-sustain`,
        ...alarmConfig.targetResponseTime.sustain,
      },
    ].forEach(
      ({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) =>
        new aws.cloudwatch.MetricAlarm(name, {
          tags: { ...defaultTags, Name: `TargetResponseTime-${name}` },
          alarmActions: [config.alertTopic.arn],
          okActions: [config.alertTopic.arn],
          comparisonOperator: "GreaterThanThreshold",
          datapointsToAlarm,
          evaluationPeriods,
          dimensions: {
            LoadBalancer: config.alb.arnSuffix,
            TargetGroup: config.targetGroup.arnSuffix,
          },
          metricName: "TargetResponseTime",
          name,
          namespace: "AWS/ApplicationELB",
          period,
          statistic: "Average",
          treatMissingData: "notBreaching",
          threshold,
          unit: "Seconds",
        })
    );
  }

  return service;
}

type IndexerServiceParams = {
  cluster: Cluster;
  privateSubnetIds: Output<any>;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  workerRole: Role;
  alertTopic: aws.sns.Topic;
  secretReferences: pulumi.Output<secretsManager.SecretRef[]>;
  environment: secretsManager.EnvironmentVar[];
  indexerImage: Input<string>;
};

export function createIndexerService(
  {
    cluster,
    privateSubnetIds,
    privateSubnetSecurityGroup,
    workerRole,
    alertTopic,
    secretReferences,
    environment,
    indexerImage,
  }: IndexerServiceParams,
  alarmThresholds: AlarmConfigurations
) {
  const indexerLogGroup = new aws.cloudwatch.LogGroup("scorer-indexer", {
    retentionInDays: stack === "production" ? 90 : 7,
    tags: { ...defaultTags, Name: "scorer-indexer" },
  });

  const containerDefinitions = pulumi
    .all([indexerImage, secretReferences, environment, indexerLogGroup.name, aws.config.region])
    .apply(([indexerImage, secrets, environment, logGroupName, region]) => {
      return JSON.stringify([
        {
          name: "indexer-process-1",
          memory: 1024,
          cpu: 512,
          image: indexerImage,
          portMappings: [],
          secrets,
          environment,
          logConfiguration: {
            logDriver: "awslogs",
            options: {
              "awslogs-group": logGroupName,
              "awslogs-region": region,
              "awslogs-stream-prefix": "scorer-staking-indexer-1",
            },
          },
        },
      ]);
    });

  const taskDefinition = new aws.ecs.TaskDefinition("scorer-staking-indexer-1", {
    family: "scorer-staking-indexer-1",
    cpu: "512",
    memory: "1024",
    networkMode: "awsvpc",
    requiresCompatibilities: ["FARGATE"],
    executionRoleArn: workerRole.arn,
    containerDefinitions,
    tags: { ...defaultTags, Name: "scorer-staking-indexer-1" },
  });

  const service = new aws.ecs.Service("scorer-staking-indexer-1", {
    name: "scorer-staking-indexer-1",
    cluster: cluster.arn,
    taskDefinition: taskDefinition.arn,
    desiredCount: 1,
    launchType: "FARGATE",
    propagateTags: "TASK_DEFINITION",
    networkConfiguration: {
      subnets: privateSubnetIds,
      securityGroups: [privateSubnetSecurityGroup.id],
      assignPublicIp: false,
    },
    tags: { ...defaultTags, Name: "scorer-staking-indexer" },
  });

  const indexerErrorsMetric = new aws.cloudwatch.LogMetricFilter("indexerErrorsMetric", {
    logGroupName: indexerLogGroup.name,
    metricTransformation: {
      defaultValue: "0",
      name: "indexerError",
      namespace: "/scorer/indexer",
      unit: "Count",
      value: "1",
    },
    name: "Indexer Errors",
    pattern: '"Error - Failed"',
  });

  const indexerErrorsAlarm = new aws.cloudwatch.MetricAlarm("indexerErrorsAlarm", {
    alarmActions: [alertTopic.arn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    datapointsToAlarm: 1,
    evaluationPeriods: 1,
    insufficientDataActions: [],
    metricName: "indexerError",
    name: "Indexer Errors",
    namespace: "/scorer/indexer",
    okActions: [],
    period: alarmThresholds.indexerErrorPeriod,
    statistic: "Sum",
    threshold: alarmThresholds.indexerErrorThreshold,
    treatMissingData: "notBreaching",
    tags: { ...defaultTags, Name: "indexerErrorsAlarm" },
  });
}

export const createSharedLambdaResources = ({ rescoreQueue }: { rescoreQueue: aws.sqs.Queue }) => {
  const lambdaLoggingPolicyDocument = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        actions: ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        resources: ["arn:aws:logs:*:*:*"],
      },
    ],
  });

  const lambdaEc2PolicyDocument = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        actions: [
          "ec2:DescribeNetworkInterfaces",
          "ec2:CreateNetworkInterface",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeInstances",
          "ec2:AttachNetworkInterface",
        ],
        resources: ["*"],
      },
    ],
  });

  const lambdaSecretsManagerPolicyDocument = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        actions: ["secretsmanager:GetSecretValue"],
        resources: ["arn:aws:secretsmanager:*:*:*"],
      },
    ],
  });

  const lambdaLoggingPolicy = new aws.iam.Policy("lambdaLoggingPolicy", {
    path: "/",
    description: "IAM policy for logging from a lambda",
    policy: lambdaLoggingPolicyDocument.then((lambdaLoggingPolicyDocument) => lambdaLoggingPolicyDocument.json),
    tags: { ...defaultTags, Name: "lambdaLoggingPolicy" },
  });

  const lambdaEc2Policy = new aws.iam.Policy("lambdaEc2Policy", {
    path: "/",
    description: "IAM policy for interfacing with EC2 network",
    policy: lambdaEc2PolicyDocument.then((lambdaEc2PolicyDocument) => lambdaEc2PolicyDocument.json),
    tags: { ...defaultTags, Name: "lambdaEc2Policy" },
  });

  const lambdaSecretsManagerPolicy = new aws.iam.Policy("lambdaSecretManagerPolicy", {
    path: "/",
    description: "IAM policy for interfacing with SecretManager network",
    policy: lambdaSecretsManagerPolicyDocument.then(
      (lambdaSecretsManagerPolicyDocument) => lambdaSecretsManagerPolicyDocument.json
    ),
    tags: { ...defaultTags, Name: "lambdaSecretManagerPolicy" },
  });

  const assumeRole = aws.iam.getPolicyDocument({
    statements: [
      {
        effect: "Allow",
        principals: [
          {
            type: "Service",
            identifiers: ["lambda.amazonaws.com"],
          },
        ],
        actions: ["sts:AssumeRole"],
      },
    ],
  });

  const httpLambdaRole = new aws.iam.Role("lambdaRole", {
    assumeRolePolicy: assumeRole.then((assumeRole) => assumeRole.json),
    tags: { ...defaultTags, Name: "lambdaRole" },
  });

  const lambdaLogRoleAttachment = new aws.iam.RolePolicyAttachment("lambdaLogRoleAttachment", {
    role: httpLambdaRole.name,
    policyArn: lambdaLoggingPolicy.arn,
  });

  const lambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment("lambdaEc2RoleAttachment", {
    role: httpLambdaRole.name,
    policyArn: lambdaEc2Policy.arn,
  });

  const lambdaSecretsManagerRoleAttachment = new aws.iam.RolePolicyAttachment("lambdaSecretManagerRoleAttachment", {
    role: httpLambdaRole.name,
    policyArn: lambdaSecretsManagerPolicy.arn,
  });

  const queueLambdaRole = new aws.iam.Role("queueLambdaRole", {
    assumeRolePolicy: assumeRole.then((assumeRole) => assumeRole.json),
    tags: { ...defaultTags, Name: "queueLambdaRole" },
  });

  const readSqsPolicyDocument = rescoreQueue.arn.apply((rescoreQueueArn) =>
    aws.iam.getPolicyDocument({
      statements: [
        {
          effect: "Allow",
          actions: ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"],
          resources: [rescoreQueueArn],
        },
      ],
    })
  );

  const readSqsPolicy = new aws.iam.Policy("readSqsPolicy", {
    path: "/",
    description: "IAM policy for reading from SQS",
    policy: readSqsPolicyDocument.apply((readSqsPolicyDocument) => readSqsPolicyDocument.json),
    tags: { ...defaultTags, Name: "readSqsPolicy" },
  });

  const queueLambdaSqsRoleAttachment = new aws.iam.RolePolicyAttachment("queueLambdaSqsRoleAttachment", {
    role: queueLambdaRole.name,
    policyArn: readSqsPolicy.arn,
  });

  const queueLambdaLogRoleAttachment = new aws.iam.RolePolicyAttachment("queueLambdaLogRoleAttachment", {
    role: queueLambdaRole.name,
    policyArn: lambdaLoggingPolicy.arn,
  });

  const queueLambdaEc2RoleAttachment = new aws.iam.RolePolicyAttachment("queueLambdaEc2RoleAttachment", {
    role: queueLambdaRole.name,
    policyArn: lambdaEc2Policy.arn,
  });

  const queueLambdaSecretsManagerRoleAttachment = new aws.iam.RolePolicyAttachment(
    "queueLambdaSecretManagerRoleAttachment",
    {
      role: queueLambdaRole.name,
      policyArn: lambdaSecretsManagerPolicy.arn,
    }
  );

  return {
    httpLambdaRole,
    httpRoleAttachments: [lambdaLogRoleAttachment, lambdaEc2RoleAttachment, lambdaSecretsManagerRoleAttachment],
    queueLambdaRole,
    queueRoleAttachments: [
      queueLambdaLogRoleAttachment,
      queueLambdaSqsRoleAttachment,
      queueLambdaSecretsManagerRoleAttachment,
      queueLambdaEc2RoleAttachment,
    ],
  };
};

type BuildLambdaFnBaseParams = {
  name: string;
  imageUri: Input<string>;
  privateSubnetSecurityGroup: SecurityGroup;
  vpcPrivateSubnetIds: Output<any>;
  environment: { name: string; value: Input<string> }[];
  role: Role;
  roleAttachments: RolePolicyAttachment[];
  memorySize: number;
  dockerCmd: string[];
  alertTopic?: Topic;
  timeout?: number;
  alb: aws.lb.LoadBalancer;
};

export function buildHttpLambdaFn(
  args: BuildLambdaFnBaseParams & {
    httpsListener: Output<Listener>;
    listenerPriority: number;
    httpListenerRulePaths?: Input<Input<aws.types.input.lb.ListenerRuleCondition>[]>;
  },
  loadBalancerAlarmThresholds: AlarmConfigurations
) {
  const lambdaFunction = buildLambdaFn(args);

  const { httpsListener, listenerPriority, httpListenerRulePaths, name, alertTopic, alb } = args;

  const lambdaTargetGroup = new aws.lb.TargetGroup(`l-${name}`, {
    name: `l-${name}`,
    targetType: "lambda",
    tags: { ...defaultTags, Name: `l-${name}` },
  });

  const withLb = new aws.lambda.Permission(`withLb-${name}`, {
    action: "lambda:InvokeFunction",
    function: lambdaFunction.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: lambdaTargetGroup.arn,
  });

  const lambdaTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    `lambdaTargetGroupAttachment-${name}`,
    {
      targetGroupArn: lambdaTargetGroup.arn,
      targetId: lambdaFunction.arn,
    },
    {
      dependsOn: [withLb],
    }
  );

  const targetPassportRule = new ListenerRule(`lrule-lambda-${name}`, {
    tags: { ...defaultTags, Name: `lrule-lambda-${name}` },
    listenerArn: httpsListener.arn,
    priority: listenerPriority,
    actions: [
      {
        type: "forward",
        targetGroupArn: lambdaTargetGroup.arn,
      },
    ],
    conditions: httpListenerRulePaths || [],
  });

  if (alertTopic) {
    // We want alarm to monitor:
    // - 5xx errors in individual targets
    // - 4xx errors in individual targets
    // - 5xx errors in elb
    // - 4xx errors in elb
    // - target response time

    const metricNamespace = "AWS/ApplicationELB";
    /*
     * Alarm for monitoring target 5XX errors
     */
    const alarmConfig =
      (loadBalancerAlarmThresholds as any as Record<string, TargetGroupAlarmsConfiguration>)[name] ||
      loadBalancerAlarmThresholds.default;

    [
      {
        name: `HTTP-Target-5XX-${name}-burst`,
        ...alarmConfig.percentHTTPCodeTarget5XX.burst,
      },
      {
        name: `HTTP-Target-5XX-${name}-sustain`,
        ...alarmConfig.percentHTTPCodeTarget5XX.sustain,
      },
    ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
      new aws.cloudwatch.MetricAlarm(name, {
        tags: { ...defaultTags, Name: name },
        name,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm,
        evaluationPeriods,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: alb.arnSuffix,
                TargetGroup: lambdaTargetGroup.arnSuffix,
              },
              namespace: metricNamespace,
              period,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_5XX_Count",
              dimensions: {
                LoadBalancer: alb.arnSuffix,
                TargetGroup: lambdaTargetGroup.arnSuffix,
              },
              namespace: metricNamespace,
              period,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 5XX errors",
            returnData: true,
          },
        ],
        threshold,
      });
    });

    /*
     * Alarm for monitoring target 4XX errors
     */
    [
      {
        name: `HTTP-Target-4XX-${name}-burst`,
        ...alarmConfig.percentHTTPCodeTarget4XX.burst,
      },
      {
        name: `HTTP-Target-4XX-${name}-sustain`,
        ...alarmConfig.percentHTTPCodeTarget4XX.sustain,
      },
    ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
      new aws.cloudwatch.MetricAlarm(name, {
        tags: { ...defaultTags, Name: name },
        name,
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm,
        evaluationPeriods,
        metricQueries: [
          {
            id: "m1",
            metric: {
              metricName: "RequestCount",
              dimensions: {
                LoadBalancer: alb.arnSuffix,
                TargetGroup: lambdaTargetGroup.arnSuffix,
              },
              namespace: metricNamespace,
              period,
              stat: "Sum",
            },
          },
          {
            id: "m2",
            metric: {
              metricName: "HTTPCode_Target_4XX_Count",
              dimensions: {
                LoadBalancer: alb.arnSuffix,
                TargetGroup: lambdaTargetGroup.arnSuffix,
              },
              namespace: metricNamespace,
              period,
              stat: "Sum",
            },
          },
          {
            expression: "m2 / m1",
            id: "e1",
            label: "Percent of target 4XX errors",
            returnData: true,
          },
        ],
        threshold,
      });
    });

    // We want an alarm to monitor for the average response time
    [
      {
        name: `TargetResponseTime-${name}-burst`,
        ...alarmConfig.targetResponseTime.burst,
      },
      {
        name: `TargetResponseTime-${name}-sustain`,
        ...alarmConfig.targetResponseTime.sustain,
      },
    ].forEach(({ name, threshold, datapointsToAlarm, evaluationPeriods, period }) => {
      new aws.cloudwatch.MetricAlarm(name, {
        tags: { ...defaultTags, Name: name },
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm,
        dimensions: {
          LoadBalancer: alb.arnSuffix,
          TargetGroup: lambdaTargetGroup.arnSuffix,
        },
        evaluationPeriods,
        metricName: "TargetResponseTime",
        name,
        namespace: metricNamespace,
        period,
        statistic: "Average",
        treatMissingData: "notBreaching",
        threshold,
        unit: "Seconds",
      });
    });
  }
}

export function buildQueueLambdaFn(
  args: BuildLambdaFnBaseParams & {
    queue: aws.sqs.Queue;
  }
) {
  const lambdaFunction = buildLambdaFn(args);

  const { queue, name } = args;

  const queueLambdaTrigger = new aws.lambda.EventSourceMapping(`queueLambdaTrigger-${name}`, {
    batchSize: 10,
    eventSourceArn: queue.arn,
    functionName: lambdaFunction.arn,
  });
}

function buildLambdaFn({
  name,
  imageUri,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  environment,
  role,
  roleAttachments,
  memorySize,
  dockerCmd,
  timeout ,
}: BuildLambdaFnBaseParams): aws.lambda.Function {
  const lambdaFunction = new aws.lambda.Function(
    name,
    {
      name: name,
      imageConfig: {
        commands: dockerCmd,
      },
      vpcConfig: {
        // vpcId: vpc.vpcId,
        securityGroupIds: [privateSubnetSecurityGroup.id], // TODO: shall we create it's own security group ???
        subnetIds: vpcPrivateSubnetIds,
      },
      packageType: "Image",
      role: role.arn,
      imageUri,
      timeout: timeout || 60,
      memorySize,
      environment: {
        variables: environment.reduce(
          (acc: { [key: string]: Input<string> }, e: { name: string; value: Input<string> }) => {
            acc[e.name] = e.value;
            return acc;
          },
          {}
        ),
      },
      tags: { ...defaultTags, Name: name },
    },
    {
      dependsOn: roleAttachments,
    }
  );

  return lambdaFunction;
}

export const createDeadLetterQueue = ({ alertTopic }: { alertTopic?: Topic }): aws.sqs.Queue => {
  const deadLetterQueue = new aws.sqs.Queue("scorer-dead-letter-queue", {
    tags: { ...defaultTags, Name: "scorer-dead-letter-queue" },
  });

  if (alertTopic) {
    const newMessageDeadLetterQueueAlarm = new aws.cloudwatch.MetricAlarm("newMessageDeadLetterQueueAlarm", {
      alarmActions: [alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      evaluationPeriods: 1,
      metricQueries: [
        {
          id: "m1",
          metric: {
            dimensions: {
              QueueName: deadLetterQueue.name,
            },
            metricName: "ApproximateNumberOfMessagesVisible",
            namespace: "AWS/SQS",
            period: 300,
            stat: "Maximum",
          },
        },
        {
          id: "m10",
          metric: {
            dimensions: {
              QueueName: deadLetterQueue.name,
            },
            metricName: "ApproximateNumberOfMessagesVisible",
            namespace: "AWS/SQS",
            period: 300,
            stat: "Minimum",
          },
        },
        {
          expression: "m1 - m10",
          id: "e1",
          label: "NumNewMessagesDeadLetterQueue",
          returnData: true,
        },
      ],
      name: "NewMessageDeadLetterQueueAlarm",
      treatMissingData: "notBreaching",
      tags: { ...defaultTags, Name: "NewMessageDeadLetterQueueAlarm" },
    });
  }

  return deadLetterQueue;
};

export const createRescoreQueue = ({ deadLetterQueue }: { deadLetterQueue: aws.sqs.Queue }): aws.sqs.Queue => {
  const fourHoursInSeconds = 60 * 60 * 4;

  return new aws.sqs.Queue("rescore-queue", {
    delaySeconds: 0,
    maxMessageSize: 2048,
    messageRetentionSeconds: 86400,
    receiveWaitTimeSeconds: 10,
    visibilityTimeoutSeconds: fourHoursInSeconds,
    redrivePolicy: deadLetterQueue.arn.apply((arn) =>
      JSON.stringify({
        deadLetterTargetArn: arn,
        maxReceiveCount: 4,
      })
    ),
    tags: { ...defaultTags, Name: "rescore-queue" },
  });
};
