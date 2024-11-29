import * as pulumi from "@pulumi/pulumi";
import * as archive from "@pulumi/archive";
import * as aws from "@pulumi/aws";
import * as command from "@pulumi/command";
import { defaultTags } from "../../lib/tags";

export function createPythonLambdaLayer(config: {
  name: string;
  bucketId: pulumi.Input<string>;
}): aws.lambda.LayerVersion {
  // The working dir will be `infra/aws`
  // The `poetry / python` commands need to be executed from within `../../api`, hence the `cd`
  // Output for the python deps will be the `infra/aws/python` folder, I was not able to get the `archivePaths` work from another location for unknown reasons
  const cmd =
    "cd ../../api && poetry export -f requirements.txt -o requirements.txt && poetry run pip install \
    --platform manylinux2014_x86_64 \
    --target=../infra/aws/python/lib/python3.12/site-packages/ \
    --implementation cp \
    --only-binary=:all: --upgrade \
    -r requirements.txt";

  const poetryLock = archive.getFile({
    type: "zip",
    outputPath: "__pythonDeps.zip",
    sourceFile: "../../api/poetry.lock",
  });

  const layerFolder = new command.local.Command(
    `${config.name}-layer-dependencies`,
    {
      create: cmd,
      update: cmd,
      archivePaths: ["python/**", "!**__pycache__**"],
      triggers: [poetryLock.then((pLock) => pLock.outputBase64sha256)],
    }
  );

  const layerBucketObjectName = `${config.name}-layer-code.zip`;

  // The layer will contain all the dependencies we have installed
  const bucketObject = new aws.s3.BucketObject(
    layerBucketObjectName,
    {
      bucket: config.bucketId,
      source: layerFolder.archive,
      sourceHash: poetryLock.then((pLock) => pLock.outputBase64sha256),
      tags: {
        ...defaultTags,
        Name: layerBucketObjectName,
      },
    },
    { dependsOn: [layerFolder] }
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
      skipDestroy: true
    },
    { dependsOn: [bucketObject] }
  );

  return lambdaLayer;
}
