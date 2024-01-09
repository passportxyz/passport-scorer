import * as aws from "@pulumi/aws";
import { Input, interpolate } from "@pulumi/pulumi";

//////////////////////////////////////////////////////////////
// Scorer API Default
// Manage : 
//  - log group
//  - service sg 
//  - service role
//  - target group
//  - task definition
//  - service
//  - listener rule
//////////////////////////////////////////////////////////////

// input : service name, cluster 

type AwsTags = Record<string, string>;

type SgConfig = {
    fromPort: number,
    toPort: number,
    protocol: string,
    cidrBlocks: Array<string>
}

type InlinePolicy= {
    name: string,
    policy: string
}

type roleConfig = {
    managedPolicyArns: Array<string>,
    inlinePolicies: Array<InlinePolicy>
}

// type PortMapping = {
//     containerPort: number,
//     hostPort: number,
//     protocol: string
// }
// type Environment = {
//     name: string,
//     value: string
// }
// type Secret = {
//     name: string,
//     value: string
// }
// type ContainerSpecs = {
//     name: string,
//     image: string, 
//     cpu: string, 
//     memory: string,
//     links: Array<string>,
//     essential: boolean,
//     portMappings: Array<PortMapping>,
//     environment: Array<Environment>,
//     logConfiguration: Object,
//     secrets: Array<Secret>,
//     mountPoints: Array<any>,
//     volumesFrom: Array<any>
// }

type serviceLbConfig = {
    containerName: string,
    containerPort: number
}

export type serviceConfig = {
    logsRetention: number,
    networking: {
        vpcId: Input<string>,
        subnets: Input<Array<string>>,
        securityGroup: Array<SgConfig>
    }
    role: roleConfig,
    // Array<ContainerSpecs>, //any //  TODO: fix this
    containers: any, 
    resources: {
        cpu: string,
        memory: string
    },
    cluster: {
        arn: Input<string>,
        name: Input<string>
    },
    targetGroup: {
        healthCheck: {
            enabled: boolean,
            healthyThreshold: number,
            interval: number,
            matcher: string,
            path: string,
            port: string,
            protocol: string,
            timeout: number,
            unhealthyThreshold: number
        },
        port : number,
        protocol: string,
        targetType: string
    },
    service: {
        desiredCount: number,
        loadBalancers: Array<serviceLbConfig>
    },
    lbRule: {
        name: string,
        lbName: Input<string>,
        listenerArn: Input<string>,
        hostHeaders?: Array<string>
    },
    asg: {
        maxCapacity?: number,
        minCapacity?: number,
    },
    alertTopicArn: Input<string>
}

// output {
//  service, task, sg, loggroup, role 
// }

export function manageEcsService(name: string, serviceConfig: serviceConfig, defaultTags: AwsTags){
    //////////////////////////////////////////////////////////////
    // Log group 
    //////////////////////////////////////////////////////////////
    const serviceLogGroup = new aws.cloudwatch.LogGroup(name , {
        name: name,
        retentionInDays: serviceConfig.logsRetention,
        tags: {
            ...defaultTags,
            Name: name,
            Scope: `LogGroup for ${name} service.`,
        },
    });

    //////////////////////////////////////////////////////////////
    // Security group 
    // do no group the security group definition & rules in the same resource =>
    // it will cause the sg to be destroyed and recreated everytime the rules change
    // By managing them separately is easier to update the security group rules even outside of this stack
    //////////////////////////////////////////////////////////////
    const securityGroup = new aws.ec2.SecurityGroup(name, {
        name: name,
        vpcId: serviceConfig.networking.vpcId,
        description: `Security Group for ${name} service.`,
        tags: {
            ...defaultTags,
            Name: name
        }
    });

    const sgIngressRule = serviceConfig.networking.securityGroup.forEach(sgRule => 
        new aws.ec2.SecurityGroupRule(`${name}-${sgRule.fromPort}`, {
            securityGroupId : securityGroup.id,
            type: "ingress",
            fromPort: sgRule.fromPort,
            toPort: sgRule.toPort,
            protocol: sgRule.protocol,
            cidrBlocks: sgRule.cidrBlocks
        }, {
            dependsOn: [securityGroup]
        })
    );

    const sgEgressRule = new aws.ec2.SecurityGroupRule(`${name}-egress-all`, {
        securityGroupId: securityGroup.id,
        type: "egress",
        fromPort: 0,
        toPort: 0,
        protocol: "-1",
        cidrBlocks: ["0.0.0.0/0"]
    }, {
        dependsOn: [securityGroup]
    });

    //////////////////////////////////////////////////////////////
    // AWS IAM Role
    //////////////////////////////////////////////////////////////
    const serviceRole = new aws.iam.Role(`${name}`, {
        name: name, 
        assumeRolePolicy: JSON.stringify({
            Version: "2012-10-17",
            Statement: [
                {
                    Action: "sts:AssumeRole",
                    Effect: "Allow",
                    Sid: "AllowEcsAssume",
                    Principal: {
                        Service: "ecs-tasks.amazonaws.com",
                    },
                },
            ],
        }),
        managedPolicyArns: serviceConfig.role.managedPolicyArns,
        inlinePolicies: serviceConfig.role.inlinePolicies,
        tags: {
            ...defaultTags,
            Name: name
        }
    });

    //////////////////////////////////////////////////////////////
    // ECS Task Definition, Service , ALB Target Group 
    //////////////////////////////////////////////////////////////
    const taskDef = new aws.ecs.TaskDefinition(name, { 
        family: name,
        containerDefinitions: serviceConfig.containers,
        executionRoleArn: serviceRole.arn,
        cpu: serviceConfig.resources.cpu,
        memory: serviceConfig.resources.memory,
        networkMode: "awsvpc",
        requiresCompatibilities: ["FARGATE"],
        tags:{
            ...defaultTags,
        }
    });
    
    const lbTargetGroup = new aws.lb.TargetGroup(name, {
        name: name,
        vpcId: serviceConfig.networking.vpcId,
        ...serviceConfig.targetGroup,
        // healthCheck: {
        //     enabled: true,
        //     healthyThreshold: 3,
        //     interval: 30,
        //     matcher: "200",
        //     path: "/health",
        //     port: "traffic-port",
        //     protocol: "HTTP",
        //     timeout: 5,
        //     unhealthyThreshold: 5
        // },
        // port: 80,
        // protocol: "HTTP",
        // targetType: "ip",
        tags: {
            ...defaultTags,
            Name: name
        }
    });

    const ecsService =  new aws.ecs.Service(name, {
        cluster: serviceConfig.cluster.arn,
        desiredCount: 2,
        enableEcsManagedTags: true,
        enableExecuteCommand: false,
        launchType: "FARGATE",
        loadBalancers: [{
            containerName: serviceConfig.service.loadBalancers[0].containerName,
            containerPort: serviceConfig.service.loadBalancers[0].containerPort,
            targetGroupArn: lbTargetGroup.arn
        }],
        name: name,
        networkConfiguration: {
            subnets: serviceConfig.networking.subnets,
            securityGroups: [securityGroup.id]
        },
        propagateTags: "TASK_DEFINITION",
        taskDefinition: taskDef.arn,
        tags: {
            ...defaultTags,
            Name: name
        }
    }, {
        dependsOn: [lbTargetGroup, taskDef]
    });


    const lbRule = new aws.lb.ListenerRule(serviceConfig.lbRule.name, {
        listenerArn: serviceConfig.lbRule.listenerArn,
        priority: 5000,
        actions: [{
            type: "forward",
            targetGroupArn: lbTargetGroup.arn
        }],
        conditions: [{
            hostHeader: {
                values: serviceConfig.lbRule.hostHeaders ? serviceConfig.lbRule.hostHeaders : []
            },
            // pathPattern: {[]}
        }],
        tags: {
            ...defaultTags,
            Name: serviceConfig.lbRule.name
        }
    });


    //////////////////////////////////////////////////////////////
    // ASG 
    //////////////////////////////////////////////////////////////

    const asgTarget = new aws.appautoscaling.Target(
        `autoscale-target-${name}`,
        {
          tags: { name: name },
          maxCapacity: serviceConfig.asg.maxCapacity ? serviceConfig.asg.maxCapacity : 20,
          minCapacity: serviceConfig.asg.minCapacity ? serviceConfig.asg.minCapacity : 2,
          resourceId: interpolate`service/${serviceConfig.cluster.name}/${ecsService.name}`,
          scalableDimension: "ecs:service:DesiredCount",
          serviceNamespace: "ecs",
        }
    );
    
    const ecsScorerServiceAutoscaling = new aws.appautoscaling.Policy(
        `autoscale-policy-${name}`,
        {
          policyType: "TargetTrackingScaling",
          resourceId: asgTarget.resourceId,
          scalableDimension: asgTarget.scalableDimension,
          serviceNamespace: asgTarget.serviceNamespace,
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
    
    if (serviceConfig.alertTopicArn) {
        const cpuAlarm = new aws.cloudwatch.MetricAlarm(`CPUUtilization-${name}`, {
          tags: { name: `CPUUtilization-${name}` },
          alarmActions: [serviceConfig.alertTopicArn],
          comparisonOperator: "GreaterThanThreshold",
          datapointsToAlarm: 1,
          dimensions: {
            ClusterName: serviceConfig.cluster.name,
            ServiceName: name,
          },
          evaluationPeriods: 1,
          metricName: "CPUUtilization",
          name: `CPUUtilization-${name}`,
          namespace: "AWS/ECS",
          period: 300,
          statistic: "Average",
          threshold: 80,
        });
    
        const memoryAlarm = new aws.cloudwatch.MetricAlarm(
          `MemoryUtilization-${name}`,
          {
            tags: { name: `MemoryUtilization-${name}` },
            alarmActions: [serviceConfig.alertTopicArn],
            comparisonOperator: "GreaterThanThreshold",
            datapointsToAlarm: 1,
            dimensions: {
              ClusterName: serviceConfig.cluster.name,
              ServiceName: name,
            },
            evaluationPeriods: 1,
            metricName: "MemoryUtilization",
            name: `MemoryUtilization-${name}`,
            namespace: "AWS/ECS",
            period: 900,
            statistic: "Average",
            threshold: 80,
          }
        );
    
        const http5xxAlarm = new aws.cloudwatch.MetricAlarm(`HTTP-5xx-${name}`, {
          tags: { name: `HTTP-5xx-${name}` },
          alarmActions: [serviceConfig.alertTopicArn],
          comparisonOperator: "GreaterThanThreshold",
          datapointsToAlarm: 3,
          dimensions: {
            LoadBalancer: serviceConfig.lbRule.lbName,
            TargetGroup: lbTargetGroup.name,
          },
          evaluationPeriods: 5,
          metricName: "HTTPCode_Target_5XX_Count",
          name: `HTTP-5xx-${name}`,
          namespace: "AWS/ApplicationELB",
          period: 60,
          statistic: "Sum",
          treatMissingData: "notBreaching",
        });
    }

    return {
        role: serviceRole,
        securityGroup: securityGroup,
        task : taskDef,
        service: ecsService
    }
}