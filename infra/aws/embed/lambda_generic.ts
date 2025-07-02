import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import { ListenerRule } from "@pulumi/aws/lb";
import { Listener } from "@pulumi/aws/alb";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../../lib/tags";

import { createLambdaFunction } from "../../lib/lambda";

export function createEmbedLambdaGeneric(config: {
  name: string;
  description: string;
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListenerArn: pulumi.Input<string>;
  scorerSecret: aws.secretsmanager.Secret;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcId: pulumi.Input<string>;
  vpcPrivateSubnetIds: pulumi.Input<any>;
  lambdaLayerArn: pulumi.Input<string>;
  bucketId: pulumi.Input<string>;
  lbRuleConditions: pulumi.Input<any>;
  lbRulePriority: pulumi.Input<number>;
  lambdaHandler: pulumi.Input<string>;
}) {
  const apiLambdaEnvironment = [
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
      name: "FF_API_ANALYTICS",
      value: "on",
    },
    {
      name: "SCORER_SERVER_SSM_ARN",
      value: config.scorerSecret.arn,
    },
    {
      name: "VERIFIER_URL",
      value: "http://core-alb.private.gitcoin.co/verifier/verify",
    },
  ].sort(secretsManager.sortByName);

  // The lambda will contain our own code (everything from the `api` folder for now)
  const lambdaCode = archive.getFile({
    type: "zip",
    sourceDir: "../../api",
    outputPath: "lambda_function_payload.zip",
    excludes: ["**/__pycache__"],
  });

  const lambdaName = `${config.name}-lambda`;
  const { lambdaFunction, lambdaFunctionUrl } = createLambdaFunction(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: lambdaName,
      description: config.description,
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      // role: lambdaRole.arn,
      handler: config.lambdaHandler,
      sourceCodeHash: lambdaCode.then((archive) => archive.outputBase64sha256),
      runtime: aws.lambda.Runtime.Python3d12,
      environment: {
        variables: apiLambdaEnvironment.reduce(
          (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
            acc[e.name] = e.value;
            return acc;
          },
          {}
        ),
      },
      memorySize: 512,
      timeout: 60,
      layers: [config.lambdaLayerArn],
      tags: {
        ...defaultTags,
        Name: lambdaName,
      },
    }
  );

  // Create alarm to monitor lambda errors
  const metricAlarmName = `${config.name}-lambda-errors`;
  const lambdaErrorsAlarm = new aws.cloudwatch.MetricAlarm(metricAlarmName, {
    tags: { ...defaultTags, Name: metricAlarmName },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    dimensions: {
      FunctionName: lambdaName,
    },
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    metricName: "Errors",
    name: metricAlarmName,
    namespace: "AWS/Lambda",
    period: 60, // 1 min
    unit: "Seconds",
    statistic: "SampleCount",
    treatMissingData: "notBreaching",
    threshold: 1,
  });

  ///////////////////////////////////////////////////////////////////////////
  const lambdaTargetGroup = new aws.lb.TargetGroup(`${config.name}-lambda-tg`, {
    name: `${config.name}-lambda-target-group`,
    targetType: "lambda",
    tags: { ...defaultTags, Name: `${config.name}-lambda` },
  });

  const withLb = new aws.lambda.Permission(`${config.name}-lambda-permission`, {
    action: "lambda:InvokeFunction",
    function: lambdaFunction.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: lambdaTargetGroup.arn,
  });
  const lambdaTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    `${config.name}-lambda-tg-attachment`,
    {
      targetGroupArn: lambdaTargetGroup.arn,
      targetId: lambdaFunction.arn,
    },
    {
      dependsOn: [withLb],
    }
  );

  const targetPassportRule = new ListenerRule(`${config.name}-rule-lambda`, {
    tags: { ...defaultTags, Name: `${config.name}-rule-lambda` },
    listenerArn: config.httpsListenerArn,
    priority: config.lbRulePriority,
    actions: [
      {
        type: "forward",
        targetGroupArn: lambdaTargetGroup.arn,
      },
    ],
    conditions: config.lbRuleConditions,
  });
}
