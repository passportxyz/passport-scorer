import * as awsx from "@pulumi/awsx";
import { all } from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import { local } from "@pulumi/command";
import {
  secrets,
  ScorerService,
  ScorerEnvironmentConfig,
  getEnvironment,
  SecretsConfig,
  getSecrets,
} from "./new_service";
import { getSecret } from "@pulumi/aws/kms/getSecret";

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

export function _createScheduledTask(
  name: string,
  config: ScheduledTaskConfig,
  envConfig: ScorerEnvironmentConfig,
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

  const eventsStsAssumeRole = new aws.iam.Role(`${name}-eventsStsAssumeRole`, {
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

  new aws.cloudwatch.EventTarget(`scheduledEventTarget-${name}`, {
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

  const metricNamespace = "/scheduled-tasks/runs/success";
  const metricName = `SuccessfulRun-${name}`;

  new aws.cloudwatch.LogMetricFilter(metricName, {
    logGroupName: logGroup.name,
    metricTransformation: {
      defaultValue: "0",
      name: metricName,
      namespace: metricNamespace,
      unit: "Count",
      value: "1",
    },
    name: metricName,
    pattern: `"${commandSuccessMessage}"`,
  });

  const SIX_HOURS_IN_SECONDS = 6 * 60 * 60;

  new aws.cloudwatch.MetricAlarm("UnsuccessfulRuns-" + name, {
    ////////////////////////////////////////////////////////////////////////////////////////////////////////////
    // Temporarily disable the alarm actions until the metric is changed
    // At the moment even if the task is completed successfully the alarm enters the alarm state for 1 minute.
    ////////////////////////////////////////////////////////////////////////////////////////////////////////////
    // alarmActions: [alertTopic.arn],
    // okActions: [alertTopic.arn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    datapointsToAlarm: 1,
    evaluationPeriods: 1,
    metricQueries: [
      {
        id: "m1",
        metric: {
          metricName,
          namespace: metricNamespace,
          period: SIX_HOURS_IN_SECONDS,
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
          period: SIX_HOURS_IN_SECONDS,
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
    name: "UnsuccessfulRuns-" + name,
    treatMissingData: "notBreaching",
  });

  // Manage Heartbeat error  Alerts
  if (envConfig.heartBeatMonitorUrl) {
    const heartBeatMetric = new aws.cloudwatch.LogMetricFilter(
      `${name}-heartBeat-error-metric`,
      {
        logGroupName: logGroup.name,
        metricTransformation: {
          defaultValue: "0",
          name: `heartBeat-${name}`,
          namespace: "/scheduled-tasks/runs/heartbeat",
          unit: "Count",
          value: "1",
        },
        name: "heartBeat-${name}",
        pattern: '"Error HeartBeat Process"',
      }
    );

    const heartBeatErrorAlarm = new aws.cloudwatch.MetricAlarm(`${name}-heartBeat-error-alarm`, {
        alarmActions: [alertTopic.arn],
        okActions: [alertTopic.arn],
        comparisonOperator: "GreaterThanOrEqualToThreshold",
        datapointsToAlarm: 1,
        evaluationPeriods: 1,
        insufficientDataActions: [],
        metricName: `heartBeat-${name}`,
        name:`heartBeat-${name}`,
        namespace: "/scheduled-tasks/runs/heartbeat",
        period: 1800, // 30min
        statistic: "Sum",
        threshold: 1,
        treatMissingData: "notBreaching",
      });
  }

  return task.taskDefinition.id;
}

export function createScheduledTask(
  name: string,
  uptimeRobotSecondsInterval: number,
  config: ScheduledTaskConfig,
  envConfig: ScorerEnvironmentConfig,
  secretsConfig?: SecretsConfig
) {
  // Manage Uptime Robot endpoint
  // The script only does a create, it doesn't update or delete old endpoints
  // The monitors need to be deleted manually at the moment
  const uptimeRobotScript = new local.Command(`uptimeRobot-${name}`, {
    create: `sh ../scripts/create_monitor.sh cron-${name} ${uptimeRobotSecondsInterval} 0`, // executed once on create
  });

  // uptimeRobotScript.stderr.apply( (_err) => {
  //   // console.log(" _err = ", _err);
  //   // if (_err) {
  //   //   throw Error(`Error creating UptimeRobot endpoint. Error: ${_err}`);
  //   // }
  // });

  let taskId;
  uptimeRobotScript.stdout.apply((_out) => {
    const parsedOutput = JSON.parse(_out);
    if (
      Object.keys(parsedOutput) &&
      parsedOutput.stat === "ok" &&
      parsedOutput.monitor &&
      Object.keys(parsedOutput.monitor) &&
      parsedOutput.monitor.url
    ) {
      const heartBeatUrl = parsedOutput.monitor.url;
      if (heartBeatUrl) {
        taskId = _createScheduledTask(
          name,
          config,
          {
            ...envConfig,
            heartBeatMonitorUrl: heartBeatUrl,
          },
          secretsConfig
        );
      }
    } else {
      throw Error(`Error retriving the heartbeat endpoint. Output: ${_out}`);
    }
  });

  return taskId;
}
