import * as aws from "@pulumi/aws";
import { Input, interpolate } from "@pulumi/pulumi";

//////////////////////////////////////////////////////////////
// Scorer API Default
// Manage : 
//  - log group
//  - service sg 
//  - target group
//  - task definition
//  - service
//  - listener rule
//////////////////////////////////////////////////////////////


function getScorerSecurityGroup(
    name: string,
    vpcId: Input<string>,
    cidrBlock: Input<string>,
    defaultTags: Record<string, string>
) {
    //////////////////////////////////////////////////////////////
    // Security group 
    // do no group the security group definition & rules in the same resource =>
    // it will cause the sg to be destroyed and recreated everytime the rules change
    // By managing them separately is easier to update the security group rules even outside of this stack
    //////////////////////////////////////////////////////////////
    const securityGroup = new aws.ec2.SecurityGroup(name, {
        name: name,
        vpcId: vpcId,
        description: `Security Group for ${name} service.`,
        tags: {
            ...defaultTags,
            Name: name
        }
    });

    const sgIngressRule = new aws.ec2.SecurityGroupRule(`${name}-80`, {
        securityGroupId: securityGroup.id,
        type: "ingress",
        fromPort: 80,
        toPort: 80,
        protocol: "tcp",
        cidrBlocks: [cidrBlock] // TODO: manage sg group ingress better in the future to not allow the entire vpc
    }, {
        dependsOn: [securityGroup]
    });

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
    return securityGroup;
}

export function manageEcsService(
    name: string,
    logsRetention: number,
    networking: {
        vpcId: Input<string>,
        vpcCidr: Input<string>,
        subnets: Input<string[]>
    },
    containers: Input<string>,
    executionRoleArn: Input<string>,
    resources: { cpu: number, memory: number },
    cluster: aws.ecs.Cluster,
    desiredCount: number,
    alb: {
        name: Input<string>,
        ruleName: string,
        listenerArn: Input<string>,
        rulePriority: number,
        hostHeaders?: Array<string>,
        pathPattern?: Array<string>
    },
    asg: {
        maxCapacity?: number,
        minCapacity?: number,
    },
    alertTopicArn: Input<string>,
    defaultTags: Record<string, string>
) {
    //////////////////////////////////////////////////////////////
    // Log group 
    //////////////////////////////////////////////////////////////
    const serviceLogGroup = new aws.cloudwatch.LogGroup(name, {
        name: name,
        retentionInDays: logsRetention,
        tags: {
            ...defaultTags,
            Name: name,
            Scope: `LogGroup for ${name} service.`,
        },
    });

    const securityGroup = getScorerSecurityGroup(name, networking.vpcId, networking.vpcCidr, defaultTags);

    //////////////////////////////////////////////////////////////
    // ECS Task Definition, Service , ALB Target Group 
    //////////////////////////////////////////////////////////////
    const lbTargetGroup = new aws.lb.TargetGroup(name, {
        name: name,
        vpcId: networking.vpcId,
        healthCheck: {
            enabled: true,
            healthyThreshold: 3,
            interval: 30,
            matcher: "200",
            path: "/health",
            port: "traffic-port",
            protocol: "HTTP",
            timeout: 5,
            unhealthyThreshold: 5
        },
        port: 80,
        protocol: "HTTP",
        targetType: "ip",
        tags: {
            ...defaultTags,
            Name: name
        }
    });

    const taskDef = new aws.ecs.TaskDefinition(name, {
        family: name,
        containerDefinitions: containers,
        executionRoleArn: executionRoleArn,
        cpu: `${resources.cpu}`,
        memory: `${resources.memory}`,
        networkMode: "awsvpc",
        requiresCompatibilities: ["FARGATE"],
        tags: {
            ...defaultTags,
        }
    });

    const ecsService = new aws.ecs.Service(name, {
        cluster: cluster.arn,
        desiredCount: desiredCount,
        enableEcsManagedTags: true,
        enableExecuteCommand: false,
        launchType: "FARGATE",
        loadBalancers: [{
            containerName: "scorer",
            containerPort: 80,
            targetGroupArn: lbTargetGroup.arn
        }],
        name: name,
        networkConfiguration: {
            subnets: networking.subnets,
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


    const lbRule = new aws.lb.ListenerRule(alb.ruleName, {
        listenerArn: alb.listenerArn,
        priority: alb.rulePriority,
        actions: [{
            type: "forward",
            targetGroupArn: lbTargetGroup.arn
        }],
        conditions: [
            {
                hostHeader: {
                    values: alb.hostHeaders ? alb.hostHeaders : []
                }
            }, {
                pathPattern: {
                    values: alb.pathPattern ? alb.pathPattern : []
                }
            }
        ],
        tags: {
            ...defaultTags,
            Name: alb.name
        }
    });


    //////////////////////////////////////////////////////////////
    // ASG 
    //////////////////////////////////////////////////////////////

    const asgTarget = new aws.appautoscaling.Target(
        `autoscale-target-${name}`,
        {
            tags: { name: name },
            maxCapacity: asg.maxCapacity ? asg.maxCapacity : 20,
            minCapacity: asg.minCapacity ? asg.minCapacity : 2,
            resourceId: interpolate`service/${cluster.name}/${ecsService.name}`,
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

    if (alertTopicArn) {
        const cpuAlarm = new aws.cloudwatch.MetricAlarm(`CPUUtilization-${name}`, {
            tags: { name: `CPUUtilization-${name}` },
            alarmActions: [alertTopicArn],
            comparisonOperator: "GreaterThanThreshold",
            datapointsToAlarm: 1,
            dimensions: {
                ClusterName: cluster.name,
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
                alarmActions: [alertTopicArn],
                comparisonOperator: "GreaterThanThreshold",
                datapointsToAlarm: 1,
                dimensions: {
                    ClusterName: cluster.name,
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
            alarmActions: [alertTopicArn],
            comparisonOperator: "GreaterThanThreshold",
            datapointsToAlarm: 3,
            dimensions: {
                LoadBalancer: alb.name,
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
        task: taskDef,
        service: ecsService
    }
}




