import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import * as command from "@pulumi/command";
import { defaultTags } from "../../lib/tags";
import { existsSync, statSync } from "fs";
import { spawn } from "child_process";

export function runCommand(
  command: string,
  args: string[],
  options: Record<string, any>
): Promise<void> {
  return new Promise((resolve, reject) => {
    const cmd = spawn(command, args, { stdio: "inherit", ...options });

    cmd.on("error", (error) => {
      reject(`Failed to start process: ${error.message}`);
    });

    cmd.on("close", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(`Process exited with code: ${code}`);
      }
    });
  });
}

export function createPythonLambdaLayer(config: {
  name: string;
  bucketId: pulumi.Input<string>;
}): aws.lambda.LayerVersion {
  // The working dir will be `infra/aws`
  // The `poetry / python` commands need to be executed from within `../../api`, hence the `cd`
  // Output for the python deps will be the `infra/aws/python` folder, I was not able to get the `archivePaths` work from another location for unknown reasons

  const layerBucketObjectName = `${config.name}-layer-code.zip`;
  const expectedArchivePath = `../../${layerBucketObjectName}`;

  function checkIfFileExists(filePath: string): boolean {
    if (existsSync(filePath)) {
      return statSync(filePath).isFile(); // Check if it's a file
    }
    return false; // File does not exist
  }

  // Example usage:
  const filePath = "./path/to/file.txt";
  if (checkIfFileExists(filePath)) {
    console.log("The file exists!");
  } else {
    console.log("The file does not exist.");
  }

  const pythonDepsArchive = runCommand(
    "poetry",
    ["export", "-f", "requirements.txt", "-o", "requirements.txt"],
    { cwd: "../../api" }
  )
    .then(() =>
      runCommand("rm", ["-Rf", "__lambda__"], {
        cwd: "../..",
      })
    )
    .then(() =>
      runCommand(
        "poetry",
        [
          "run",
          "pip",
          "-q",
          "install",
          "--platform",
          "manylinux2014_x86_64",
          "--target=../__lambda__/python/lib/python3.12/site-packages/",
          "--implementation",
          "cp",
          "--only-binary=:all:",
          "--upgrade",
          "-r",
          "requirements.txt",
        ],
        { cwd: "../../api" }
      )
    )

    .then(() =>
      runCommand(
        "find",
        [
          "__lambda__",
          "-type",
          "d",
          "-name",
          "__pycache__",
          "-exec",
          "rm",
          "-rf",
          "{}",
          "+",
        ],
        {
          cwd: "../..",
        }
      )
    )
    .then(() => runCommand("rm", ["-Rf", expectedArchivePath], {}))
    .then(() =>
      // See https://docs.aws.amazon.com/lambda/latest/dg/packaging-layers.html
      // for the expected folder structure
      runCommand("zip", ["-q", "-r", `../${layerBucketObjectName}`, "python"], {
        cwd: "../../__lambda__",
      })
    )
    .then(() => new pulumi.asset.FileArchive(expectedArchivePath));

  const poetryLock = archive.getFile({
    type: "zip",
    outputPath: "__pythonDeps.zip",
    sourceFile: "../../api/poetry.lock",
  });

  // const pythonDepsArchiv1 = archive.getFile({
  //   type: "zip",
  //   outputPath: "__pythonDeps1.zip",
  //   sourceDir: "../../__lambda__/python",
  // });

  // The layer will contain all the dependencies we have installed
  const bucketObject = new aws.s3.BucketObject(
    layerBucketObjectName,
    {
      bucket: config.bucketId,
      source: pythonDepsArchive,
      sourceHash: poetryLock.then((pLock) => pLock.outputBase64sha256),
      tags: {
        ...defaultTags,
        Name: layerBucketObjectName,
      },
    },
    { dependsOn: [] }
  );

  const layerName = `${config.name}-python-deps`;
  const lambdaLayer = new aws.lambda.LayerVersion(
    layerName,
    {
      s3Bucket: config.bucketId,
      s3Key: bucketObject.id,
      s3ObjectVersion: bucketObject.versionId,
      layerName: layerName,
      compatibleRuntimes: [aws.lambda.Runtime.Python3d12],
      sourceCodeHash: poetryLock.then((pLock) => pLock.outputBase64sha256),
      skipDestroy: true,
    },
    { dependsOn: [bucketObject] }
  );

  return lambdaLayer;
}
