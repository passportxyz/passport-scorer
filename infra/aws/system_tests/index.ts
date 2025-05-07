import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import { secretsManager } from "infra-libs";
import { defaultTags, stack } from "../../lib/tags";
import { createLambdaFunction } from "../../lib/lambda";
import { runCommand } from "../layer";

export function createMonitoringLambdaFunction(config: {
  snsAlertsTopicArn: pulumi.Input<string>;
  httpsListenerArn: pulumi.Input<string>;
  ceramicCacheScorerId: number;
  privateSubnetSecurityGroup: aws.ec2.SecurityGroup;
  vpcId: pulumi.Input<string>;
  vpcPrivateSubnetIds: pulumi.Input<any>;
  lambdaLayerArn: pulumi.Input<string>;
  bucketId: pulumi.Input<string>;
  scorerDbProxyEndpointConn: pulumi.Input<string>;
}) {
  pulumi.all([config.scorerDbProxyEndpointConn]).apply(([_scorerDbProxyEndpointConn]) => {
    const name = "system-tests";
    const description = "execute system tests";

    const systemTestsSecret = new aws.secretsmanager.Secret("system-tests", {
      name: "system-tests",
      description: "System Tests Secrets",
      tags: {
        ...defaultTags,
        Name: "scorer-secret",
      },
    });

    secretsManager.syncSecretsAndGetRefs({
      vault: "DevOps",
      repo: "system-tests",
      env: stack,
      section: "run",
      targetSecret: systemTestsSecret,
      secretVersionName: "system-tests-version",
      extraSecretDefinitions: [
        {
          name: "DATABASE_URL",
          value: _scorerDbProxyEndpointConn,
        },
      ],
    });

    const apiLambdaEnvironment = [
      ...secretsManager.getEnvironmentVars({
        vault: "DevOps",
        repo: "system-tests",
        env: stack,
        section: "run",
      }),
    ].sort(secretsManager.sortByName);

    // The lambda will contain our own code (everything from the `api` folder for now)
    const lambdaCode = archive.getFile({
      type: "zip",
      sourceDir: "../../system_tests",
      outputPath: `${name}-lambda-function-payload.zip`,
      excludes: [], //["**/__pycache__"],
    });
    const layerBucketObjectName = `${name}-lambda-code.zip`;
    const expectedArchivePath = `../../${layerBucketObjectName}`;

    const nodeCodeArchive = runCommand("yarn", ["install", "--frozen-lockfile"], { cwd: "../../system_tests" })
      .then(() => runCommand("rm", ["-Rf", expectedArchivePath], {}))
      .then(() =>
        runCommand("zip", ["-q", "-r", `../${layerBucketObjectName}`, "."], {
          cwd: "../../system_tests",
        })
      )
      .then(() => new pulumi.asset.FileArchive(expectedArchivePath));

    const lambdaName = `${name}-lambda`;
    const lambdaHandler = "index.handler";
    const { lambdaFunction, lambdaFunctionUrl } = createLambdaFunction(
      [systemTestsSecret.arn],
      config.vpcId,
      config.vpcPrivateSubnetIds,
      {
        name: lambdaName,
        description: description,
        code: nodeCodeArchive,
        // new pulumi.asset.FileArchive(
        //   `${name}-lambda-function-payload.zip`
        // ),
        // role: lambdaRole.arn,
        handler: lambdaHandler,
        sourceCodeHash: lambdaCode.then((archive) => archive.outputBase64sha256),
        runtime: aws.lambda.Runtime.NodeJS20dX,
        environment: {
          variables: apiLambdaEnvironment.reduce(
            (acc: { [key: string]: pulumi.Input<string> }, e: { name: string; value: pulumi.Input<string> }) => {
              acc[e.name] = e.value;
              return acc;
            },
            {}
          ),
        },
        memorySize: 1024,
        timeout: 60 * 15,
        layers: [],
        tags: {
          ...defaultTags,
          Name: lambdaName,
        },
      }
    );

    const scheduledEventRuleName = `${name}-rule`;
    const scheduledEventRule = new aws.cloudwatch.EventRule(scheduledEventRuleName, {
      scheduleExpression: stack === "production" ? "cron(0/5 * ? * * *)" : "cron(0 0 ? * * *)",
      tags: {
        ...defaultTags,
        Name: scheduledEventRuleName,
      },
    });

    // Granting EventBridge the necessary permissions to trigger the Lambda function.
    new aws.lambda.Permission(`${name}-permission`, {
      action: "lambda:InvokeFunction",
      function: lambdaFunction,
      principal: "events.amazonaws.com",
      sourceArn: scheduledEventRule.arn,
    });

    // Target the rule to the lambda
    const scheduledEventTargetName = `${name}-target`;
    new aws.cloudwatch.EventTarget(scheduledEventTargetName, {
      rule: scheduledEventRule.name,
      arn: lambdaFunction.arn,
    });
  });
}
