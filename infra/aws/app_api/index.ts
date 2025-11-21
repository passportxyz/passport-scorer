import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as archive from "@pulumi/archive";

import { createLambdaFunction, createLambdaTargetGroup } from "../../lib/scorer/routing-utils";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../../lib/tags";
import { createLambdaFunction as createLambdaFunctionOld } from "../../lib/lambda";

export function createAppApiLambdaFunctions(config: {
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListenerArn: pulumi.Input<string>;
  scorerSecret: aws.secretsmanager.Secret;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcId: pulumi.Input<string>;
  vpcPrivateSubnetIds: pulumi.Input<any>;
  lambdaLayerArn: pulumi.Input<string>;
  bucketId: pulumi.Input<string>;
}) {
  // Common environment variables for all app API lambdas
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

  // Account Nonce Lambda
  const ccNonceLambdaName = "cc-nonce-lambda";
  const { lambdaFunction: ccNonceLambda } = createLambdaFunctionOld(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: ccNonceLambdaName,
      description: "Get nonce for authentication from app",
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      handler: "app_api.lambda_fn.lambda_handler_account_nonce",
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
        Name: ccNonceLambdaName,
      },
    }
  );

  const ccNonceTargetGroup = createLambdaTargetGroup({
    name: "cc-nonce-lambda",
    lambda: ccNonceLambda,
    vpcId: config.vpcId,
  });

  // Authenticate Lambda
  const ccAuthLambdaName = "cc-auth-lambda";
  const { lambdaFunction: ccAuthLambda } = createLambdaFunctionOld(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: ccAuthLambdaName,
      description: "Authenticate a user and return JWT",
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      handler: "app_api.lambda_fn.lambda_handler_authenticate",
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
        Name: ccAuthLambdaName,
      },
    }
  );

  const ccAuthTargetGroup = createLambdaTargetGroup({
    name: "cc-auth-lambda",
    lambda: ccAuthLambda,
    vpcId: config.vpcId,
  });

  // Create CloudWatch alarms for monitoring
  const ccNonceAlarm = new aws.cloudwatch.MetricAlarm("cc-nonce-lambda-errors", {
    tags: { ...defaultTags, Name: "cc-nonce-lambda-errors" },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    dimensions: {
      FunctionName: ccNonceLambdaName,
    },
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    metricName: "Errors",
    name: "cc-nonce-lambda-errors",
    namespace: "AWS/Lambda",
    period: 60,
    unit: "Seconds",
    statistic: "SampleCount",
    treatMissingData: "notBreaching",
    threshold: 1,
  });

  const ccAuthAlarm = new aws.cloudwatch.MetricAlarm("cc-auth-lambda-errors", {
    tags: { ...defaultTags, Name: "cc-auth-lambda-errors" },
    alarmActions: [config.snsAlertsTopicArn],
    okActions: [config.snsAlertsTopicArn],
    comparisonOperator: "GreaterThanOrEqualToThreshold",
    dimensions: {
      FunctionName: ccAuthLambdaName,
    },
    datapointsToAlarm: 3,
    evaluationPeriods: 5,
    metricName: "Errors",
    name: "cc-auth-lambda-errors",
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
      ccNonceTargetGroup,
      ccAuthTargetGroup,
    },
  };
}