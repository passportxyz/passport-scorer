import * as awsx from "@pulumi/awsx";
import { all } from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import {
  secrets,
  ScorerService,
  ScorerEnvironmentConfig,
  getEnvironment,
  SecretsConfig,
  getSecrets,
} from "./new_service";

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;

export type ScheduledTaskConfig = Pick<
  ScorerService,
  | "dockerImageScorer"
  | "executionRole"
  | "taskRole"
  | "cluster"
  | "subnets"
  | "securityGroup"
  | "cpu"
  | "memory"
> &
  Required<Pick<ScorerService, "alertTopic">> & {
    command: string;
    scheduleExpression: string;
    ephemeralStorageSizeInGiB?: number;
  };

export function createScheduledTask(
  name: string,
  config: ScheduledTaskConfig,
  envConfig: ScorerEnvironmentConfig,
  alarmPeriondSeconds?: number,
  enableInvocationAlerts?: boolean,
  secretsConfig?: SecretsConfig
) {
  const {
    alertTopic,
    executionRole,
    taskRole,
    subnets,
    dockerImageScorer,
    cluster,
    securityGroup,
    command,
    scheduleExpression,
    ephemeralStorageSizeInGiB,
    cpu,
    memory,
  } = config;

  const commandSuccessMessage = `SUCCESS <${name}>`;
  const commandWithTest = [
    "/bin/bash",
    "-c",
    command + ` && echo "${commandSuccessMessage}"`,
  ];

  const logGroup = new aws.cloudwatch.LogGroup(`scheduled-${name}`, {
    retentionInDays: 90,
  });

  const task = new awsx.ecs.FargateTaskDefinition(name, {
    executionRole: {
      roleArn: executionRole.arn,
    },
    taskRole: {
      roleArn: taskRole.arn,
    },
    ephemeralStorage: ephemeralStorageSizeInGiB
      ? {
          sizeInGib: ephemeralStorageSizeInGiB,
        }
      : undefined,
    logGroup: {
      existing: {
        arn: logGroup.arn,
      },
    },
    containers: {
      web: {
        name: `${name}-container`,
        image: dockerImageScorer,
        cpu: cpu ? cpu : 256,
        memory: memory ? memory : 2048,
        secrets: secretsConfig
          ? getSecrets(secretsConfig).concat(secrets)
          : secrets,
        environment: getEnvironment(envConfig),
        command: commandWithTest,
      },
    },
  });

  const scheduledEventRule = new aws.cloudwatch.EventRule(`rule-${name}`, {
    scheduleExpression,
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
        policy: JSON.stringify({
          Version: "2012-10-17",
          Statement: [
            {
              Action: ["secretsmanager:GetSecretValue"],
              Effect: "Allow",
              Resource: SCORER_SERVER_SSM_ARN,
            },
          ],
        }),
      },
      {
        name: "allow_run_task",
        policy: task.taskDefinition.arn.apply((Resource) =>
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
        policy: all([executionRole.arn, task.taskDefinition.taskRoleArn]).apply(
          ([dpoppEcsRoleArn, weeklyDataDumpTaskRoleArn]) =>
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
    managedPolicyArns: [
      "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    ],
    tags: {
      dpopp: "",
    },
  });

  new aws.cloudwatch.EventTarget(`scheduled-${name}`, {
    rule: scheduledEventRule.name,
    arn: cluster.arn,
    roleArn: eventsStsAssumeRole.arn,
    ecsTarget: {
      taskCount: 1,
      taskDefinitionArn: task.taskDefinition.arn,
      launchType: "FARGATE",
      networkConfiguration: {
        assignPublicIp: false,
        securityGroups: [securityGroup.id],
        subnets,
      },
    },
  });

  if (alarmPeriondSeconds) {
    if (enableInvocationAlerts) {
      // No invocation in the given period
      const missingInvocationsAlarm = new aws.cloudwatch.MetricAlarm(
        "MissingInvocations-" + name,
        {
          alarmActions: [alertTopic.arn],
          okActions: [alertTopic.arn],
          comparisonOperator: "LessThanThreshold",
          datapointsToAlarm: 1,
          evaluationPeriods: 1,
          metricName: "Invocations",
          name: "MissingInvocations-" + name,
          namespace: "AWS/Events",
          dimensions: {
            RuleName: scheduledEventRule.name,
          },
          period: alarmPeriondSeconds,
          statistic: "Sum",
          threshold: 1,
          treatMissingData: "notBreaching",
        }
      );
    }
    // Verify failed invocations
    const failedInvocationsAlarm = new aws.cloudwatch.MetricAlarm(
      `FailedInvocations-${name}`,
      {
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanThreshold",
        datapointsToAlarm: 1,
        evaluationPeriods: 1,
        metricName: "FailedInvocations",
        name: `FailedInvocations-${name}`,
        namespace: "AWS/Events",
        dimensions: {
          RuleName: scheduledEventRule.name,
        },
        period: alarmPeriondSeconds,
        statistic: "Sum",
        threshold: 0,
        treatMissingData: "notBreaching",
      }
    );

    // Missing succes Message
    const successfulRunMetricNamespace = "/scheduled-tasks/runs/success";
    const successfulRunMetricName = `SuccessfulRun-${name}`;

    new aws.cloudwatch.LogMetricFilter(successfulRunMetricName, {
      logGroupName: logGroup.name,
      metricTransformation: {
        defaultValue: "0",
        name: successfulRunMetricName,
        namespace: successfulRunMetricNamespace,
        unit: "Count",
        value: "1",
      },
      name: successfulRunMetricName,
      pattern: `"${commandSuccessMessage}"`,
    });

    new aws.cloudwatch.MetricAlarm(`UnsuccessfulRuns-${name}`, {
      alarmActions: [alertTopic.arn],
      okActions: [alertTopic.arn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      evaluationPeriods: 1,
      metricQueries: [
        {
          id: "m1",
          metric: {
            metricName: successfulRunMetricName,
            namespace: successfulRunMetricNamespace,
            period: alarmPeriondSeconds,
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
            period: alarmPeriondSeconds,
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
    });

    // Cronjob error
    const cronJobErrorMetricNamespace = "/scheduled-tasks/runs/errors";
    const cronJobErrorMetricName = `CronJobErrorMsg-${name}`;

    const cronJobErrorFilter = new aws.cloudwatch.LogMetricFilter(
      cronJobErrorMetricName,
      {
        logGroupName: logGroup.name,
        metricTransformation: {
          defaultValue: "0",
          name: cronJobErrorMetricName,
          namespace: cronJobErrorMetricNamespace,
          unit: "Count",
          value: "1",
        },
        name: cronJobErrorMetricName,
        pattern: '"CRONJOB ERROR:"',
      }
    );

    const cronJobErrorAlarm = new aws.cloudwatch.MetricAlarm(
      `CronJobErrorMsgAlarm-${name}`,
      {
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanOrEqualToThreshold",
        datapointsToAlarm: 1,
        evaluationPeriods: 1,
        insufficientDataActions: [],
        metricName: cronJobErrorMetricName,
        name: `CronJobErrorMsgAlarm-${name}`,
        namespace: cronJobErrorMetricNamespace,
        period: alarmPeriondSeconds,
        statistic: "Sum",
        threshold: 1,
        treatMissingData: "notBreaching",
      }
    );
  }

  return task.taskDefinition.id;
}
