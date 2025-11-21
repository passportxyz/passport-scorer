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

### Actual Implementation Architecture
```typescript
// Two focused files with clean separation:

// routing-utils.ts - Infrastructure primitives:
createLambdaFunction()      // Lambda with Docker support (NOT buildLambdaFunction)
createLambdaTargetGroup()   // Target group with permissions
createListenerRule()        // Simple single-target routing
createWeightedListenerRule() // Multi-target weighted routing with stickiness
getRoutingPercentages()     // Environment-based config (staging=100% Rust, prod=0%)

// routing-rules.ts - Application routing logic:
configureAllRouting()       // ALL listener rules in ONE place (no more conflicts!)
```

## Implementation Steps

### Step 1: Create New Infrastructure Functions ✅ COMPLETED

Created TWO files (not one generic routing.ts):

1. **routing-utils.ts** - See actual implementation in `infra/lib/scorer/routing-utils.ts`
2. **routing-rules.ts** - See actual implementation in `infra/lib/scorer/routing-rules.ts`

Key differences from original plan:
- Function is named `createLambdaFunction` NOT `buildLambdaFunction`
- Takes `dockerCommand` parameter NOT `dockerCmd`
- Uses `imageUri` NOT `code` for Docker images
- Target group creation includes VPC ID parameter
- Weighted rules use `pulumi.Output<string>` for ARNs, not plain strings


### Step 2: Refactor ALL 15 Call Sites (~30% COMPLETED)

#### ✅ COMPLETED: V2 Stamps Score Endpoint

**Before** (in `infra/aws/v2/index.ts`):
```typescript
buildHttpLambdaFn({
  name: "passport-v2-stamp-score",
  dockerCmd: ["v2.aws_lambdas.stamp_score_GET.handler"],
  listenerPriority: 2023,
  // ... other params
});
```

**After** (ACTUAL implementation):
```typescript
import { createLambdaFunction, createLambdaTargetGroup } from "../../lib/scorer/routing-utils";

// Create Lambda and target group - NO routing rules here!
const v2StampScoreLambda = createLambdaFunction({
  name: "passport-v2-stamp-score",
  dockerImage: dockerLambdaImage,
  dockerCommand: ["v2.aws_lambdas.stamp_score_GET.handler"], // Note: dockerCommand not dockerCmd
  // ... Lambda params
});

const stampScoreTargetGroup = createLambdaTargetGroup(
  stampScoreLambda,
  "l-passport-v2-stamp-score"
);

// NO ROUTING RULES in individual files anymore!
// Routing is ALL handled centrally in routing-rules.ts

// Just return target groups:
return {
  pythonV2StampScore: v2StampScoreTargetGroup,
  pythonV2ModelScore: v2ModelScoreTargetGroup,
};
```

### Step 3: Update rust-scorer.ts ✅ COMPLETED

Deleted ALL listener rule creation (lines 189-512 removed). Now only:
- Creates Lambda and target groups
- Returns target groups: `{ rustScorer, rustScorerInternal }`
- NO listener rules whatsoever

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

## Key Architectural Change: Centralized Routing

**Before**: Each Lambda file created its own listener rules → Priority conflicts
**After**: ALL routing in `routing-rules.ts` → No conflicts, single source of truth

## Benefits of This Approach

✅ **Clean Architecture**: Proper separation of concerns (Lambdas vs routing)
✅ **No More Conflicts**: Each priority has exactly ONE rule
✅ **Explicit Control**: ALL routing visible in one file
✅ **Future Proof**: Easy to add canary, blue-green deployments
✅ **Smaller Codebase**: Deleted 300+ lines from rust-scorer.ts alone

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