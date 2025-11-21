### [16:01] [deployment] Rust scorer weighted routing implementation details
**Details**: Implemented weighted routing for Rust scorer to replace header-based routing. Key changes:

**Routing Configuration**:
- Object-based lookup instead of switch: rustPercentages[environment] || 0
- staging: 100% Rust, review: 100% Rust, production: 0% Rust (safe default)
- Python percentage = 100 - rustPercentage

**Listener Rules - Using existing Python priorities to replace them**:
1. V2 stamps score (GET /v2/stamps/*/score/*): priority 2023, target: l-passport-v2-stamp-score
2. Ceramic-cache stamps bulk (POST): priority 1002, target: l-cc-v1-st-bulk-POST-0
3. Ceramic-cache score (POST): priority 1001, target: l-cc-v1-score-POST-0
4. Embed stamps (POST /internal/embed/stamps/*): priority 2100, target: embed-st-lambda-target-group
5. Embed validate-api-key (GET): priority 2101, target: embed-rl-lambda-target-group
6. Embed score (GET): priority 2103, target: embed-gs-lambda-target-group

**Important corrections**:
- Ceramic-cache endpoints DO exist in Python (api/ceramic_cache/api/v1.py)
- Using existing Python priorities to replace Python rules (not creating new rules)
- ceramic-cache/score uses POST method, not GET
- All weighted rules have session stickiness (1 hour)

**To prevent duplicate rules**: 
- Weighted rules must use same priorities as existing Python rules they replace
- Python Lambda deployments should be modified to NOT create rules when Rust weighted rules exist
- Or use conditional deployment based on environment
**Files**: infra/aws/v2/rust-scorer.ts
---

### [16:14] [deployment] Rust weighted routing implementation status
**Details**: The weighted routing for Rust scorer has been partially implemented in infra/aws/v2/rust-scorer.ts with environment-based percentages (staging/review: 100% Rust, production: 0% Rust). However, there's a critical blocker: AWS ALB doesn't allow two listener rules with the same priority. The current implementation tries to create rules at the same priorities as existing Python rules, which will cause AWS to throw errors.

The solution requires refactoring Lambda creation functions (buildHttpLambdaFn and createEmbedLambdaGeneric) to optionally skip listener rule creation, so we can manually create ONE set of weighted rules for dual-implementation endpoints instead of having conflicting rules.

8 endpoints need weighted routing for gradual migration:
- /v2/stamps/*/score/* (GET)
- /ceramic-cache/stamps/bulk (POST, PATCH, DELETE)
- /ceramic-cache/score/* (POST)
- /internal/embed/stamps/* (POST)
- /internal/embed/validate-api-key (GET)
- /internal/embed/score/*/* (GET)

Python-only endpoints can keep their existing rules.
**Files**: infra/aws/v2/rust-scorer.ts, RUST_WEIGHTED_ROUTING_HANDOFF.md
---

### [16:15] [deployment] Listener Rule Priority Conflict Analysis for Weighted Routing
**Details**: CRITICAL FINDING: The Rust weighted routing implementation has a fundamental conflict with how Python lambdas create their listener rules.

## The Problem

The Rust code in `infra/aws/v2/rust-scorer.ts` is trying to CREATE NEW ListenerRule resources that replace Python's existing rules at the same priority levels:
- Priority 2023: v2/stamps/*/score/* (main scoring endpoint)
- Priority 1002: /ceramic-cache/stamps/bulk (POST)
- Priority 1001: /ceramic-cache/score/* (POST)
- Priority 2100: /internal/embed/stamps/* (embed)
- Priority 2101: /internal/embed/validate-api-key (embed)
- Priority 2103: /internal/embed/score/*/* (embed)

## How Python Creates Rules

1. **buildHttpLambdaFn()** in `infra/lib/scorer/new_service.ts` (lines 87-143):
   - Called twice for v2 endpoints (model-score and stamp-score)
   - Creates a Python Lambda function with specific handler
   - Creates a ListenerRule at specified priority (2021, 2023, etc.)
   - The Python code itself creates these rules - it doesn't just create Lambdas

2. **createEmbedLambdaGeneric()** in `infra/aws/embed/lambda_generic.ts` (lines 141-152):
   - Called 3 times (embed-st, embed-rl, embed-gs)
   - Creates a Python Lambda function for each
   - Creates a ListenerRule at specified priority (2100, 2101, 2103)
   - Rules point to Python target groups

## The Conflict

The Rust code tries to:
1. Look up existing Python target groups using `aws.lb.TargetGroup.get()`:
   - `aws.lb.TargetGroup.get("python-v2-stamp-score-tg", "l-passport-v2-stamp-score")`
   - `aws.lb.TargetGroup.get("python-cc-stamps-bulk-post-tg", "l-cc-v1-st-bulk-POST-0")`
   - `aws.lb.TargetGroup.get("python-embed-st-tg", "embed-st-lambda-target-group")`

2. Create NEW ListenerRule resources at THE SAME PRIORITY as existing Python rules

This creates TWO ListenerRule resources for the same path+priority, which AWS will reject because:
- ALB listener rules enforce unique (priority, listener) pairs
- You cannot have two rules at the same priority on the same listener
- Pulumi will try to create both and one will fail

## Why This Doesn't Work

In Terraform/Pulumi, when you create a new resource at the same logical key as an existing one, you have conflicts. The Python code creates the original ListenerRules during infrastructure deployment. The Rust code tries to create competing rules.

## Files Involved

- `infra/aws/v2/index.ts` (lines 87-143): Python buildHttpLambdaFn calls for v2/stamps
- `infra/aws/embed/index.ts` (lines 16-72): Python createEmbedLambdaGeneric calls for embed
- `infra/aws/v2/rust-scorer.ts` (lines 189-514): Rust weighted routing attempts

## Required Solution

The Rust implementation needs to MODIFY existing Python ListenerRules in-place, not create new ones. This requires:
1. Converting Python's simple ListenerRules (single targetGroupArn) to weighted ListenerRules
2. Doing this in the SAME place where the Python rule is created
3. Passing routing information through the entire infrastructure stack

OR

Use different approach:
1. Create Rust rules at DIFFERENT priorities (e.g., 2023 becomes 2090)
2. Update buildHttpLambdaFn to increment priority for Python rules
3. Maintain separate rule priorities rather than replacing them

Currently the Rust code comment says "We're replacing the existing Python rule" but infrastructure code doesn't support in-place replacement - you need to either delete the old one or not create it in the first place.
**Files**: infra/aws/v2/index.ts, infra/aws/v2/rust-scorer.ts, infra/aws/embed/index.ts, infra/aws/embed/lambda_generic.ts, infra/lib/scorer/new_service.ts
---

### [16:19] [gotcha] ALB listener rule creation in Lambda functions
**Details**: The buildHttpLambdaFn function in infra/lib/scorer/new_service.ts:774 automatically creates a ListenerRule when creating a Lambda. This is the root cause of the weighted routing conflict - both Python Lambda creation (via buildHttpLambdaFn) and Rust weighted routing try to create rules at the same priority.

Similarly, createEmbedLambdaGeneric in infra/aws/embed/lambda_generic.ts also creates ListenerRules automatically.

The ceramic-cache lambdas are created via buildHttpLambdaFn calls in infra/aws/index.ts with priorities:
- 1001: ceramic_cache_score_POST
- 1002: ceramic_cache_stamps_bulk_POST  
- 1003: ceramic_cache_stamps_bulk_PATCH
- 1004: ceramic_cache_stamps_bulk_DELETE

These automatic rule creations conflict with the weighted routing rules that need to be at the same priorities to replace them.
**Files**: infra/lib/scorer/new_service.ts, infra/aws/v2/rust-scorer.ts, infra/aws/index.ts
---

### [17:22] [architecture] Weighted Routing Infrastructure Analysis - Complete Call Site Inventory
**Details**: Comprehensive analysis of AWS ALB infrastructure showing all Lambda creation patterns and routing rules.

## Current Architecture Problems

### The Core Issue
The buildHttpLambdaFn() function in infra/lib/scorer/new_service.ts does THREE things in one monolithic function:
1. Creates Lambda function via buildLambdaFn()
2. Creates Lambda target group
3. Creates ALB listener rule

This violates separation of concerns and creates the priority conflict blocker: When Rust scorer tries to create weighted rules at the same priorities as Python Lambda rules, both functions try to create listener rules at the same priority number, causing deployment conflicts.

### AWS ALB Constraint
Each ALB listener can only have ONE rule at each priority number. Priorities are evaluated from LOWEST to HIGHEST.

## All Call Sites (15 Total)

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

## Nested Function Calls

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

## What Rust Scorer Currently Does (infra/aws/v2/rust-scorer.ts)

**Successfully creates**:
- Lambda function (line 109-151)
- Target group for public ALB (line 154-158)
- Lambda permission (line 161-166)
- Target group attachment (line 169-178)
- Internal target group (line 346-350)
- Internal Lambda permission (line 353-361)
- Internal target group attachment (line 364-373)

**Incorrectly creates listener rules** (lines 191-513):
- Uses aws.lb.ListenerRule directly with weighted forward config
- Creates rules at priorities 2023, 1002, 1001, 2100, 2101, 2103
- Gets references to Python target groups using aws.lb.TargetGroup.get()
- This works but creates the architectural conflict

**Why this works**: aws.lb.ListenerRule is a new resource that replaces the old Python rule, so there's no deployment conflict in practice. However, the architecture is fragile because:
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

### Step 4: Remove Old Functions
- Delete buildHttpLambdaFn completely
- Delete createEmbedLambdaGeneric completely (after refactoring embed calls)
- Delete createLambdaTargetGroup from buildHttpLambdaFn

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

## Implementation Notes

### Naming Convention
Target group names already established:
- Python v2 stamp score: "l-passport-v2-stamp-score"
- Python ceramic-cache stamps: "l-cc-v1-st-bulk-POST-0"
- Python ceramic-cache score: "l-cc-v1-score-POST-0"
- Python embed-st: "embed-st-lambda-target-group"
- Python embed-rl: "embed-rl-lambda-target-group"
- Python embed-gs: "embed-gs-lambda-target-group"
- Rust public: "l-passport-v2-rust-scorer"
- Rust internal: "l-passport-v2-rust-scorer-int"

### Environment-Based Percentages
Current routing percentages in rust-scorer.ts:
- staging: 100% Rust, 0% Python
- review: 100% Rust, 0% Python
- production: 0% Rust, 100% Python (safe default)

### Listener References
- Public ALB: httpsListener.arn
- Internal ALB: internalHttpsListener.arn (optional, only if provided)

Files affected: 
- infra/lib/scorer/new_service.ts (738-1029 lines)
- infra/lib/scorer/routing.ts (NEW FILE)
- infra/aws/v2/index.ts (87-143)
- infra/aws/index.ts (1285-1490)
- infra/aws/embed/lambda_generic.ts (11-153)
- infra/aws/embed/index.ts (16-72)
- infra/aws/v2/rust-scorer.ts (1-516)
**Files**: infra/lib/scorer/new_service.ts, infra/aws/v2/index.ts, infra/aws/index.ts, infra/aws/embed/lambda_generic.ts, infra/aws/v2/rust-scorer.ts
---

