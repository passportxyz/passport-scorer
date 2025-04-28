import { spawn } from "child_process";
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

export const handler = async (event) => {
  console.log("EVENT: \n" + JSON.stringify(event, null, 2));
  console.log("Running tests in child process...");

  try {
    // Run Jest in a child process
    const result = await runJestInChildProcess();

    console.log("Jest process completed", result);

    // Always return success response to the caller
    return {
      statusCode: 200,
      body: JSON.stringify({
        testsPassed: result.exitCode === 0,
        details: result,
      }),
    };
  } catch (error) {
    console.error("Failed to run Jest:", error);

    // Return success even if Jest process itself failed to run
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: "Failed to run Jest",
        details: error.message,
      }),
    };
  }
};

/**
 * Runs Jest in a child process and returns the result
 */
async function runJestInChildProcess() {
  return new Promise((resolve, reject) => {
    // Create a new file that will call jest.run()
    // You'll need to create a jest-runner.mjs file with the content shown below
    const childProcess = spawn("node", ["jest-runner.mjs"], {
      // Important: set detached: false to ensure the process terminates
      detached: false,
      // This ensures Jest can find your config and tests
      cwd: process.cwd(),
      // Pass through environment variables
      env: { ...process.env, FORCE_COLOR: "0" },
    });

    let stdout = "";
    let stderr = "";

    // Capture output
    childProcess.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    childProcess.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    // Handle process completion
    childProcess.on("close", (exitCode) => {
      resolve({
        exitCode: exitCode ?? -1,
        stdout,
        stderr,
      });
    });

    // Handle process errors (like failed to spawn)
    childProcess.on("error", (error) => {
      reject(error);
    });

    // Set a timeout to ensure the process doesn't hang
    const timeout = setTimeout(
      () => {
        try {
          // Force kill if it's taking too long
          childProcess.kill("SIGKILL");
        } catch (e) {
          console.warn("Failed to kill Jest process:", e);
        }
        reject(new Error("Jest child process timed out"));
      },
      5 * 60 * 1000, // 5 minutes
    );

    // Clear timeout if process ends normally
    childProcess.on("exit", () => {
      clearTimeout(timeout);
    });
  });
}
