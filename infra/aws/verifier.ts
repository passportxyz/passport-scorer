import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

type StackType = "review" | "staging" | "production";
export const stack: StackType = pulumi.getStack() as StackType;

const DEFAULT_TAGS = {
  Name: "verifier",
  Environment: "stack",
  Project: "passport-scorer",
};

const serviceResources = Object({
  review: {
    memory: 512, // 512 MiB
    cpu: 256, // 0.25 vCPU
  },
  staging: {
    memory: 1024, // 1 GB
    cpu: 512, // 0.5 vCPU
  },
  production: {
    memory: 1024, // 1 GB
    cpu: 512, // 0.5 vCPU
  },
});

const logsRetention = Object({
  review: 1,
  staging: 7,
  production: 30,
});

export const createVerifierService = ({
  vpcId,
  albListenerArn,
  privateAlbArnSuffix,
  albPriorityRule,
  pathPatterns,
  clusterArn,
  clusterName,
  dockerImage,
  vpcPrivateSubnets,
  snsTopicArn,
}: {
  vpcId: pulumi.Output<string>;
  albListenerArn: pulumi.Output<string>;
  privateAlbArnSuffix: pulumi.Output<string>;
  albPriorityRule: number;
  pathPatterns: string[];
  clusterArn: pulumi.Output<string>;
  clusterName: pulumi.Output<string>;
  dockerImage: string;
  vpcPrivateSubnets: pulumi.Output<string[]>;
  snsTopicArn: pulumi.Output<string>;
}) => {
  // Service Role
  const serviceRole = new aws.iam.Role("verifier-ecs-role", {
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Sid: "EcsAssume",
          Action: "sts:AssumeRole",
          Effect: "Allow",
          Principal: {
            Service: "ecs-tasks.amazonaws.com",
          },
        },
      ],
    }),
    managedPolicyArns: [
      "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    ],
    tags: {
      ...DEFAULT_TAGS,
    },
  });

  // Log Group
  const serviceLogGroup = new aws.cloudwatch.LogGroup("verifier", {
    name: "verifier",
    retentionInDays: logsRetention[stack],
    tags: {
      ...DEFAULT_TAGS,
    },
  });

  // Security Group
  const serviceSG = new aws.ec2.SecurityGroup(`verifier`, {
    name: `verifier`,
    vpcId: vpcId,
    description: `Security Group for verifier service.`,
    tags: {
      ...DEFAULT_TAGS,
      Name: `verifier`,
    },
  });

  const sgIngressRule80 = new aws.ec2.SecurityGroupRule(
    `verifier-80`,
    {
      securityGroupId: serviceSG.id,
      type: "ingress",
      fromPort: 80,
      toPort: 80,
      protocol: "tcp",
      cidrBlocks: ["10.0.0.0/16"], // For now allow from VPC
    },
    {
      dependsOn: [serviceSG],
    }
  );

  // Allow all outbound traffic
  const sgEgressRule = new aws.ec2.SecurityGroupRule(
    `verifier-all`,
    {
      securityGroupId: serviceSG.id,
      type: "egress",
      fromPort: 0,
      toPort: 0,
      protocol: "-1",
      cidrBlocks: ["0.0.0.0/0"],
    },
    {
      dependsOn: [serviceSG],
    }
  );

  // ALB Target Group & Listener
  const albTargetGroup = new aws.lb.TargetGroup(`verifier`, {
    name: `verifier`,
    vpcId: vpcId,
    healthCheck: {
      enabled: true,
      healthyThreshold: 3,
      interval: 30,
      matcher: "200",
      path: "/verifier/health",
      port: "traffic-port",
      protocol: "HTTP",
      timeout: 5,
      unhealthyThreshold: 5,
    },
    port: 80,
    protocol: "HTTP",
    targetType: "ip",
    tags: {
      ...DEFAULT_TAGS,
      Name: `verifier`,
    },
  });

  const albListenerRule = new aws.lb.ListenerRule(`verifier-http`, {
    listenerArn: albListenerArn,
    priority: albPriorityRule, // This needs to be grater than the priority number for passport-scroll-badge-service
    actions: [
      {
        type: "forward",
        targetGroupArn: albTargetGroup.arn,
      },
    ],
    conditions: [
      {
        pathPattern: {
          values: pathPatterns,
        },
      },
    ],
    tags: {
      ...DEFAULT_TAGS,
      Name: `verifier-http`,
    },
  });

  // Task Definition & service

  const containerDefinitions = JSON.stringify([
    {
      name: "verifier",
      image: dockerImage,
      cpu: serviceResources[stack]["cpu"],
      memory: serviceResources[stack]["memory"],
      links: [],
      essential: true,
      portMappings: [
        {
          containerPort: 80,
          hostPort: 80,
          protocol: "tcp",
        },
      ],
      logConfiguration: {
        logDriver: "awslogs",
        options: {
          "awslogs-group": "verifier", // "${serviceLogGroup.name}`,
          "awslogs-region": "us-west-2", // `${regionId}`,
          "awslogs-create-group": "true",
          "awslogs-stream-prefix": "verifier",
        },
      },
      mountPoints: [],
      volumesFrom: [],
      environment: [
        {
          name: "VERIFIER_PORT",
          value: "80",
        },
      ],
      secrets: [],
    },
  ]);

  const taskDefinition = new aws.ecs.TaskDefinition(`verifier`, {
    family: `verifier`,
    containerDefinitions,
    executionRoleArn: serviceRole.arn,
    cpu: serviceResources[stack]["cpu"],
    memory: serviceResources[stack]["memory"],
    networkMode: "awsvpc",
    requiresCompatibilities: ["FARGATE"],
    tags: {
      ...DEFAULT_TAGS,
      EcsService: `verifier`,
    },
  });

  const service = new aws.ecs.Service(
    `verifier`,
    {
      cluster: clusterArn,
      desiredCount: stack === "production" ? 2 : 1,
      enableEcsManagedTags: true,
      enableExecuteCommand: false,
      launchType: "FARGATE",
      loadBalancers: [
        {
          containerName: "verifier",
          containerPort: 80,
          targetGroupArn: albTargetGroup.arn,
        },
      ],
      name: `verifier`,
      networkConfiguration: {
        subnets: vpcPrivateSubnets,
        securityGroups: [serviceSG.id],
      },
      propagateTags: "TASK_DEFINITION",
      taskDefinition: taskDefinition.arn,
      tags: {
        ...DEFAULT_TAGS,
        Name: `verifier`,
      },
    },
    {
      dependsOn: [albTargetGroup, taskDefinition],
    }
  );

  // Auto Scaling

  const ecsAutoScalingTarget = new aws.appautoscaling.Target(
    "autoscaling_target",
    {
      maxCapacity: 10,
      minCapacity: 1,
      resourceId: pulumi.interpolate`service/${clusterName}/${service.name}`,
      scalableDimension: "ecs:service:DesiredCount",
      serviceNamespace: "ecs",
    }
  );

  const ecsAutoScalingPolicy = new aws.appautoscaling.Policy(
    "autoscaling-policy",
    {
      policyType: "TargetTrackingScaling",
      resourceId: ecsAutoScalingTarget.resourceId,
      scalableDimension: ecsAutoScalingTarget.scalableDimension,
      serviceNamespace: ecsAutoScalingTarget.serviceNamespace,
      targetTrackingScalingPolicyConfiguration: {
        predefinedMetricSpecification: {
          predefinedMetricType: "ECSServiceAverageCPUUtilization",
        },
        targetValue: 50,
        scaleInCooldown: 300,
        scaleOutCooldown: 300,
      },
    }
  );

  // Alerts
  // Send an alert on alb target  500
  const metricNamespace = "AWS/ApplicationELB";

  const http5xxTargetAlarm = new aws.cloudwatch.MetricAlarm(
    `HTTP-Target-5XX-verifier`,
    {
      tags: { name: `HTTP-Target-5XX-verifier` },
      name: `HTTP-Target-5XX-verifier`,
      alarmActions: [snsTopicArn],
      okActions: [snsTopicArn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 3,
      evaluationPeriods: 5,
      metricQueries: [
        {
          id: "m1",
          metric: {
            metricName: "RequestCount",
            dimensions: {
              LoadBalancer: privateAlbArnSuffix,
              TargetGroup: albTargetGroup.arnSuffix,
            },
            namespace: metricNamespace,
            period: 60,
            stat: "Sum",
          },
        },
        {
          id: "m2",
          metric: {
            metricName: "HTTPCode_Target_5XX_Count",
            dimensions: {
              LoadBalancer: privateAlbArnSuffix,
              TargetGroup: albTargetGroup.arnSuffix,
            },
            namespace: metricNamespace,
            period: 60,
            stat: "Sum",
          },
        },
        {
          expression: "m2 / m1",
          id: "e1",
          label: "Percent of target 5XX errors",
          returnData: true,
        },
      ],
      threshold: 0.1,
    }
  );

  // Alert on task count
  const runningTaskCountAlarm = new aws.cloudwatch.MetricAlarm(
    `RunningTaskCount-verifier`,
    {
      tags: { name: `RunningTaskCount-verifier` },
      alarmActions: [snsTopicArn],
      okActions: [snsTopicArn],
      comparisonOperator: "GreaterThanThreshold",
      datapointsToAlarm: 1,
      dimensions: {
        ClusterName: clusterName,
        ServiceName: service.name,
      },
      evaluationPeriods: 1,
      metricName: "RunningTaskCount",
      name: `RunningTaskCount-verifier`,
      namespace: "ECS/ContainerInsights",
      period: 300,
      statistic: "Average",
      threshold: 7,
    }
  );
  return {
    task: taskDefinition,
    service: service,
  };
};
