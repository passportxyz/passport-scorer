import { LogGroup } from "@pulumi/aws/cloudwatch/logGroup";
import { Cluster } from "@pulumi/awsx/ecs";
import { Role } from "@pulumi/aws/iam/role";
import * as awsx from "@pulumi/awsx";
import { Input } from "@pulumi/pulumi";
import { TargetGroup } from "@pulumi/aws/lb";

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;

export type ScorerService = {
  dockerImageScorer: Input<string>;
  dockerImageVerifier: Input<string>;
  executionRole: Role;
  cluster: Cluster;
  logGroup: LogGroup;
  subnets: Input<Input<string>[]>;
  targetGroup: TargetGroup;
};

export type ScorerEnvironmentConfig = {
  domain: Input<string>;
  rdsConnectionUrl: Input<string>;
  uiDomains: Input<string>;
  allowedHosts: Input<string>;
  csrfTrustedOrigins: Input<string>;
  redisCacheOpsConnectionUrl: Input<string>;
};

export const secrets = [
  {
    name: "SECRET_KEY",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:SECRET_KEY::`,
  },
  {
    name: "GOOGLE_OAUTH_CLIENT_ID",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:GOOGLE_OAUTH_CLIENT_ID::`,
  },
  {
    name: "GOOGLE_CLIENT_SECRET",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:GOOGLE_CLIENT_SECRET::`,
  },
  {
    name: "RATELIMIT_ENABLE",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:RATELIMIT_ENABLE::`,
  },
  {
    name: "TRUSTED_IAM_ISSUER",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:TRUSTED_IAM_ISSUER::`,
  },
  {
    name: "CERAMIC_CACHE_SCORER_ID",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:CERAMIC_CACHE_SCORER_ID::`,
  },
  {
    name: "FF_API_ANALYTICS",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:FF_API_ANALYTICS::`,
  },
  {
    name: "FF_DEDUP_WITH_LINK_TABLE",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:FF_DEDUP_WITH_LINK_TABLE::`,
  },
  {
    name: "CGRANTS_API_TOKEN",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:CGRANTS_API_TOKEN::`,
  },
  {
    name: "S3_DATA_AWS_SECRET_KEY_ID",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:S3_DATA_AWS_SECRET_KEY_ID::`,
  },
  {
    name: "S3_DATA_AWS_SECRET_ACCESS_KEY",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:S3_DATA_AWS_SECRET_ACCESS_KEY::`,
  },
  {
    name: "S3_WEEKLY_BACKUP_BUCKET_NAME",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:S3_WEEKLY_BACKUP_BUCKET_NAME::`,
  },
  {
    name: "REGISTRY_API_READ_DB",
    valueFrom: `${SCORER_SERVER_SSM_ARN}:REGISTRY_API_READ_DB::`,
  },
];

export function getEnvironment(config: ScorerEnvironmentConfig) {
  return [
    {
      name: "DEBUG",
      value: "on",
    },
    {
      name: "DATABASE_URL",
      value: config.rdsConnectionUrl,
    },
    {
      name: "READ_REPLICA_0_URL",
      value: config.rdsConnectionUrl,
    },
    {
      name: "UI_DOMAINS",
      value: config.uiDomains,
    },
    {
      name: "ALLOWED_HOSTS",
      value: JSON.stringify([config.domain, "*"]),
    },
    {
      name: "CSRF_TRUSTED_ORIGINS",
      value: JSON.stringify([`https://${config.domain}`]),
    },
    {
      name: "CELERY_BROKER_URL",
      value: config.redisCacheOpsConnectionUrl,
    },
    {
      name: "CERAMIC_CACHE_CACAO_VALIDATION_URL",
      value: "http://localhost:8001/verify",
    },
    {
      name: "SECURE_SSL_REDIRECT",
      value: "off",
    },
    {
      name: "SECURE_PROXY_SSL_HEADER",
      value: JSON.stringify(["HTTP_X_FORWARDED_PROTO", "https"]),
    },
    {
      name: "LOGGING_STRATEGY",
      value: "structlog_json",
    },
    {
      name: "PASSPORT_PUBLIC_URL",
      value: "https://staging.passport.gitcoin.co/",
    },
  ];
}

export function createScorerECSService(
  name: string,
  config: ScorerService,
  envConfig: ScorerEnvironmentConfig
): awsx.ecs.FargateService {
  return new awsx.ecs.FargateService(name, {
    cluster: config.cluster,
    desiredCount: 1,
    subnets: config.subnets,
    loadBalancers: [
      {
        containerName: "scorer",
        containerPort: 80,
        targetGroupArn: config.targetGroup.arn,
      },
    ],
    taskDefinitionArgs: {
      logGroup: config.logGroup,
      executionRole: config.executionRole,
      containers: {
        scorer: {
          image: config.dockerImageScorer,
          memory: 4096,
          cpu: 4000,
          portMappings: [{ containerPort: 80, hostPort: 80 }],
          command: [
            "gunicorn",
            "-w",
            "4",
            "-k",
            "uvicorn.workers.UvicornWorker",
            "scorer.asgi:application",
            "-b",
            "0.0.0.0:80",
          ],
          links: [],
          secrets: secrets,
          environment: getEnvironment(envConfig),
          linuxParameters: {
            initProcessEnabled: true,
          },
        },
        verifier: {
          image: config.dockerImageVerifier,
          memory: 512,
          links: [],
          portMappings: [
            {
              containerPort: 8001,
              hostPort: 8001,
            },
          ],
          environment: [
            {
              name: "VERIFIER_PORT",
              value: "8001",
            },
          ],
          linuxParameters: {
            initProcessEnabled: true,
          },
        },
      },
    },
  });
}
