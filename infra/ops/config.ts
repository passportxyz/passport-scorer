import * as pulumi from "@pulumi/pulumi";

export const stack = pulumi.getStack(); // values : review, staging & production

// export const coreInfraOutputs = new pulumi.StackReference(
//   `passportxyz/core-infra/${stack}`
// );

// export const coreRdsSecretArn = coreInfraOutputs.getOutput("coreRdsSecretArn");
// export const coreVpcId = coreInfraOutputs.getOutput("vpcId");
// export const corePrivateSubnetIds =
//   coreInfraOutputs.getOutput("privateSubnetIds");

// export const rdsSecretArn = coreInfraOutputs.getOutput("rdsSecretArn");
