# Rust Scorer Weighted Routing Implementation - Handoff Document

## Current State

We've implemented weighted (percentage-based) load balancing to gradually migrate from Python to Rust implementations of the scoring endpoints. This replaces the previous header-based routing that required clients to send `X-Use-Rust-Scorer: true`.

### What's Been Done

1. **Modified `infra/aws/v2/rust-scorer.ts`**:
   - Added environment-based routing configuration using object lookup (not switch statement)
   - Staging/Review: 100% Rust, 0% Python
   - Production: 0% Rust, 100% Python (safe default)
   - All weighted rules include 1-hour session stickiness for consistent user experience

2. **Updated listener rules to use weighted routing**:
   - Using AWS ALB's native weighted target group feature
   - Looking up existing Python target groups by their well-known names
   - Using the SAME priorities as existing Python rules (this will cause conflicts - see "Problem" section)

## The Problem

**AWS ALB doesn't allow two listener rules with the same priority.** Currently:

1. Python Lambda deployments (via `buildHttpLambdaFn` and `createEmbedLambdaGeneric`) automatically create listener rules
2. Our new Rust weighted routing tries to create rules at the SAME priorities
3. This will cause AWS to throw errors when both try to create rules

## Complete Endpoint Inventory

### Endpoints Implemented in BOTH Python and Rust

These need weighted routing for gradual migration:

| Endpoint | Method | Priority | Python Target Group | Rust Target Group |
|----------|--------|----------|-------------------|------------------|
| `/v2/stamps/*/score/*` | GET | 2023 | `l-passport-v2-stamp-score` | `l-passport-v2-rust-scorer` |
| `/ceramic-cache/stamps/bulk` | POST | 1002 | `l-cc-v1-st-bulk-POST-0` | `l-passport-v2-rust-scorer` |
| `/ceramic-cache/stamps/bulk` | PATCH | 1003 | `l-cc-v1-st-bulk-PATCH-0` | `l-passport-v2-rust-scorer` |
| `/ceramic-cache/stamps/bulk` | DELETE | 1004 | `l-cc-v1-st-bulk-DELETE-0` | `l-passport-v2-rust-scorer` |
| `/ceramic-cache/score/*` | POST | 1001 | `l-cc-v1-score-POST-0` | `l-passport-v2-rust-scorer` |
| `/internal/embed/stamps/*` | POST | 2100 | `embed-st-lambda-target-group` | `l-passport-v2-rust-scorer-int` |
| `/internal/embed/validate-api-key` | GET | 2101 | `embed-rl-lambda-target-group` | `l-passport-v2-rust-scorer-int` |
| `/internal/embed/score/*/*` | GET | 2103 | `embed-gs-lambda-target-group` | `l-passport-v2-rust-scorer-int` |

### Python-ONLY Endpoints

These don't need weighted routing and can keep their existing rules:

| Endpoint | Method | Priority | Target | Notes |
|----------|--------|----------|--------|-------|
| `/v2/stamps/*/score/*/history` | GET | 2022 | `targetGroupRegistry` | Direct rule |
| `/v2/stamps/metadata` | GET | 2060 | `targetGroupRegistry` | Via generic `/v2/*` rule |
| `/v2/stamps/{address}` | GET | 2060 | `targetGroupRegistry` | Via generic `/v2/*` rule |
| `/v2/models/score/*` | GET | 2021 | `l-passport-v2-model-score` | Lambda |
| `/ceramic-cache/authenticate` | POST | - | `l-cc-auth` | Lambda |

## Required Changes to Complete Implementation

### 1. Refactor Lambda Creation Functions

The core issue is that `buildHttpLambdaFn` and `createEmbedLambdaGeneric` bundle three things together:
- Lambda function creation
- Target group creation
- **Listener rule creation** (the problematic part)

We need to:
1. **Extract listener rule creation** from these functions
2. Create Lambda functions and target groups WITHOUT automatically creating rules
3. Manually create ONE set of weighted rules for dual-implementation endpoints

### 2. Infrastructure Code Changes Needed

#### Option A: Modify Existing Functions (Recommended)
```typescript
// Add optional parameter to skip rule creation
buildHttpLambdaFn({
  ...existingParams,
  skipListenerRule: true  // New parameter
});
```

#### Option B: Create New Functions
Create `buildHttpLambdaFnWithoutRule` and `createEmbedLambdaGenericWithoutRule` variants

### 3. Deployment Strategy

1. **Phase 1**: Modify infrastructure code to support Lambda creation without rules
2. **Phase 2**: Deploy with weighted rules using same priorities (replacing Python rules)
3. **Phase 3**: Monitor and adjust percentages as needed

## Files That Need Modification

1. **`infra/lib/scorer/new_service.ts`**:
   - Modify `buildHttpLambdaFn` to optionally skip listener rule creation

2. **`infra/aws/embed/lambda_generic.ts`**:
   - Modify `createEmbedLambdaGeneric` to optionally skip listener rule creation

3. **`infra/aws/index.ts`**:
   - Update ceramic-cache Lambda deployments to skip rule creation
   - Let weighted rules handle routing instead

4. **`infra/aws/embed/index.ts`**:
   - Update embed Lambda deployments to skip rule creation
   - Let weighted rules handle routing instead

5. **`infra/aws/v2/index.ts`**:
   - Update v2 Lambda deployment to skip rule creation for `/v2/stamps/*/score/*`
   - Keep rules for Python-only endpoints

## Environment Configuration

Current routing percentages (in `rust-scorer.ts`):

```typescript
const rustPercentages: { [key: string]: number } = {
  staging: 100,     // 100% to Rust in staging
  review: 100,      // 100% to Rust in review
  production: 0,    // 0% to Rust in production (safe default)
};
```

To gradually roll out in production, change `production: 0` to desired percentage (e.g., 5, 10, 25, 50, 100).

## Important Technical Notes

1. **Target Group Naming**: Python target groups have consistent names we can look up via `aws.lb.TargetGroup.get()`

2. **Separate Internal ALB Target Group**: AWS doesn't allow the same target group on multiple ALBs, so we have:
   - `l-passport-v2-rust-scorer` for public ALB
   - `l-passport-v2-rust-scorer-int` for internal ALB

3. **Method Mismatch**: Note that ceramic-cache/score uses POST in Python (not GET)

4. **Priority Conflicts**: The weighted rules MUST use the same priorities as existing Python rules to replace them

## Monitoring and Rollback

### Key Metrics to Monitor
- `TargetResponseTime`
- `HTTPCode_Target_4XX_Count`
- `HTTPCode_Target_5XX_Count`
- Cold start times
- Error rates between Python and Rust implementations

### Rollback Procedure
1. Set `production: 0` in `rustPercentages` configuration
2. Deploy via Pulumi
3. All traffic immediately routes to Python

## Next Steps for Implementation Team

1. **Decide on refactoring approach** (Option A or B above)
2. **Implement Lambda function changes** to skip rule creation
3. **Test in staging** with 100% Rust routing
4. **Deploy to production** with 0% Rust initially
5. **Gradually increase** Rust percentage while monitoring
6. **Complete migration** once confident in Rust implementation

## Current Blockers

The main blocker is the listener rule conflict. We cannot deploy the weighted routing as-is because AWS will reject duplicate priorities. The Lambda creation functions MUST be modified to support creating Lambdas without automatically creating listener rules.

## Questions for Decision

1. Should we modify existing functions or create new variants?
2. Do we want to keep any header-based routing as a fallback/override mechanism?
3. What's the desired rollout timeline and percentage increments?