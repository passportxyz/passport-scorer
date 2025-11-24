# AWS Lambda Infrastructure Analysis

**STATUS UPDATE (Nov 24, 2025)**: Priority conflict resolved. All priorities shifted to new ranges:
- V2 API: 2110-2112 (was 2021-2023)
- Ceramic-cache: 1030-1039 (was 1001-1010)
- Embed: 2104-2106 (was 2100-2103)

This document provides historical context for the refactoring that enabled weighted routing.

## Current Architecture Problems

### The Core Issue
The buildHttpLambdaFn() function in infra/lib/scorer/new_service.ts does THREE things in one monolithic function:
1. Creates Lambda function via buildLambdaFn()
2. Creates Lambda target group
3. Creates ALB listener rule

This violates separation of concerns and creates the priority conflict blocker: When Rust scorer tries to create weighted rules at the same priorities as Python Lambda rules, both functions try to create listener rules at the same priority number, causing deployment conflicts.

### AWS ALB Constraint
Each ALB listener can only have ONE rule at each priority number. Priorities are evaluated from LOWEST to HIGHEST.

## All Lambda Creation Call Sites (15 Total)

### In infra/aws/v2/index.ts (2 calls)
1. **Line 87-114**: passport-v2-model-score (Priority 2021)
   - Path: /v2/models/score/*
   - Method: GET
   - Memory: 256MB
   - Handler: v2.aws_lambdas.models_score_GET.handler

2. **Line 116-143**: passport-v2-stamp-score (Priority 2023) ← BLOCKED by Rust!
   - Path: /v2/stamps/*/score/*
   - Method: GET
   - Memory: 256MB
   - Handler: v2.aws_lambdas.stamp_score_GET.handler
   - **Rust wants to create weighted rule at priority 2023**

### In infra/aws/index.ts (9 calls)
3. **Line 1285-1306**: submit-passport-0 (Priority 1001)
   - Path: /registry/submit-passport
   - Method: POST
   - Memory: 1024MB
   - Handler: aws_lambdas.submit_passport.submit_passport.handler

4. **Line 1308-1329**: cc-v1-st-bulk-POST-0 (Priority 1002) ← BLOCKED by Rust!
   - Path: /ceramic-cache/stamps/bulk
   - Method: POST
   - Memory: 512MB
   - Handler: aws_lambdas.scorer_api_passport.v1.stamps.bulk_POST.handler
   - **Rust ceramic-cache stamps POST wants priority 1002**

5. **Line 1331-1352**: cc-v1-st-bulk-PATCH-0 (Priority 1003)
   - Path: /ceramic-cache/stamps/bulk
   - Method: PATCH
   - Memory: 512MB
   - Handler: aws_lambdas.scorer_api_passport.v1.stamps.bulk_PATCH.handler
   - **Python-only, no Rust implementation**

6. **Line 1354-1375**: cc-v1-st-bulk-DELETE-0 (Priority 1004)
   - Path: /ceramic-cache/stamps/bulk
   - Method: DELETE
   - Memory: 512MB
   - Handler: aws_lambdas.scorer_api_passport.v1.stamps.bulk_DELETE.handler
   - **Python-only, no Rust implementation**

7. **Line 1377-1398**: cc-v1-score-POST-0 (Priority 1006) ← BLOCKED by Rust!
   - Path: /ceramic-cache/score/*
   - Method: POST
   - Memory: 512MB
   - Handler: aws_lambdas.scorer_api_passport.v1.score_POST.handler
   - **Rust ceramic-cache score POST wants priority 1001**

8. **Line 1400-1421**: cc-v1-score-GET-0 (Priority 1007)
   - Path: /ceramic-cache/score/0x*
   - Method: GET
   - Memory: 512MB
   - Handler: aws_lambdas.scorer_api_passport.v1.score_GET.handler

9. **Line 1423-1444**: cc-weights-GET-0 (Priority 1015)
   - Path: /ceramic-cache/weights
   - Method: GET
   - Memory: 512MB
   - Handler: aws_lambdas.scorer_api_passport.v1.weights_GET.handler

10. **Line 1446-1467**: cc-v1-st-GET-0 (Priority 1010)
    - Path: /ceramic-cache/stamp
    - Method: GET
    - Memory: 512MB
    - Handler: aws_lambdas.scorer_api_passport.v1.stamp_GET.handler

11. **Line 1469-1490**: passport-analysis-GET-0 (Priority 1012)
    - Path: /passport/analysis/*
    - Method: GET
    - Memory: 256MB
    - Handler: aws_lambdas.passport.analysis_GET.handler

### In infra/aws/embed/index.ts via createEmbedLambdaGeneric (3 calls)
12. **embed-st** (Priority 2100) ← BLOCKED by Rust!
    - Path: /internal/embed/stamps/*
    - Method: POST
    - Handler: embed.lambda_fn.lambda_handler_save_stamps
    - **Rust wants to create weighted rule at priority 2100**

13. **embed-rl** (Priority 2101) ← BLOCKED by Rust!
    - Path: /internal/embed/validate-api-key
    - Method: GET
    - Handler: embed.lambda_fn.lambda_handler_get_rate_limit
    - **Rust wants to create weighted rule at priority 2101**

14. **embed-gs** (Priority 2103) ← BLOCKED by Rust!
    - Path: /internal/embed/score/*
    - Method: GET
    - Handler: embed.lambda_fn.lambda_handler_get_score
    - **Rust wants to create weighted rule at priority 2103**

### In infra/aws/app_api/index.ts via createAppLambdaGeneric (2 calls - different ALB)
15. **cc-nonce** (Priority 5010)
    - Path: /account/nonce
    - Methods: GET, OPTIONS

16. **cc-auth** (Priority 5020)
    - Path: /ceramic-cache/authenticate
    - Methods: POST, OPTIONS

## Nested Function Calls Architecture

### buildHttpLambdaFn (infra/lib/scorer/new_service.ts, line 738-951)
- Takes BuildLambdaFnBaseParams + httpsListener + listenerPriority + httpListenerRulePaths
- Calls buildLambdaFn() to create Lambda
- Creates target group: new aws.lb.TargetGroup
- Creates Lambda permission for ALB
- Creates target group attachment
- **Creates listener rule at listenerPriority** ← THE BLOCKER
- Creates CloudWatch alarms

### buildLambdaFn (infra/lib/scorer/new_service.ts, line 969-1029)
- Just creates aws.lambda.Function
- Handles both Image (container) and Zip package types
- Does NOT create target groups or listener rules

### createEmbedLambdaGeneric (infra/aws/embed/lambda_generic.ts, line 11-153)
- Called by createEmbedLambdaFunctions in embed/index.ts
- Calls createLambdaFunction from infra/lib/lambda
- Creates target group
- Creates Lambda permission
- Creates target group attachment
- **Creates listener rule at lbRulePriority** ← THE BLOCKER
- Creates CloudWatch alarms

## Current Rust Scorer Implementation (infra/aws/v2/rust-scorer.ts)

**Successfully creates**:
- Lambda function (line 109-151)
- Target group for public ALB (line 154-158)
- Lambda permission (line 161-166)
- Target group attachment (line 169-178)
- Internal target group (line 346-350)
- Internal Lambda permission (line 353-361)
- Internal target group attachment (line 364-373)

**Creates listener rules** (lines 191-513):
- Uses aws.lb.ListenerRule directly with weighted forward config
- Creates rules at priorities 2023, 1002, 1001, 2100, 2101, 2103
- Gets references to Python target groups using aws.lb.TargetGroup.get()

**Architecture Issues**:
1. Rust code depends on exact Python target group names being discoverable
2. Changes to Python naming would break Rust
3. Future code won't understand the weighted routing pattern
4. If Python lambda names change, Rust breaks silently

## Refactoring Strategy

### Step 1: Create New Routing Functions
New file: infra/lib/scorer/routing.ts

Separate concerns into 4 independent functions:
1. buildLambdaFunction() - Just create Lambda (extracted from buildLambdaFn)
2. createLambdaTargetGroup() - Just create target group + permission + attachment
3. createListenerRule() - Simple single-target routing
4. createWeightedListenerRule() - Weighted routing with multiple targets

### Step 2: Update Imports
- infra/aws/v2/index.ts - import new functions, stop using buildHttpLambdaFn
- infra/aws/index.ts - import new functions, stop using buildHttpLambdaFn
- infra/aws/embed/index.ts - keep using createEmbedLambdaGeneric (refactor later)

### Step 3: Refactor All 15 Call Sites
Transform from:
```typescript
buildHttpLambdaFn({ ...params, listenerPriority: 1001 }, alarmConfigurations)
```

To:
```typescript
const lambda = buildLambdaFunction({ ...params });
const targetGroup = createLambdaTargetGroup(lambda, name);
if (isRustEnabled(stack) && isWeightedRoutingEndpoint(priority)) {
  createWeightedListenerRule({ targetGroups, priority, conditions, listenerArn });
} else {
  createListenerRule({ targetGroup, priority, conditions, listenerArn });
}
```

## Dual Implementation Endpoints (6 Total)
These need weighted routing:
1. /v2/stamps/*/score/* (Priority 2023)
2. /ceramic-cache/score/* (Priority 1001)
3. /ceramic-cache/stamps/bulk POST (Priority 1002)
4. /internal/embed/stamps/* (Priority 2100)
5. /internal/embed/validate-api-key (Priority 2101)
6. /internal/embed/score/* (Priority 2103)

## Python-Only Endpoints (9 Total)
These keep simple routing:
1. /v2/models/score/* (Priority 2021)
2. /registry/submit-passport (Priority 1001)
3. /ceramic-cache/stamps/bulk PATCH (Priority 1003)
4. /ceramic-cache/stamps/bulk DELETE (Priority 1004)
5. /ceramic-cache/score/0x* (Priority 1007)
6. /ceramic-cache/weights (Priority 1015)
7. /ceramic-cache/stamp (Priority 1010)
8. /passport/analysis/* (Priority 1012)
9. App API endpoints (different ALB)

## Naming Convention
Target group names already established:
- Python v2 stamp score: "l-passport-v2-stamp-score"
- Python ceramic-cache stamps: "l-cc-v1-st-bulk-POST-0"
- Python ceramic-cache score: "l-cc-v1-score-POST-0"
- Python embed-st: "embed-st-lambda-target-group"
- Python embed-rl: "embed-rl-lambda-target-group"
- Python embed-gs: "embed-gs-lambda-target-group"
- Rust public: "l-passport-v2-rust-scorer"
- Rust internal: "l-passport-v2-rust-scorer-int"

## Environment-Based Percentages
Current routing percentages in rust-scorer.ts:
- staging: 100% Rust, 0% Python
- review: 100% Rust, 0% Python
- production: 0% Rust, 100% Python (safe default)

## Listener References
- Public ALB: httpsListener.arn
- Internal ALB: internalHttpsListener.arn (optional, only if provided)

See: `infra/lib/scorer/new_service.ts`, `infra/aws/v2/index.ts`, `infra/aws/index.ts`, `infra/aws/embed/lambda_generic.ts`, `infra/aws/v2/rust-scorer.ts`