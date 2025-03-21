import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../../lib/tags";
import { createLambdaFunction } from "../../lib/lambda";

export function createMonitoringLambdaFunction(config: {
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListenerArn: pulumi.Input<string>;
  ceramicCacheScorerId: number;
  scorerSecret: aws.secretsmanager.Secret;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcId: pulumi.Input<string>;
  vpcPrivateSubnetIds: pulumi.Input<any>;
  lambdaLayerArn: pulumi.Input<string>;
  bucketId: pulumi.Input<string>;
}) {
  // createEmbedLambdaGeneric({
  //   ...config,
  //   name: "embed-st",
  //   description: "Submit stamps & score passport",
  //   lbRuleConditions: [
  //     {
  //       pathPattern: {
  //         values: ["/internal/embed/stamps/*"],
  //       },
  //     },
  //     {
  //       httpRequestMethod: {
  //         values: ["POST"],
  //       },
  //     },
  //   ],
  //   lbRulePriority: 2100,
  //   lambdaHandler: "embed.lambda_fn.lambda_handler_save_stamps",
  // });
  // const lambdaHandler: "embed.lambda_fn.lambda_handler_save_stamps",
  const name = "system-tests";
  const description = "execute system tests";

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
      name: "CERAMIC_CACHE_SCORER_ID",
      value: `${config.ceramicCacheScorerId}`,
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
    sourceDir: "../../system_tests",
    outputPath: "lambda_function_payload.zip",
    excludes: [], //["**/__pycache__"],
  });

  const lambdaName = `${name}-lambda`;
  const lambdaHandler = "index.handler";
  const { lambdaFunction, lambdaFunctionUrl } = createLambdaFunction(
    [config.scorerSecret.arn],
    config.vpcId,
    config.vpcPrivateSubnetIds,
    {
      name: lambdaName,
      description: description,
      code: new pulumi.asset.FileArchive("lambda_function_payload.zip"),
      // role: lambdaRole.arn,
      handler: lambdaHandler,
      sourceCodeHash: lambdaCode.then((archive) => archive.outputBase64sha256),
      runtime: aws.lambda.Runtime.NodeJS20dX,
      environment: {
        variables: apiLambdaEnvironment.reduce(
          (
            acc: { [key: string]: pulumi.Input<string> },
            e: { name: string; value: pulumi.Input<string> }
          ) => {
            acc[e.name] = e.value;
            return acc;
          },
          {}
        ),
      },
      memorySize: 512,
      timeout: 60,
      layers: [],
      tags: {
        ...defaultTags,
        Name: lambdaName,
      },
    }
  );
}
