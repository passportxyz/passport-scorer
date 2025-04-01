import { all, Input } from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { ScorerService } from "./new_service";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../tags";

export type ScheduledTaskConfig = Pick<
  ScorerService,
  "dockerImageScorer" | "executionRole" | "taskRole" | "cluster" | "subnets" | "securityGroup" | "cpu" | "memory"
> &
  Required<Pick<ScorerService, "alertTopic">> & {
    command: string;
    scheduleExpression: string;
    ephemeralStorageSizeInGiB?: number;
    scheduled?: boolean;
  };

export function createTask({
  name,
  config,
  environment,
  secrets,
  scorerSecretManagerArn,
}: {
  name: string;
  config: ScheduledTaskConfig;
  environment: secretsManager.EnvironmentVar[];
  secrets: pulumi.Output<secretsManager.SecretRef[]> | secretsManager.SecretRef[];
  scorerSecretManagerArn: Input<string>;
}) {
  const {
    alertTopic,
    executionRole,
    taskRole,
    subnets,
    dockerImageScorer,
    cluster,
    securityGroup,
    command,
    ephemeralStorageSizeInGiB,
    cpu,
    memory,
    scheduled,
  } = config;

  const commandSuccessMessage = `SUCCESS <${name}>`;
  const commandWithTest = ["/bin/bash", "-c", command + ` && echo "${commandSuccessMessage}"`];

  const logGroupName = `${scheduled ? "scheduled-" : ""}${name}`;

  const logGroup = new aws.cloudwatch.LogGroup(logGroupName, {
    retentionInDays: stack === "production" ? 90 : 7,
    tags: {
      ...defaultTags,
      Name: logGroupName,
    },
  });

  const containerName = `${name}-container`;

  const task = new aws.ecs.TaskDefinition(`${name}-1`, {
    family: `${name}-1`,
    cpu: (cpu ? cpu : 256).toString(),
    memory: (memory ? memory : 2048).toString(),
    networkMode: "awsvpc",
    requiresCompatibilities: ["FARGATE"],
    executionRoleArn: executionRole.arn,
    taskRoleArn: taskRole.arn,
    ephemeralStorage: ephemeralStorageSizeInGiB
      ? {
          sizeInGib: ephemeralStorageSizeInGiB,
        }
      : undefined,
    containerDefinitions: pulumi
      .all([environment, secrets, dockerImageScorer, logGroup.name, aws.config.region])
      .apply(([env, secs, image, logGroupName, logGroupRegion]) =>
        JSON.stringify([
          {
            name: containerName,
            image,
            cpu: cpu ? cpu : 256,
            memory: memory ? memory : 2048,
            command: commandWithTest,
            essential: true,
            environment: env.map((e) => ({
              name: e.name,
              value: e.value,
            })),
            secrets: secs.map((s) => ({
              name: s.name,
              valueFrom: s.valueFrom,
            })),
            logConfiguration: {
              logDriver: "awslogs",
              options: {
                "awslogs-group": logGroupName,
                "awslogs-region": logGroupRegion,
                "awslogs-stream-prefix": name,
              },
            },
          },
        ])
      ),
    tags: {
      ...defaultTags,
      Name: name,
    },
  });

  const eventsStsAssumeRole = new aws.iam.Role(`${name}-eventsRole`, {
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Action: "sts:AssumeRole",
          Effect: "Allow",
          Sid: "",
          Principal: {
            Service: "ecs-tasks.amazonaws.com",
          },
        },
        {
          Action: "sts:AssumeRole",
          Effect: "Allow",
          Sid: "",
          Principal: {
            Service: "events.amazonaws.com",
          },
        },
      ],
    }),
    inlinePolicies: [
      {
        name: "allow_exec",
        policy: JSON.stringify({
          Version: "2012-10-17",
          Statement: [
            {
              Effect: "Allow",
              Action: [
                "ssmmessages:CreateControlChannel",
                "ssmmessages:CreateDataChannel",
                "ssmmessages:OpenControlChannel",
                "ssmmessages:OpenDataChannel",
              ],
              Resource: "*",
            },
          ],
        }),
      },
      {
        name: "allow_iam_secrets_access",
        policy: all([scorerSecretManagerArn]).apply(([scorerSecretManagerArnStr]) =>
          JSON.stringify({
            Version: "2012-10-17",
            Statement: [
              {
                Action: ["secretsmanager:GetSecretValue"],
                Effect: "Allow",
                Resource: scorerSecretManagerArnStr,
              },
            ],
          })
        ),
      },
      {
        name: "allow_run_task",
        policy: task.arn.apply((Resource) =>
          JSON.stringify({
            Version: "2012-10-17",
            Statement: [
              {
                Action: ["ecs:RunTask"],
                Effect: "Allow",
                Resource: Resource,
              },
            ],
          })
        ),
      },
      {
        name: "allow_pass_role",
        policy: all([executionRole.arn, task.taskRoleArn]).apply(([dpoppEcsRoleArn, weeklyDataDumpTaskRoleArn]) =>
          JSON.stringify({
            Version: "2012-10-17",
            Statement: [
              {
                Action: ["iam:PassRole"],
                Effect: "Allow",
                Resource: [dpoppEcsRoleArn, weeklyDataDumpTaskRoleArn],
              },
            ],
          })
        ),
      },
    ],
    managedPolicyArns: ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"],
    tags: {
      ...defaultTags,
      Name: `${name}-eventsRole`,
    },
  });

  return {
    task,
    logGroup,
    eventsStsAssumeRole,
    cluster,
    securityGroup,
    subnets,
    alertTopic,
    commandSuccessMessage,
    containerName,
  };
}

export function createScheduledTask({
  name,
  config,
  environment,
  secrets,
  alarmPeriodSeconds,
  enableInvocationAlerts,
  scorerSecretManagerArn,
}: {
  name: string;
  config: ScheduledTaskConfig;
  environment: secretsManager.EnvironmentVar[];
  secrets: pulumi.Output<secretsManager.SecretRef[]> | secretsManager.SecretRef[];
  alarmPeriodSeconds?: number;
  enableInvocationAlerts?: boolean;
  scorerSecretManagerArn: Input<string>;
}) {
  const { scheduleExpression } = config;

  const taskResources = createTask({
    name,
    config: {
      ...config,
      scheduled: true,
    },
    environment,
    secrets,
    scorerSecretManagerArn,
  });

  const scheduledEventRule = new aws.cloudwatch.EventRule(`rule-${name}`, {
    scheduleExpression,
    tags: {
      ...defaultTags,
      Name: `rule-${name}`,
    },
  });

  new aws.cloudwatch.EventTarget(`scheduled-${name}`, {
    rule: scheduledEventRule.name,
    arn: taskResources.cluster.arn,
    roleArn: taskResources.eventsStsAssumeRole.arn,
    ecsTarget: {
      taskCount: 1,
      taskDefinitionArn: taskResources.task.arn,
      launchType: "FARGATE",
      networkConfiguration: {
        assignPublicIp: false,
        securityGroups: [taskResources.securityGroup.id],
        subnets: taskResources.subnets,
      },
    },
  });

  if (alarmPeriodSeconds) {
    if (enableInvocationAlerts) {
      // No invocation in the given period
      const missingInvocationsAlarm = new aws.cloudwatch.MetricAlarm(`MissingInvocations-${name}`, {
        alarmActions: [taskResources.alertTopic.arn],
        okActions: [taskResources.alertTopic.arn],
        comparisonOperator: "LessThanThreshold",
        datapointsToAlarm: 1,
        evaluationPeriods: 1,
        metricName: "Invocations",
        name: "MissingInvocations-" + name,
        namespace: "AWS/Events",
        dimensions: {
          RuleName: scheduledEventRule.name,
        },
        period: alarmPeriodSeconds,
        statistic: "Sum",
        threshold: 1,
        treatMissingData: "notBreaching",
        tags: {
          ...defaultTags,
          Name: `MissingInvocations-${name}`,
        },
      });
    }
    // Verify failed invocations
    const failedInvocationsAlarm = new aws.cloudwatch.MetricAlarm(`FailedInvocations-${name}`, {
      alarmActions: [taskResources.alertTopic.arn],
      okActions: [taskResources.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      evaluationPeriods: 1,
      metricName: "FailedInvocations",
      name: `FailedInvocations-${name}`,
      namespace: "AWS/Events",
      dimensions: {
        RuleName: scheduledEventRule.name,
      },
      period: alarmPeriodSeconds,
      statistic: "Sum",
      threshold: 0,
      treatMissingData: "notBreaching",
      tags: {
        ...defaultTags,
        Name: `FailedInvocations-${name}`,
      },
    });

    // Missing succes Message
    const successfulRunMetricNamespace = "/scheduled-tasks/runs/success";
    const successfulRunMetricName = `SuccessfulRun-${name}`;

    new aws.cloudwatch.LogMetricFilter(successfulRunMetricName, {
      logGroupName: taskResources.logGroup.name,
      metricTransformation: {
        defaultValue: "0",
        name: successfulRunMetricName,
        namespace: successfulRunMetricNamespace,
        unit: "Count",
        value: "1",
      },
      name: successfulRunMetricName,
      pattern: `"${taskResources.commandSuccessMessage}"`,
    });

    new aws.cloudwatch.MetricAlarm(`UnsuccessfulRuns-${name}`, {
      alarmActions: [taskResources.alertTopic.arn],
      okActions: [taskResources.alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      evaluationPeriods: 1,
      metricQueries: [
        {
          id: "m1",
          metric: {
            metricName: successfulRunMetricName,
            namespace: successfulRunMetricNamespace,
            period: alarmPeriodSeconds,
            stat: "Sum",
          },
        },
        {
          id: "m2",
          metric: {
            dimensions: {
              RuleName: scheduledEventRule.name,
            },
            metricName: "Invocations",
            namespace: "AWS/Events",
            period: alarmPeriodSeconds,
            stat: "Sum",
          },
        },
        {
          expression: "m2 - m1",
          id: "e1",
          label: "UnsuccessfulRuns",
          returnData: true,
        },
      ],
      threshold: 1,
      name: `UnsuccessfulRuns-${name}`,
      treatMissingData: "notBreaching",
      tags: {
        ...defaultTags,
        Name: `UnsuccessfulRuns-${name}`,
      },
    });

    // Cronjob error
    const cronJobErrorMetricNamespace = "/scheduled-tasks/runs/errors";
    const cronJobErrorMetricName = `CronJobErrorMsg-${name}`;

    const cronJobErrorFilter = new aws.cloudwatch.LogMetricFilter(cronJobErrorMetricName, {
      logGroupName: taskResources.logGroup.name,
      metricTransformation: {
        defaultValue: "0",
        name: cronJobErrorMetricName,
        namespace: cronJobErrorMetricNamespace,
        unit: "Count",
        value: "1",
      },
      name: cronJobErrorMetricName,
      pattern: '"CRONJOB ERROR:"',
    });

    const cronJobErrorAlarm = new aws.cloudwatch.MetricAlarm(`CronJobErrorMsgAlarm-${name}`, {
      alarmActions: [taskResources.alertTopic.arn],
      okActions: [taskResources.alertTopic.arn],
      comparisonOperator: "GreaterThanOrEqualToThreshold",
      datapointsToAlarm: 1,
      evaluationPeriods: 1,
      insufficientDataActions: [],
      metricName: cronJobErrorMetricName,
      name: `CronJobErrorMsgAlarm-${name}`,
      namespace: cronJobErrorMetricNamespace,
      period: alarmPeriodSeconds,
      statistic: "Sum",
      threshold: 1,
      treatMissingData: "notBreaching",
      tags: {
        ...defaultTags,
        Name: `CronJobErrorMsgAlarm-${name}`,
      },
    });
  }

  return taskResources.task.id;
}
