import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";
import { defaultTags } from "./tags";
import { coreRdsSecretArn } from "./config";
//////////////////////////////////////////////////////////////
// Create a Lambda function
//////////////////////////////////////////////////////////////

export function createLambdaFunction(
  name: string,
  lambdaDescription: string,
  dockerImageUri: string,
  dockerCmd: string[],
  vpcId: string,
  vpcSubnetIds: string[],
  secretManagerArns: string[],
  environmentVariables: Record<string, string>
) {
  // manage lambda role

  const lambdaRole = new aws.iam.Role(`${name}-role`, {
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Action: "sts:AssumeRole",
          Principal: {
            Service: "lambda.amazonaws.com",
          },
          Effect: "Allow",
          Sid: `${name}LambdaAssumeRole`,
        },
      ],
    }),
    tags: {
      ...defaultTags,
      Name: `${name}-role`,
    },
  });

  // Manage log group permissions
  const logPolicy = new aws.iam.Policy(`${name}-log-policy`, {
    name: `${name}-log-policy`,
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
  new aws.iam.RolePolicyAttachment(`${name}-log-policy-attachment`, {
    policyArn: logPolicy.arn,
    role: lambdaRole.name,
  });

  // TODO: function accepts a list of additional policies to attach to the role .
  if (vpcId) {
    // add VPC required permissions
    const vpcPolicy = new aws.iam.Policy(`${name}-vpc-policy`, {
      name: `${name}-vpc-policy`,
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: [
              "ec2:CreateNetworkInterface",
              "ec2:DescribeNetworkInterfaces",
              "ec2:DeleteNetworkInterface",
            ],
            Effect: "Allow",
            Resource: "*",
          },
        ],
      }),
    });

    new aws.iam.RolePolicyAttachment(`${name}-vpc-policy-attachment`, {
      policyArn: vpcPolicy.arn,
      role: lambdaRole.name,
    });
  }

  // Manage secrets manager
  if (secretManagerArns.length > 0) {
    const secretPolicy = new aws.iam.Policy(`${name}-secret-policy`, {
      name: `${name}-secret-policy`,
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: secretManagerArns,
          },
        ],
      }),
    });
    new aws.iam.RolePolicyAttachment(`${name}-secret-policy-attachment`, {
      policyArn: secretPolicy.arn,
      role: lambdaRole.name,
    });
  }

  // This should be created & parsed only if VPC id is provided
  const lambdaSecurityGroup = new aws.ec2.SecurityGroup(`${name}-sg`, {
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
      Name: `${name}-sg`,
    },
  });

  const lambdaLogGroup = new aws.cloudwatch.LogGroup(`${name}-log-group`, {
    name: `/aws/lambda/${name}`,
    retentionInDays: 14,
    tags: {
      ...defaultTags,
      Name: `${name}-log-group`,
    },
  });

  const lambdaFunction = new aws.lambda.Function(`${name}-function`, {
    name: name,
    description: lambdaDescription,
    role: lambdaRole.arn,
    packageType: "Image",
    imageUri: dockerImageUri,
    imageConfig: {
      commands: dockerCmd,
    },
    memorySize: 128,
    timeout: 120,
    vpcConfig: {
      securityGroupIds: [lambdaSecurityGroup.id],
      subnetIds: vpcSubnetIds,
    },
    loggingConfig: {
      logFormat: "Text", // select between Text and structured JSON format for your function's logs.
      logGroup: lambdaLogGroup.name,
      // systemLogLevel : "DEBUG"  // for JSON structured logs, choose the detail level of the Lambda platform event logs sent to CloudWatch, such as ERROR, DEBUG, or INFO.
    },
    environment: {
      variables: environmentVariables,
    },
  });

  //TODO:  make the creation of URL conditional
  const lambdaFunctionUrl = new aws.lambda.FunctionUrl(`${name}-url`, {
    functionName: lambdaFunction.name,
    authorizationType: "AWS_IAM", // Set to "NONE" to bypass IAM authentication and create a public endpoint.
  });

  return {
    lambdaFunction,
    lambdaFunctionUrl,
  };
}
