import * as pulumi from "@pulumi/pulumi";
import { Input } from "@pulumi/pulumi";
import {
  ROUTE53_DOMAIN, ROOT_DOMAIN, SCORER_DOCKER_IMG, SCORER_SERVER_SSM_ARN,
  REDIS_URL, RDS_URL, RDS_RR_URL, AWS_REGION
} from './envs';

type ScorerEnvironmentConfig = {
  domain: Input<string>;
  rdsConnectionUrl: Input<string>;
  uiDomains: Input<string>;
  allowedHosts: Input<string>;
  csrfTrustedOrigins: Input<string>;
  redisCacheOpsConnectionUrl: Input<string>;
  debug?: Input<string>;
  readReplicaConnectionUrl?: Input<string>;
  passportPublicUrl?: Input<string>;
};

function getScorerSecrets(aws_sm_arn: string) {
  // This function maps the keys-value from the given secrets manager arn to the application secret envs
  return [
    {
      name: "SECRET_KEY",
      valueFrom: `${aws_sm_arn}:SECRET_KEY::`,
    },
    {
      name: "GOOGLE_OAUTH_CLIENT_ID",
      valueFrom: `${aws_sm_arn}:GOOGLE_OAUTH_CLIENT_ID::`,
    },
    {
      name: "GOOGLE_CLIENT_SECRET",
      valueFrom: `${aws_sm_arn}:GOOGLE_CLIENT_SECRET::`,
    },
    {
      name: "RATELIMIT_ENABLE",
      valueFrom: `${aws_sm_arn}:RATELIMIT_ENABLE::`,
    },
    {
      name: "TRUSTED_IAM_ISSUER",
      valueFrom: `${aws_sm_arn}:TRUSTED_IAM_ISSUER::`,
    },
    {
      name: "CERAMIC_CACHE_SCORER_ID",
      valueFrom: `${aws_sm_arn}:CERAMIC_CACHE_SCORER_ID::`,
    },
    {
      name: "FF_API_ANALYTICS",
      valueFrom: `${aws_sm_arn}:FF_API_ANALYTICS::`,
    },
    {
      name: "CGRANTS_API_TOKEN",
      valueFrom: `${aws_sm_arn}:CGRANTS_API_TOKEN::`,
    },
    {
      name: "S3_DATA_AWS_SECRET_KEY_ID",
      valueFrom: `${aws_sm_arn}:S3_DATA_AWS_SECRET_KEY_ID::`,
    },
    {
      name: "S3_DATA_AWS_SECRET_ACCESS_KEY",
      valueFrom: `${aws_sm_arn}:S3_DATA_AWS_SECRET_ACCESS_KEY::`,
    },
    {
      name: "S3_WEEKLY_BACKUP_BUCKET_NAME",
      valueFrom: `${aws_sm_arn}:S3_WEEKLY_BACKUP_BUCKET_NAME::`,
    },
    {
      name: "REGISTRY_API_READ_DB",
      valueFrom: `${aws_sm_arn}:REGISTRY_API_READ_DB::`,
    },
    {
      name: "STAKING_SUBGRAPH_API_KEY",
      valueFrom: `${aws_sm_arn}:STAKING_SUBGRAPH_API_KEY::`,
    },
  ]
}

function getScorerEnvs(config: ScorerEnvironmentConfig) {
  return [
    {
      name: "DEBUG",
      value: config.debug || "off",
    },
    {
      name: "DATABASE_URL",
      value: config.rdsConnectionUrl,
    },
    {
      name: "READ_REPLICA_0_URL",
      value: config.readReplicaConnectionUrl || config.rdsConnectionUrl,
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
      value: config.passportPublicUrl || "https://passport.gitcoin.co/",
    },
  ];
}

export function getScorerContainers(
  name: string,
  resources: { cpu: number, memory: number }
) {
  return pulumi.all([REDIS_URL, RDS_URL, RDS_RR_URL]).apply(([_REDIS_URL, _RDS_URL, _RDS_RR_URL]) => {
    const environments = getScorerEnvs({
      allowedHosts: JSON.stringify([ROUTE53_DOMAIN, "*"]),
      domain: ROUTE53_DOMAIN,
      csrfTrustedOrigins: JSON.stringify([`https://${ROUTE53_DOMAIN}`]),
      rdsConnectionUrl: _RDS_URL,
      readReplicaConnectionUrl: _RDS_RR_URL,
      redisCacheOpsConnectionUrl: _REDIS_URL,
      uiDomains: JSON.stringify([
        "scorer." + ROOT_DOMAIN,
        "www.scorer." + ROOT_DOMAIN,
      ]),
      debug: "off",
      passportPublicUrl: "https://passport.gitcoin.co/",
    });

    return JSON.stringify([{
      name: "scorer",
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
      image: SCORER_DOCKER_IMG,
      cpu: resources.cpu,
      memory: resources.memory,
      links: [],
      essential: true,
      portMappings: [{
        containerPort: 80,
        hostPort: 80,
        protocol: "tcp"
      }],
      environment: environments,
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": name, // `${serviceLogGroup.name}`,
          "awslogs-region": AWS_REGION, // `${regionId}`,
          "awslogs-create-group": "true",
          "awslogs-stream-prefix": "scorer"
        }
      },
      secrets: getScorerSecrets(SCORER_SERVER_SSM_ARN),
      mountPoints: [],
      volumesFrom: []
    }]);
  })
};