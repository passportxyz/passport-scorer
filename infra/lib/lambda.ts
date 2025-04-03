import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { defaultTags } from "./tags";
import { FunctionArgs } from "@pulumi/aws/lambda";

//////////////////////////////////////////////////////////////
// Create a Lambda function
//////////////////////////////////////////////////////////////
export function createLambdaFunction(
  secretManagerArns: pulumi.Output<string>[],
  vpcId: pulumi.Input<string>,
  vpcSubnetIds: string[],
  functionArgs: Partial<FunctionArgs>
) {
  // manage lambda role
  const lambdaRole = new aws.iam.Role(`${functionArgs.name}-role`, {
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Action: "sts:AssumeRole",
          Principal: {
            Service: "lambda.amazonaws.com",
          },
          Effect: "Allow",
        },
      ],
    }),
    tags: {
      ...defaultTags,
      Name: `${functionArgs.name}-role`,
    },
  });

  // Manage log group permissions
  const logPolicy = new aws.iam.Policy(`${functionArgs.name}-log-policy`, {
    name: `${functionArgs.name}-log-policy`,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Action: ["logs:*"],
          Effect: "Allow",
          Resource: `arn:aws:logs:*:*:*`,
        },
      ],
    }),
  });
  new aws.iam.RolePolicyAttachment(`${functionArgs.name}-log-policy-attachment`, {
    policyArn: logPolicy.arn,
    role: lambdaRole.name,
  });

  // All our lambdas need to run within the VPC
  const vpcPolicy = new aws.iam.Policy(`${functionArgs.name}-vpc-policy`, {
    name: `${functionArgs.name}-vpc-policy`,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Action: ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DeleteNetworkInterface"],
          Effect: "Allow",
          Resource: "*",
        },
      ],
    }),
  });

  new aws.iam.RolePolicyAttachment(`${functionArgs.name}-vpc-policy-attachment`, {
    policyArn: vpcPolicy.arn,
    role: lambdaRole.name,
  });

  // Manage secrets manager
  if (secretManagerArns.length > 0) {
    pulumi.all(secretManagerArns).apply((secretManagerArnsStrings) => {
      const secretPolicy = new aws.iam.Policy(`${functionArgs.name}-secret-policy`, {
        name: `${functionArgs.name}-secret-policy`,
        policy: JSON.stringify({
          Version: "2012-10-17",
          Statement: [
            {
              Action: ["secretsmanager:GetSecretValue"],
              Effect: "Allow",
              Resource: secretManagerArnsStrings,
            },
          ],
        }),
      });
      new aws.iam.RolePolicyAttachment(`${functionArgs.name}-secret-policy-attachment`, {
        policyArn: secretPolicy.arn,
        role: lambdaRole.name,
      });
    });
  }

  // This should be created & parsed only if VPC id is provided
  const lambdaSecurityGroup = new aws.ec2.SecurityGroup(`${functionArgs.name}-sg`, {
    vpcId: vpcId,
    ingress: [
      {
        protocol: "-1",
        fromPort: 0,
        toPort: 0,
        cidrBlocks: ["0.0.0.0/0"], //TODO: this should be restricted
      },
    ],
    egress: [
      {
        protocol: "-1",
        fromPort: 0,
        toPort: 0,
        cidrBlocks: ["0.0.0.0/0"],
      },
    ],
    tags: {
      ...defaultTags,
      Name: `${functionArgs.name}-sg`,
    },
  });

  const lambdaLogGroup = new aws.cloudwatch.LogGroup(`${functionArgs.name}-log-group`, {
    name: `/aws/lambda/${functionArgs.name}`,
    retentionInDays: 14,
    tags: {
      ...defaultTags,
      Name: `${functionArgs.name}-log-group`,
    },
  });

  const lambdaFunction = new aws.lambda.Function(`${functionArgs.name}-function`, {
    role: lambdaRole.arn,
    vpcConfig: {
      securityGroupIds: [lambdaSecurityGroup.id],
      subnetIds: vpcSubnetIds,
    },
    loggingConfig: {
      logFormat: "Text", // select between Text and structured JSON format for your function's logs.
      logGroup: lambdaLogGroup.name,
      // systemLogLevel : "DEBUG"  // for JSON structured logs, choose the detail level of the Lambda platform event logs sent to CloudWatch, such as ERROR, DEBUG, or INFO.
    },
    ...functionArgs,
  });

  //TODO:  make the creation of URL conditional
  const lambdaFunctionUrl = new aws.lambda.FunctionUrl(`${functionArgs.name}-url`, {
    functionName: lambdaFunction.name,
    authorizationType: "AWS_IAM", // Set to "NONE" to bypass IAM authentication and create a public endpoint.
  });

  return {
    lambdaFunction,
    lambdaFunctionUrl,
  };
}
