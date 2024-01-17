import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";


export function createScorerEcsIamRole(secretsArn: string[], defaultTags: object) {
    return new aws.iam.Role("scorerExecRole", {
        assumeRolePolicy: JSON.stringify({
            Version: "2012-10-17",
            Statement: [
                {
                    Action: "sts:AssumeRole",
                    Effect: "Allow",
                    Sid: "",
                    Principal: {
                        Service: "ecs-tasks.amazonaws.com",
                    },
                },
            ],
        }),
        inlinePolicies: [
            {
                name: "allow_exec",
                policy: JSON.stringify({
                    Version: "2012-10-17",
                    Statement: [
                        {
                            Effect: "Allow",
                            Action: [
                                "ssmmessages:CreateControlChannel",
                                "ssmmessages:CreateDataChannel",
                                "ssmmessages:OpenControlChannel",
                                "ssmmessages:OpenDataChannel",
                            ],
                            Resource: "*",
                        },
                    ],
                }),
            },
            {
                name: "allow_iam_secrets_access",
                policy: JSON.stringify({
                    Version: "2012-10-17",
                    Statement: [
                        {
                            Action: ["secretsmanager:GetSecretValue"],
                            Effect: "Allow",
                            Resource: secretsArn,
                        },
                    ],
                }),
            },
        ],
        managedPolicyArns: [
            "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
        ],
        tags: {
            ...defaultTags
        },
    });
}
