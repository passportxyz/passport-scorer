import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as archive from "@pulumi/archive";

import { createLambdaFunction, createLambdaTargetGroup } from "../../lib/scorer/routing-utils";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../../lib/tags";
import { createLambdaFunction as createLambdaFunctionOld } from "../../lib/lambda";

export function createEmbedLambdaFunctions(config: {
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListenerArn: pulumi.Input<string>;
  scorerSecret: aws.secretsmanager.Secret;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcId: pulumi.Input<string>;
  vpcPrivateSubnetIds: pulumi.Input<any>;
  lambdaLayerArn: pulumi.Input<string>;
  bucketId: pulumi.Input<string>;
}) {
  // Common environment variables for all embed lambdas
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

  // We need to use the old createLambdaFunction for now since the new one doesn't support zip files
  // This is a temporary workaround - these should eventually be migrated to Docker containers

  // Embed Save Stamps Lambda
  const embedStLambdaName = "embed-st-lambda";
  const { lambdaFunction: embedStLambda } = createLambdaFunctionOld(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: embedStLambdaName,
      description: "Submit stamps & score passport",
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      handler: "embed.lambda_fn.lambda_handler_save_stamps",
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
        Name: embedStLambdaName,
      },
    }
  );

  const embedStTargetGroup = createLambdaTargetGroup({
    name: "embed-st-lambda",
    lambda: embedStLambda,
    vpcId: config.vpcId,
  });

  // Embed Rate Limit Lambda
  const embedRlLambdaName = "embed-rl-lambda";
  const { lambdaFunction: embedRlLambda } = createLambdaFunctionOld(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: embedRlLambdaName,
      description: "Retrieve the rate limit for an API key",
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      handler: "embed.lambda_fn.lambda_handler_get_rate_limit",
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
        Name: embedRlLambdaName,
      },
    }
  );

  const embedRlTargetGroup = createLambdaTargetGroup({
    name: "embed-rl-lambda",
    lambda: embedRlLambda,
    vpcId: config.vpcId,
  });

  // Embed Get Score Lambda
  const embedGsLambdaName = "embed-gs-lambda";
  const { lambdaFunction: embedGsLambda } = createLambdaFunctionOld(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: embedGsLambdaName,
      description: "Retrieve the score for an address",
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      handler: "embed.lambda_fn.lambda_handler_get_score",
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
        Name: embedGsLambdaName,
      },
    }
  );

  const embedGsTargetGroup = createLambdaTargetGroup({
    name: "embed-gs-lambda",
    lambda: embedGsLambda,
    vpcId: config.vpcId,
  });

  // Create CloudWatch alarms for monitoring
  const embedStAlarm = new aws.cloudwatch.MetricAlarm("embed-st-lambda-errors", {
    tags: { ...defaultTags, Name: "embed-st-lambda-errors" },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    dimensions: {
      FunctionName: embedStLambdaName,
    },
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    metricName: "Errors",
    name: "embed-st-lambda-errors",
    namespace: "AWS/Lambda",
    period: 60,
    unit: "Seconds",
    statistic: "SampleCount",
    treatMissingData: "notBreaching",
    threshold: 1,
  });

  const embedRlAlarm = new aws.cloudwatch.MetricAlarm("embed-rl-lambda-errors", {
    tags: { ...defaultTags, Name: "embed-rl-lambda-errors" },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    dimensions: {
      FunctionName: embedRlLambdaName,
    },
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    metricName: "Errors",
    name: "embed-rl-lambda-errors",
    namespace: "AWS/Lambda",
    period: 60,
    unit: "Seconds",
    statistic: "SampleCount",
    treatMissingData: "notBreaching",
    threshold: 1,
  });

  const embedGsAlarm = new aws.cloudwatch.MetricAlarm("embed-gs-lambda-errors", {
    tags: { ...defaultTags, Name: "embed-gs-lambda-errors" },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    dimensions: {
      FunctionName: embedGsLambdaName,
    },
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    metricName: "Errors",
    name: "embed-gs-lambda-errors",
    namespace: "AWS/Lambda",
    period: 60,
    unit: "Seconds",
    statistic: "SampleCount",
    treatMissingData: "notBreaching",
    threshold: 1,
  });

  // Return the target groups for use in centralized routing
  return {
    targetGroups: {
      embedStTargetGroup,
      embedRlTargetGroup,
      embedGsTargetGroup,
    },
  };
}
