import * as aws from "@pulumi/aws";

export function createS3TriggeredECSTask(
  bucketName: string,
  clusterArn: string,
  taskDefinitionArn: string,
  subnetIds: string[],
  securityGroupIds: string[],
) {
  // Create S3 bucket
  const bucket = new aws.s3.Bucket(bucketName, {
    bucket: bucketName,
  });

  // Enable S3 event notifications to EventBridge
  new aws.s3.BucketNotification(`${bucketName}-notification`, {
    bucket: bucket.id,
    eventbridge: true,
  });

  // Create IAM role for EventBridge to trigger ECS task
  const eventBridgeRole = new aws.iam.Role("eventbridge-ecs-role", {
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Principal: {
            Service: "events.amazonaws.com",
          },
          Action: "sts:AssumeRole",
        },
      ],
    }),
  });

  // Attach policy to the role
  new aws.iam.RolePolicy("eventbridge-ecs-role-policy", {
    role: eventBridgeRole.id,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: ["ecs:RunTask"],
          Resource: [taskDefinitionArn],
          Condition: {
            ArnLike: {
              "ecs:cluster": clusterArn,
            },
          },
        },
        {
          Effect: "Allow",
          Action: "iam:PassRole",
          Resource: ["*"],
          Condition: {
            StringLike: {
              "iam:PassedToService": "ecs-tasks.amazonaws.com",
            },
          },
        },
      ],
    }),
  });

  // Create EventBridge rule
  const rule = new aws.cloudwatch.EventRule("s3-to-ecs-rule", {
    eventPattern: JSON.stringify({
      source: ["aws.s3"],
      "detail-type": ["Object Created"],
      detail: {
        bucket: {
          name: [bucketName],
        },
      },
    }),
  });

  // Create EventBridge target
  new aws.cloudwatch.EventTarget("ecs-task-target", {
    rule: rule.name,
    arn: clusterArn,
    roleArn: eventBridgeRole.arn,
    ecsTarget: {
      taskDefinitionArn: taskDefinitionArn,
      taskCount: 1,
      launchType: "FARGATE",
      networkConfiguration: {
        assignPublicIp: false,
        subnets: subnetIds,
        securityGroups: securityGroupIds,
      },
    },
  });

  return {
    bucketName: bucket.id,
    eventBridgeRuleArn: rule.arn,
  };
}
