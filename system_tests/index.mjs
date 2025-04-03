import jest from "jest";
import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

if (process.env.NODE_ENV == null) {
  process.env.NODE_ENV = "test";
}

// If you need more information about configurations or implementing the sample code, visit the AWS docs:
// https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/getting-started.html
const secret_name = "system-tests";

const client = new SecretsManagerClient({
  region: "us-west-2",
});

let response;

try {
  response = await client.send(
    new GetSecretValueCommand({
      SecretId: secret_name,
      VersionStage: "AWSCURRENT", // VersionStage defaults to AWSCURRENT if unspecified
    }),
  );
} catch (error) {
  // For a list of exceptions thrown, see
  // https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
  console.log("Failed to load secrets! Error: ", error);
  throw error;
}

const secret = response.SecretString;
const secretObj = JSON.parse(secret);

// Assign secret values to process.env
process.env = Object.assign(process.env, secretObj);

// Your code goes here
export const handler = async (event, context) => {
  console.log("EVENT: \n" + JSON.stringify(event, null, 2));
  await jest.run();
  return context.logStreamName;
};
