# Weighted Routing Infrastructure Analysis

## Current State Summary

### ✅ COMPLETED (30%)
1. **New infrastructure layer created**:
   - `infra/lib/scorer/routing-utils.ts` - Helper functions for Lambda/target group/routing creation
   - `infra/lib/scorer/routing-rules.ts` - Centralized routing configuration

2. **V2 API endpoints refactored**:
   - `infra/aws/v2/index.ts` - Separated Lambda/target group creation from routing
   - Uses `createLambdaFunction()` and `createLambdaTargetGroup()` from routing-utils
   - Returns target groups for central routing

3. **Rust scorer cleanup**:
   - `infra/aws/v2/rust-scorer.ts` - Removed listener rules (deleted 300+ lines)
   - Now only creates Lambda and target groups
   - **BUG FOUND**: References undefined `internalTargetGroup` variable

### ⚠️ IN PROGRESS / INCOMPLETE (70% remaining)

#### 1. Ceramic Cache Endpoints (7 lambdas) - NOT REFACTORED
**File**: `infra/aws/index.ts` (lines 1285-1492)
**Using**: Old `buildHttpLambdaFn()` pattern (monolithic)

Endpoints using old pattern:
- Priority 1000: `/submit-passport` (POST) - submit-passport-0
- Priority 1001: `/ceramic-cache/score/*` (POST) - cc-v1-score-POST-0  
- Priority 1002: `/ceramic-cache/stamps/bulk` (POST) - cc-v1-st-bulk-POST-0
- Priority 1003: `/ceramic-cache/stamps/bulk` (PATCH) - cc-v1-st-bulk-PATCH-0
- Priority 1004: `/ceramic-cache/stamps/bulk` (DELETE) - cc-v1-st-bulk-DELETE-0
- Priority 1006: `/ceramic-cache/score/*` (GET) - cc-v1-score-GET-0
- Priority 1007: `/ceramic-cache/stamps` (GET) - cc-v1-st-GET-0
- Priority 1012: `/passport/analysis/{address}` (GET) - passport-analysis-GET-0
- Priority 1015: `/ceramic-cache/weights` (GET) - cc-weights-GET-0

#### 2. Embed Endpoints (3 lambdas) - NOT REFACTORED
**File**: `infra/aws/embed/index.ts` (lines 6-73)
**Using**: `createEmbedLambdaGeneric()` (old pattern, creates listener rules)

Endpoints using old pattern:
- Priority 2100: `/internal/embed/stamps/*` (POST) - embed-st
- Priority 2101: `/internal/embed/validate-api-key` (GET) - embed-rl
- Priority 2103: `/internal/embed/score/*/*` (GET) - embed-gs

#### 3. App API Endpoints (2 lambdas) - NOT REFACTORED
**File**: `infra/aws/app_api/index.ts` (lines 6-54)
**Using**: `createAppLambdaGeneric()` (identical to embed, creates listener rules)

Endpoints using old pattern:
- Priority 5010: `/account/nonce` (GET/OPTIONS) - cc-nonce
- Priority 5020: `/ceramic-cache/authenticate` (POST/OPTIONS) - cc-auth

#### 4. Routing Configuration - NOT WIRED UP
The new `configureAllRouting()` function in `routing-rules.ts` is defined but **never called**.

Key issues:
- No integration with main `infra/aws/index.ts`
- Old listener rules from embed/app_api still being created independently
- V2 target groups created but routing rules still coming from old code paths

### 🐛 BUGS FOUND

#### Bug #1: Undefined Variable in rust-scorer.ts (Line 186)
```typescript
return {
  rustScorer: rustScorerTargetGroup,
  rustScorerInternal: internalTargetGroup,  // ❌ UNDEFINED!
};
```

**Impact**: V2 API index.ts will crash when it tries to use `internalTargetGroup`

**Root Cause**: The internal target group was never created in `createRustScorerLambda()` function

**Solution**: Need to create the internal target group for the internal ALB (embed endpoints)

#### Bug #2: No Internal ALB Integration
The `createRustScorerLambda()` function receives `internalHttpsListener` parameter but never uses it to create the internal target group.

**Missing Code**:
```typescript
// For internal ALB (embed endpoints)
const rustScorerInternalTargetGroup = new aws.lb.TargetGroup("l-passport-v2-rust-scorer-int", {
  name: "l-passport-v2-rust-scorer-int",
  targetType: "lambda",
  tags: { ...defaultTags, Name: "l-passport-v2-rust-scorer-int" },
});

// Grant permission for internal ALB
const rustScorerInternalPermission = new aws.lambda.Permission("withLb-passport-v2-rust-scorer-int", {
  action: "lambda:InvokeFunction",
  function: rustScorerLambda.name,
  principal: "elasticloadbalancing.amazonaws.com",
  sourceArn: rustScorerInternalTargetGroup.arn,
});

// Attach Lambda to internal target group
const rustScorerInternalAttachment = new aws.lb.TargetGroupAttachment(
  "lambdaTargetGroupAttachment-passport-v2-rust-scorer-int",
  {
    targetGroupArn: rustScorerInternalTargetGroup.arn,
    targetId: rustScorerLambda.arn,
  },
  { dependsOn: [rustScorerInternalPermission] }
);
```

## Architecture Analysis

### New Pattern (routing-utils.ts + routing-rules.ts)

**GOOD:**
- Clean separation of concerns
- All routing decisions in one place (`configureAllRouting()`)
- Eliminates ALB priority conflicts
- Enables weighted routing and session stickiness
- Environment-based configuration (staging=100% Rust, prod=0% Rust)

**CURRENT ISSUE:**
- Only partially integrated (V2 API done, rest still using old pattern)
- Leaves room for conflicts if old and new patterns run simultaneously

### Old Pattern (buildHttpLambdaFn, createEmbedLambdaGeneric)

**Problems:**
- Each function creates its own listener rules
- Creates ALB priority conflicts when multiple endpoints target same priority
- No support for weighted routing
- Rules are scattered across multiple files, hard to maintain

**Still used by:**
- All ceramic cache endpoints (7 lambdas)
- All embed endpoints (3 lambdas)
- All app API endpoints (2 lambdas)

## Integration Flow Currently Missing

What SHOULD happen when `infra/aws/index.ts` is deployed:

```
1. createV2Api() → creates Lambda + target groups
   ├─ Calls createRustScorerLambda() → creates Rust Lambda + target groups
   └─ Returns {pythonV2StampScore, pythonV2ModelScore}

2. createEmbedLambdaFunctions() → creates Embed Lambdas + rules (STILL OLD PATTERN)

3. createAppApiLambdaFunctions() → creates App API Lambdas + rules (STILL OLD PATTERN)

4. [MISSING] configureAllRouting() call with all target groups
   ├─ Would create V2 API weighted rules
   ├─ Would create Ceramic Cache rules
   ├─ Would create Embed rules
   └─ Would create App API rules
```

Currently step 4 never happens, so old listener rules still get created in steps 2-3.

## Target Groups Inventory

### Currently Created (but routing may conflict)

**V2 API** (in `infra/aws/v2/index.ts`):
- `l-passport-v2-model-score` (Python only)
- `l-passport-v2-stamp-score` (Python, conflicts with Rust routing)
- `l-passport-v2-rust-scorer` (Rust, created but routing not set up)
- `l-passport-v2-rust-scorer-int` (Rust internal, UNDEFINED BUG)

**Ceramic Cache** (in `infra/aws/index.ts`, via `buildHttpLambdaFn`):
- Implicit target groups created by buildHttpLambdaFn:
  - submit-passport-0-l-submit-passport-0
  - cc-v1-st-bulk-POST-0-l-cc-v1-st-bulk-POST-0
  - cc-v1-st-bulk-PATCH-0-l-cc-v1-st-bulk-PATCH-0
  - cc-v1-st-bulk-DELETE-0-l-cc-v1-st-bulk-DELETE-0
  - cc-v1-score-POST-0-l-cc-v1-score-POST-0
  - cc-v1-score-GET-0-l-cc-v1-score-GET-0
  - cc-weights-GET-0-l-cc-weights-GET-0
  - cc-v1-st-GET-0-l-cc-v1-st-GET-0
  - passport-analysis-GET-0-l-passport-analysis-GET-0

**Embed** (in `infra/aws/embed/index.ts`, via `createEmbedLambdaGeneric`):
- embed-st-lambda-tg
- embed-rl-lambda-target-group
- embed-gs-lambda-target-group

**App API** (in `infra/aws/app_api/index.ts`, via `createAppLambdaGeneric`):
- cc-nonce-lambda-tg
- cc-auth-lambda-target-group

### Need to be Refactored into routing-rules.ts

These should be exposed as named target groups in `TargetGroups` interface:
```typescript
export interface TargetGroups {
  // Already there:
  pythonV2StampScore?: aws.lb.TargetGroup;
  pythonV2ModelScore?: aws.lb.TargetGroup;
  rustScorer?: aws.lb.TargetGroup;
  rustScorerInternal?: aws.lb.TargetGroup;

  // NEED TO ADD:
  // Ceramic Cache
  pythonSubmitPassport?: aws.lb.TargetGroup;
  pythonCeramicCacheBulkPost?: aws.lb.TargetGroup;
  pythonCeramicCacheBulkPatch?: aws.lb.TargetGroup;
  pythonCeramicCacheBulkDelete?: aws.lb.TargetGroup;
  pythonCeramicCacheScore?: aws.lb.TargetGroup;
  pythonPassportAnalysis?: aws.lb.TargetGroup;
  pythonCeramicCacheWeights?: aws.lb.TargetGroup;  // Currently missing!
  pythonCeramicCacheStamps?: aws.lb.TargetGroup;

  // Embed
  pythonEmbedAddStamps?: aws.lb.TargetGroup;
  pythonEmbedValidateKey?: aws.lb.TargetGroup;
  pythonEmbedGetScore?: aws.lb.TargetGroup;

  // App API
  pythonAppApiEnsPrimary?: aws.lb.TargetGroup;
  pythonAppApiGithubPrimary?: aws.lb.TargetGroup;
}
```

## Code Organization Current State

### File Structure

```
infra/
├── aws/
│   ├── index.ts                     [MAIN - calls v2, embed, app_api]
│   ├── v2/
│   │   ├── index.ts                 [✅ REFACTORED - uses new utils]
│   │   └── rust-scorer.ts           [✅ MOSTLY - has undefined bug]
│   ├── embed/
│   │   ├── index.ts                 [❌ NEEDS REFACTOR]
│   │   ├── lambda_generic.ts        [OLD PATTERN - should delete]
│   │   └── rate_limit.ts            [Not involved in refactor]
│   └── app_api/
│       ├── index.ts                 [❌ NEEDS REFACTOR]
│       └── lambda_generic.ts        [OLD PATTERN - should delete]
│
└── lib/scorer/
    ├── routing-utils.ts             [✅ NEW - created, good shape]
    ├── routing-rules.ts             [✅ NEW - created, good shape]
    ├── new_service.ts               [OLD - contains buildHttpLambdaFn]
    ├── loadBalancer.ts              [Alarm config]
    ├── scheduledTasks.ts            [Not involved]
    └── ... other files
```

### Function Dependencies

```
buildHttpLambdaFn() [old, in new_service.ts]
├── Used by 9+ Lambda definitions in index.ts
├── Creates Lambda, target group, AND listener rule
└── SHOULD BE DELETED after refactor

createEmbedLambdaGeneric() [old, in embed/lambda_generic.ts]
├── Used by embed index.ts to create 3 Lambdas
├── Creates Lambda, target group, AND listener rule
└── SHOULD BE DELETED after refactor

createAppLambdaGeneric() [old, in app_api/lambda_generic.ts]
├── Just re-exports createEmbedLambdaGeneric
├── Used by app_api index.ts to create 2 Lambdas
└── SHOULD BE DELETED after refactor

createLambdaFunction() [NEW, in routing-utils.ts]
├── Creates Lambda only (clean)
├── Used by v2/index.ts
├── Should be used by embed/index.ts after refactor
└── Should be used by app_api/index.ts after refactor

createLambdaTargetGroup() [NEW, in routing-utils.ts]
├── Creates target group + permissions (clean)
├── Used by v2/index.ts
├── Should be used by embed/index.ts after refactor
└── Should be used by app_api/index.ts after refactor

configureAllRouting() [NEW, in routing-rules.ts]
├── Creates ALL listener rules in centralized location
├── Takes all target groups as input
├── Supports weighted routing for dual Python/Rust
├── Currently NOT CALLED from anywhere
└── Should be called from index.ts after all refactoring
```

## Summary of Work Needed

### Phase 1: Fix Immediate Bugs (CRITICAL)
- [ ] Add internal target group creation to rust-scorer.ts
- [ ] Test that rust-scorer exports both target groups correctly

### Phase 2: Refactor Ceramic Cache Endpoints
- [ ] Extract 9 ceramic cache Lambdas from buildHttpLambdaFn calls
- [ ] Use createLambdaFunction() + createLambdaTargetGroup()
- [ ] Collect all target groups and pass to configureAllRouting()

### Phase 3: Refactor Embed Endpoints
- [ ] Replace createEmbedLambdaGeneric calls with new pattern
- [ ] Create createEmbedLambdaFunction() wrapper or just use createLambdaFunction()
- [ ] Collect target groups for routing configuration

### Phase 4: Refactor App API Endpoints
- [ ] Replace createAppLambdaGeneric calls with new pattern
- [ ] Use createLambdaFunction() + createLambdaTargetGroup()
- [ ] Collect target groups for routing configuration

### Phase 5: Wire Up Central Routing
- [ ] Call configureAllRouting() with all target groups
- [ ] Remove manual listener rule creation from index.ts
- [ ] Test weighted routing with Rust at 0% in production

### Phase 6: Cleanup
- [ ] Delete buildHttpLambdaFn from new_service.ts
- [ ] Delete createEmbedLambdaGeneric from embed/lambda_generic.ts
- [ ] Delete createAppLambdaGeneric from app_api/lambda_generic.ts
- [ ] Delete now-unused embed/lambda_generic.ts file
- [ ] Delete now-unused app_api/lambda_generic.ts file

## Key Patterns for Refactoring

### Current Old Pattern
```typescript
createEmbedLambdaGeneric({
  name: "embed-st",
  lbRuleConditions: [...],
  lbRulePriority: 2100,
  // ...
});
```
Creates: Lambda + target group + listener rule (all in one function)

### New Pattern (to use instead)
```typescript
const embedStLambda = createLambdaFunction({
  name: "embed-st-lambda",
  dockerImage: dockerLambdaImage,
  dockerCommand: ["embed.lambda_fn.lambda_handler_save_stamps"],
  // ... other params
});

const embedStTargetGroup = createLambdaTargetGroup({
  name: "embed-st-lambda-tg",
  lambda: embedStLambda,
  vpcId: vpcId,
});

// Then later in configureAllRouting():
pythonEmbedAddStamps: embedStTargetGroup
```

Listener rule is created centrally in routing-rules.ts, not scattered.

