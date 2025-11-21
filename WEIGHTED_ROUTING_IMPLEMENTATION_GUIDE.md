# Weighted Routing Implementation Guide

## 🚧 IMPLEMENTATION IN PROGRESS - STATUS UPDATE

**Last Updated**: 2024-11-21
**Progress**: ~30% Complete - Core infrastructure done, V2 API refactored

### ✅ What's Been Completed

1. **Created routing infrastructure** (DONE)
   - `infra/lib/scorer/routing-utils.ts` - Helper functions for Lambda/target group creation
   - `infra/lib/scorer/routing-rules.ts` - Centralized routing configuration

2. **Refactored V2 API endpoints** (DONE)
   - `infra/aws/v2/index.ts` - Separated Lambda/target group from routing
   - Returns target groups for central routing

3. **Refactored Rust Scorer** (DONE)
   - `infra/aws/v2/rust-scorer.ts` - Removed all listener rules (deleted lines 189-512)
   - Now only creates Lambda and target groups

### ⚠️ What Still Needs to Be Done

1. **Ceramic Cache endpoints** (7 lambdas) - `infra/aws/index.ts`
2. **Embed endpoints** (3 lambdas) - `infra/aws/embed/index.ts`
3. **App API endpoints** (2 lambdas) - `infra/aws/app_api/index.ts`
4. **Wire up central routing** - Call `configureAllRouting` from main index.ts
5. **Delete old functions** - Remove `buildHttpLambdaFn` and `createEmbedLambdaGeneric`

### 🔄 How to Continue

See "Implementation Steps - Detailed" section below for exact patterns to follow.
The V2 API refactoring in `infra/aws/v2/index.ts` provides the template.

---

## Executive Summary

The Rust scorer weighted routing is blocked by AWS ALB constraints. This guide provides the complete solution using a clean refactoring approach that separates Lambda creation, target groups, and routing rules into independent functions.

## The Blocker

**AWS Constraint**: Each ALB listener can only have ONE rule at each priority number.

**Current Problem**: Both Python Lambda creation (`buildHttpLambdaFn`) and Rust weighted routing try to create rules at the same priorities (2023, 1001-1004, 2100-2103).

## Solution: Clean Function Separation

### Current Anti-Pattern
```typescript
buildHttpLambdaFn() does three things:
1. Creates Lambda
2. Creates target group
3. Creates listener rule (causes conflicts!)
```

### New Clean Architecture
```typescript
// Separate, composable functions:
buildLambdaFunction()      // Just Lambda
createLambdaTargetGroup()   // Just target group
createListenerRule()        // Simple routing
createWeightedListenerRule() // Weighted routing
```

## Implementation Steps

### Step 1: Create New Infrastructure Functions (3-4 hours)

Create `infra/lib/scorer/routing.ts`:

```typescript
import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

// Extract from buildHttpLambdaFn
export function buildLambdaFunction(args: {
  name: string,
  dockerImage: string,
  environment: any,
  // ... other Lambda config
}): aws.lambda.Function {
  // Just create Lambda, nothing else
  return new aws.lambda.Function(name, {
    // ... Lambda configuration
  });
}

// New function for target groups
export function createLambdaTargetGroup(
  lambda: aws.lambda.Function,
  name: string
): aws.lb.TargetGroup {
  const targetGroup = new aws.lb.TargetGroup(name, {
    targetType: "lambda",
    // ... config
  });

  // Grant permission and attach
  const permission = new aws.lambda.Permission(/*...*/);
  const attachment = new aws.lb.TargetGroupAttachment(/*...*/);

  return targetGroup;
}

// Simple routing for Python-only endpoints
export function createListenerRule(args: {
  targetGroup: aws.lb.TargetGroup,
  priority: number,
  conditions: any[],
  listenerArn: pulumi.Output<string>
}): aws.lb.ListenerRule {
  return new aws.lb.ListenerRule(/*...*/);
}

// Weighted routing for dual implementations
export function createWeightedListenerRule(args: {
  targetGroups: Array<{arn: string, weight: number}>,
  priority: number,
  conditions: any[],
  listenerArn: pulumi.Output<string>
}): aws.lb.ListenerRule {
  return new aws.lb.ListenerRule(name, {
    listenerArn: args.listenerArn,
    priority: args.priority,
    conditions: args.conditions,
    actions: [{
      type: "forward",
      forward: {
        targetGroups: args.targetGroups,
        stickiness: {
          enabled: true,
          duration: 3600  // 1 hour
        }
      }
    }]
  });
}

// Helper to determine if Rust is enabled
export function isRustEnabled(stack: string): boolean {
  const percentages = getRoutingPercentages(stack);
  return percentages.rust > 0;
}
```

### Step 2: Refactor ALL 15 Call Sites (5-6 hours)

#### Example: V2 Stamps Score Endpoint

**Before** (in `infra/aws/v2/index.ts`):
```typescript
buildHttpLambdaFn({
  name: "passport-v2-stamp-score",
  listenerPriority: 2023,
  // ... other params
});
```

**After**:
```typescript
import { buildLambdaFunction, createLambdaTargetGroup,
         createListenerRule, createWeightedListenerRule,
         isRustEnabled } from "../../lib/scorer/routing";

// Create Lambda and target group
const stampScoreLambda = buildLambdaFunction({
  name: "passport-v2-stamp-score",
  // ... Lambda params
});

const stampScoreTargetGroup = createLambdaTargetGroup(
  stampScoreLambda,
  "l-passport-v2-stamp-score"
);

// Conditional routing based on Rust enablement
if (isRustEnabled(stack)) {
  // Get Rust target group (created in rust-scorer.ts)
  const rustTargetGroup = // ... get reference

  createWeightedListenerRule({
    targetGroups: [
      { arn: stampScoreTargetGroup.arn, weight: routingPercentages.python },
      { arn: rustTargetGroup.arn, weight: routingPercentages.rust }
    ],
    priority: 2023,
    conditions: [/* path, method, host conditions */],
    listenerArn: httpsListener.arn
  });
} else {
  createListenerRule({
    targetGroup: stampScoreTargetGroup,
    priority: 2023,
    conditions: [/* same conditions */],
    listenerArn: httpsListener.arn
  });
}
```

### Step 3: Update rust-scorer.ts (1 hour)

Remove ALL listener rule creation (lines 191-513). Keep only:
- Lambda creation
- Target group creation
- Export target groups for use in weighted routing

### Step 4: Delete Old Functions

Once all call sites are updated:
- Delete `buildHttpLambdaFn` entirely
- Delete `createEmbedLambdaGeneric` entirely

## Endpoints Requiring Changes

### Dual Implementation (Need Weighted Routing)

| Priority | Endpoint | Method | File Location |
|----------|----------|--------|---------------|
| 2023 | `/v2/stamps/*/score/*` | GET | infra/aws/v2/index.ts:116 |
| 1001 | `/ceramic-cache/score/*` | POST | infra/aws/index.ts |
| 1002 | `/ceramic-cache/stamps/bulk` | POST | infra/aws/index.ts:1308 |
| 2100 | `/internal/embed/stamps/*` | POST | infra/aws/embed/index.ts:16 |
| 2101 | `/internal/embed/validate-api-key` | GET | infra/aws/embed/index.ts:35 |
| 2103 | `/internal/embed/score/*/*` | GET | infra/aws/embed/index.ts:54 |

### Python-Only (Simple Routing)

All other endpoints keep simple routing - just refactor to use new functions.

## Routing Configuration

Current settings in `rust-scorer.ts`:
```typescript
staging: 100,     // 100% Rust
review: 100,      // 100% Rust
production: 0,    // 0% Rust (safe default)
```

## Testing Checklist

- [ ] Deploy to staging with Rust disabled (0%)
- [ ] Verify all Python endpoints work
- [ ] Deploy to staging with Rust enabled (100%)
- [ ] Verify no priority conflicts
- [ ] Test weighted routing at 50/50
- [ ] Verify session stickiness
- [ ] Test rollback (100% → 0%)
- [ ] Monitor metrics during transitions

## Rollback Procedure

1. Set `production: 0` in routing configuration
2. Redeploy via Pulumi
3. All traffic immediately routes to Python

## Timeline

- **Total: 11-14 hours**
- Can be done incrementally (endpoint by endpoint)
- Must be deployed as single change to avoid conflicts

## Benefits of This Approach

✅ **Clean Architecture**: Proper separation of concerns
✅ **No Tech Debt**: Delete old functions entirely
✅ **Explicit Control**: Clear routing logic at each endpoint
✅ **Future Proof**: Easy to add canary, blue-green deployments
✅ **Smaller Codebase**: Actually removing code, not adding

## Implementation Steps - Detailed

### For Each Remaining Endpoint

Follow this exact pattern from the V2 API refactoring:

#### Before (Old Pattern)
```typescript
buildHttpLambdaFn({
  name: "some-lambda",
  dockerCmd: ["handler.path"],
  httpListenerRulePaths: [...],
  listenerPriority: 1234,
  ...
}, alarmConfigurations);
```

#### After (New Pattern)
```typescript
// 1. Create the Lambda
const someLambda = createLambdaFunction({
  name: "some-lambda",
  dockerImage: dockerLambdaImage,
  dockerCommand: ["handler.path"],
  environment: lambdaSettings.environment,
  memorySize: 256,
  timeout: 60,
  roleArn: httpLambdaRole.arn,
  securityGroupIds: [privateSubnetSecurityGroup.id],
  subnetIds: vpcPrivateSubnetIds,
});

// 2. Create the target group
const someTargetGroup = createLambdaTargetGroup({
  name: "l-some-lambda",
  lambda: someLambda,
  vpcId: pulumi.output(aws.ec2.getVpc({ default: true })).apply((vpc) => vpc.id),
});

// 3. Return or export the target group for central routing
```

### Ceramic Cache Endpoints to Refactor

In `infra/aws/index.ts`, find and refactor these 7 calls:
1. `l-cc-v1-st-bulk-POST-0` (priority 1002) - DUAL IMPLEMENTATION
2. `l-cc-v1-st-bulk-PATCH-0` (priority 1003)
3. `l-cc-v1-st-bulk-DELETE-0` (priority 1004)
4. `l-cc-v1-score-POST-0` (priority 1001)
5. `l-cc-v1-score-GET-0` (priority 1006) - DUAL IMPLEMENTATION
6. `l-submit-passport` (priority 1000)
7. `l-analysis` (priority 1005)

### Embed Endpoints to Refactor

In `infra/aws/embed/index.ts`, refactor these 3 calls to `createEmbedLambdaGeneric`:
1. `embed-st` (priority 2100) - DUAL IMPLEMENTATION
2. `embed-rl` (priority 2101) - DUAL IMPLEMENTATION
3. `embed-gs` (priority 2103) - DUAL IMPLEMENTATION

### Wiring Central Routing

In `infra/aws/index.ts`, at the end after all Lambda/target groups are created:

```typescript
import { configureAllRouting } from "../lib/scorer/routing-rules";

// After all target groups are created...
const targetGroups = {
  pythonV2StampScore: v2Api.pythonV2StampScore,
  pythonV2ModelScore: v2Api.pythonV2ModelScore,
  rustScorer: rustScorer?.rustScorer,
  rustScorerInternal: rustScorer?.rustScorerInternal,
  pythonCeramicCacheBulkPost: ceramicCacheBulkPostTargetGroup,
  // ... collect all target groups
};

configureAllRouting({
  publicListener: httpsListener,
  internalListener: internalHttpsListener,
  targetGroups,
  stack,
  envName: `${process.env.ENV_NAME || "dev"}`,
});
```

### Cleanup

After all refactoring is complete:
1. Delete `buildHttpLambdaFn` from `infra/lib/scorer/new_service.ts`
2. Delete `createEmbedLambdaGeneric` from `infra/aws/embed/lambda_generic.ts`
3. Remove their imports from all files

## Testing Checklist

- [ ] Run `pulumi preview` to ensure no infrastructure changes (only code reorganization)
- [ ] Deploy to staging with Rust disabled (0%)
- [ ] Verify all Python endpoints still work
- [ ] Enable Rust (100%) in staging
- [ ] Verify no ALB priority conflicts
- [ ] Test weighted routing at 50/50
- [ ] Monitor for proper session stickiness

## Questions?

Contact the Rust scorer team for clarification on any implementation details.

## Implementation Notes from Current Session

- The `createLambdaFunction` helper expects `dockerCommand` not `dockerCmd`
- Target groups need VPC ID - use the default VPC pattern shown above
- The V2 API returns target groups from its function for use in central routing
- Rust scorer's listener rules (lines 189-512) have been deleted
- The routing-rules.ts file is ready but needs target group references wired up