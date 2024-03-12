import * as aws from "@pulumi/aws";

export function createStakingApp() {
  const example = new aws.amplify.App("example", {
    name: "example",
    repository: "https://github.com/gitcoinco/id-staking-v2-app", // TODO: add env var for this
    oauthToken: process.env["GITHUB_ACCESS_TOKEN_FOR_AMPLIFY"],
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
    },
  });

  const main = new aws.amplify.Branch("main", {
    appId: example.id,
    branchName: "main",
  });
  const exampleDomainAssociation = new aws.amplify.DomainAssociation(
    "example",
    {
      appId: example.id,
      domainName: "review.passport.xyz",
      subDomains: [
        {
          branchName: main.branchName,
          prefix: "",
        },
        {
          branchName: main.branchName,
          prefix: "www",
        },
      ],
    }
  );

  return {
    app: example,
  };
}
