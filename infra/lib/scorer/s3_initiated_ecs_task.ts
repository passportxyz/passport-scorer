import * as aws from "@pulumi/aws";
import { Input, Output } from "@pulumi/pulumi";
import { defaultTags } from "../tags";

export function createS3InitiatedECSTask({
  bucketId,
  bucketName,
  legacyBucketName,
  clusterArn,
  taskDefinitionArn,
  subnetIds,
  securityGroupIds,
  eventsStsAssumeRoleArn,
  containerName,
}: {
  bucketId: Output<string>;
  bucketName: string;
  legacyBucketName: string;
  clusterArn: Output<string>;
  taskDefinitionArn: Output<string>;
  subnetIds: Output<any>;
  securityGroupIds: Output<string>[];
  eventsStsAssumeRoleArn: Input<string>;
  containerName: string;
}) {
  // Create the legacy S3 bucket. We will not use this any more,
  // but we want to keep the data in it for now
  new aws.s3.Bucket(legacyBucketName, {
    bucket: legacyBucketName,
    tags: {
      ...defaultTags,
      Name: bucketName,
    },
  });

  // Enable S3 event notifications to EventBridge
  new aws.s3.BucketNotification(`${bucketName}-notification`, {
    bucket: bucketId,
    eventbridge: true,
  });

  // const folders = ["batch_model_scoring_request/triggers/"];
  // folders.forEach((folder) => {
  //   new aws.s3.BucketObject(`${folder}`, {
  //     bucket: bucket.id,
  //     key: folder,
  //     content: "",
  //     tags: {
  //       ...defaultTags,
  //       Name: folder,
  //     },
  //   });
  // });

  // Create EventBridge rule
  const rule = new aws.cloudwatch.EventRule("s3-to-ecs-rule", {
    eventPattern: JSON.stringify({
      source: ["aws.s3"],
      "detail-type": ["Object Created"],
      detail: {
        bucket: {
          name: [bucketName],
        },
        object: {
          key: [
            {
              prefix: "batch_model_scoring_request/triggers/",
            },
          ],
        },
      },
    }),
    tags: {
      ...defaultTags,
      Name: "s3-to-ecs-rule",
      Scope: "MBD batch processing",
    },
  });

  // Create EventBridge target
  new aws.cloudwatch.EventTarget("ecs-task-target", {
    rule: rule.name,
    arn: clusterArn,
    roleArn: eventsStsAssumeRoleArn,
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
    inputTransformer: {
      inputPaths: {
        bucketName: "$.detail.bucket.name",
        objectKey: "$.detail.object.key",
      },
      inputTemplate: JSON.stringify({
        containerOverrides: [
          {
            name: containerName,
            environment: [
              {
                name: "S3_BUCKET",
                value: "<bucketName>",
              },
              {
                name: "S3_OBJECT_KEY",
                value: "<objectKey>",
              },
            ],
          },
        ],
      }),
    },
  });

  return {
    bucketId: bucketId,
    eventBridgeRuleArn: rule.arn,
  };
}
