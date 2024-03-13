import * as aws from "@pulumi/aws";
import { Input } from "@pulumi/pulumi";

export function createStakingApp(domainName: Input<string>, prefix: Input<string>, environmentVariables: Input<{
  [key: string]: Input<string>
}>): aws.amplify.App {
  const amplifyApp = new aws.amplify.App("example", {
    name: "example",
    repository: "https://github.com/gitcoinco/id-staking-v2-app", // TODO: add env var for this
    oauthToken: process.env["GITHUB_ACCESS_TOKEN_FOR_AMPLIFY"],
    platform: "WEB_COMPUTE",
    buildSpec: `version: 1
applications:
  - frontend:
      phases:
        preBuild:
          commands:
            - yarn install
        build:
          commands:
            - yarn run build
      artifacts:
        baseDirectory: .next
        files:
          - '**/*'
      cache:
        paths:
          - .next/cache/**/*
          - node_modules/**/*
    appRoot: app
`,
    customRules: [
      {
        source: "/<*>",
        status: "404",
        target: "/index.html",
      },
    ],
    environmentVariables: {
      AMPLIFY_DIFF_DEPLOY: "false",
      AMPLIFY_MONOREPO_APP_ROOT: "app",
      ...environmentVariables
    },
  });

  const main = new aws.amplify.Branch("main", {
    appId: amplifyApp.id,
    branchName: "main",
  });
  const exampleDomainAssociation = new aws.amplify.DomainAssociation(
    "example",
    {
      appId: amplifyApp.id,
      domainName: domainName,
      subDomains: [
        {
          branchName: main.branchName,
          prefix: prefix,
        },
      ],
    }
  );

  return amplifyApp;
}
