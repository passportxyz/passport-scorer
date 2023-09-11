import * as awsx from "@pulumi/awsx";
import { all } from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import {
  secrets,
  ScorerService,
  ScorerEnvironmentConfig,
  getEnvironment,
} from "./service";

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;

export type ScheduledTaskConfig = Pick<
  ScorerService,
  | "dockerImageScorer"
  | "executionRole"
  | "cluster"
  | "subnets"
  | "securityGroup"
> & {
  command: string[];
  scheduleExpression: string;
  ephemeralStorageSizeInGiB?: number;
  cpu?: number;
  memory?: number;
};

export function createScheduledTask(
  name: string,
  config: ScheduledTaskConfig,
  envConfig: ScorerEnvironmentConfig
) {
  const {
    executionRole,
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

  const task = new awsx.ecs.FargateTaskDefinition(name, {
    executionRole: {
      roleArn: executionRole.arn,
    },
    ephemeralStorage: ephemeralStorageSizeInGiB
      ? {
          sizeInGib: ephemeralStorageSizeInGiB,
        }
      : undefined,
    containers: {
      web: {
        name: `${name}-container`,
        image: "public.ecr.aws/c8n6v8e9/passport-scorer", //dockerImageScorer,
        cpu: cpu ? cpu : 256,
        memory: memory ? memory : 2048,
        secrets,
        environment: getEnvironment(envConfig),
        command,
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

  return task.taskDefinition.id;
}
