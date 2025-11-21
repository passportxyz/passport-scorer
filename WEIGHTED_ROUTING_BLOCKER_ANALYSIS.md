# Weighted Routing Blocker Analysis

## Executive Summary

The weighted routing implementation for the Rust scorer is **blocked by an AWS ALB constraint**: Two listener rules cannot share the same priority. The current implementation creates conflicts at 6 priority levels where both Python and Rust try to create rules.

## The Core Problem

### AWS ALB Constraint
- **AWS Rule**: Each listener can only have ONE rule at each priority number
- **Current Situation**: Both Python Lambda creation and Rust weighted routing try to create rules at the same priorities
- **Result**: Pulumi deployment fails with "Priority already in use" errors

### The 6 Conflicts

| Priority | Endpoint | Python Creates | Rust Creates | Conflict |
|----------|----------|---------------|--------------|----------|
| 2023 | `/v2/stamps/*/score/*` | Via `buildHttpLambdaFn` | Weighted rule | ❌ |
| 1001 | `/ceramic-cache/score/*` | Via `buildHttpLambdaFn` | Weighted rule | ❌ |
| 1002 | `/ceramic-cache/stamps/bulk` POST | Via `buildHttpLambdaFn` | Weighted rule | ❌ |
| 2100 | `/internal/embed/stamps/*` | Via `createEmbedLambdaGeneric` | Weighted rule | ❌ |
| 2101 | `/internal/embed/validate-api-key` | Via `createEmbedLambdaGeneric` | Weighted rule | ❌ |
| 2103 | `/internal/embed/score/*/*` | Via `createEmbedLambdaGeneric` | Weighted rule | ❌ |

Note: Priorities 1003 and 1004 (PATCH/DELETE ceramic-cache) are Python-only, no conflict.

## Root Cause Analysis

### Python Lambda Creation Functions

1. **`buildHttpLambdaFn`** (infra/lib/scorer/new_service.ts:774)
   - Automatically creates a ListenerRule at the specified priority
   - Used for v2 and ceramic-cache endpoints
   - Cannot be disabled without modifying the function

2. **`createEmbedLambdaGeneric`** (infra/aws/embed/lambda_generic.ts)
   - Automatically creates a ListenerRule at the specified priority
   - Used for all embed endpoints
   - Cannot be disabled without modifying the function

### Current Rust Implementation

The rust-scorer.ts file tries to create weighted routing rules at the same priorities:
```typescript
new aws.lb.ListenerRule("lrule-weighted-v2-stamps-score", {
  priority: 2023,  // Same as Python!
  forward: {
    targetGroups: [
      { arn: pythonTargetGroup, weight: routingPercentages.python },
      { arn: rustTargetGroup, weight: routingPercentages.rust }
    ]
  }
})
```

## Proposed Solution: Clean Function Separation

### The Problem with Current Design

`buildHttpLambdaFn` violates the Single Responsibility Principle by doing three things:
1. Creating a Lambda function
2. Creating a target group
3. Creating a listener rule

This coupling makes it impossible to use weighted routing without conflicts.

### Recommended Solution: Extract and Separate Concerns

Refactor the infrastructure code to separate these three concerns into independent, composable functions:

```typescript
// Step 1: Create focused, single-purpose functions
export function buildLambdaFunction(args: LambdaArgs): aws.lambda.Function {
  // Just creates the Lambda, nothing else
}

export function createLambdaTargetGroup(lambda: aws.lambda.Function, name: string): aws.lb.TargetGroup {
  // Creates target group and attaches Lambda
}

export function createListenerRule(args: {
  targetGroup: aws.lb.TargetGroup,
  priority: number,
  conditions: aws.types.input.lb.ListenerRuleCondition[],
  listenerArn: pulumi.Output<string>
}): aws.lb.ListenerRule {
  // Creates a simple forward rule
}

export function createWeightedListenerRule(args: {
  targetGroups: Array<{ arn: string, weight: number }>,
  priority: number,
  conditions: aws.types.input.lb.ListenerRuleCondition[],
  listenerArn: pulumi.Output<string>,
  sessionStickiness?: number
}): aws.lb.ListenerRule {
  // Creates a weighted routing rule
}
```

### Implementation at Call Sites

With separated functions, each endpoint can explicitly control its routing:

```typescript
// Example: v2 stamps score endpoint
const stampScoreLambda = buildLambdaFunction({
  name: "passport-v2-stamp-score",
  // ... other params
});

const stampScoreTargetGroup = createLambdaTargetGroup(
  stampScoreLambda,
  "l-passport-v2-stamp-score"
);

// Conditionally create appropriate routing based on Rust enablement
const rustEnabled = getRoutingPercentages(stack).rust > 0;

if (rustEnabled) {
  // Create ONE weighted rule for both Python and Rust
  createWeightedListenerRule({
    targetGroups: [
      { arn: stampScoreTargetGroup.arn, weight: routingPercentages.python },
      { arn: rustScorerTargetGroup.arn, weight: routingPercentages.rust }
    ],
    priority: 2023,
    conditions: [/* path, method, host conditions */],
    listenerArn: httpsListener.arn,
    sessionStickiness: 3600
  });
} else {
  // Create simple Python-only rule
  createListenerRule({
    targetGroup: stampScoreTargetGroup,
    priority: 2023,
    conditions: [/* path, method, host conditions */],
    listenerArn: httpsListener.arn
  });
}
```

### Migration Strategy: Clean Break

**No backward compatibility layer** - refactor all call sites in one deployment:

```typescript
// DELETE the old buildHttpLambdaFn entirely
// Replace ALL call sites with the new pattern

// This forces clean, explicit code everywhere
```

Why a clean break is better:
- **No tech debt**: Don't leave deprecated functions lying around
- **Forced consistency**: All endpoints use the same pattern
- **Clear intent**: No ambiguity about which approach to use
- **Smaller codebase**: Remove old code instead of maintaining both

The refactoring touches exactly 15 call sites:
- 11 calls to `buildHttpLambdaFn` across the codebase
- 4 calls to `createEmbedLambdaGeneric`
- All must be updated to use the new functions
- Then DELETE both old functions entirely

## Implementation Steps

### Phase 1: Extract Core Functions (3-4 hours)
1. Create `buildLambdaFunction` that only creates Lambda
2. Create `createLambdaTargetGroup` for target group + attachment
3. Create `createListenerRule` for simple routing
4. Create `createWeightedListenerRule` for weighted routing
5. Add `isRustEnabled()` helper function

### Phase 2: Refactor ALL Call Sites (5-6 hours)
1. Update all 11 `buildHttpLambdaFn` calls to use new functions
2. Update all 4 `createEmbedLambdaGeneric` calls to use new functions
3. Add conditional logic for weighted routing on the 6 dual-implementation endpoints
4. Leave simple routing for Python-only endpoints
5. Delete `buildHttpLambdaFn` and `createEmbedLambdaGeneric` entirely

### Phase 3: Update Rust Scorer Configuration (1 hour)
1. Remove duplicate listener rule creation from rust-scorer.ts
2. Ensure Rust target groups are created correctly
3. Verify weighted routing configuration

### Phase 4: Deploy and Test (2-3 hours)
1. Deploy to staging with Python-only (Rust disabled)
2. Deploy to staging with 100% Rust
3. Test 50/50 weighted split
4. Verify session stickiness
5. Deploy to production with 0% Rust initially

## Files Requiring Modification

### New Infrastructure Functions
1. **infra/lib/scorer/routing.ts** (NEW FILE)
   - Extract `buildLambdaFunction` from buildHttpLambdaFn
   - Extract `createLambdaTargetGroup` from buildHttpLambdaFn
   - Create `createListenerRule` for simple routing
   - Create `createWeightedListenerRule` for weighted routing
   - Add `isRustEnabled()` helper

2. **infra/lib/scorer/new_service.ts**
   - Refactor `buildHttpLambdaFn` to use new functions
   - Mark as deprecated with console warning
   - Maintain backward compatibility

### Lambda Deployments to Refactor
3. **infra/aws/v2/index.ts**
   - Line 116-143: v2 stamp score Lambda - use new functions
   - Add conditional routing logic

4. **infra/aws/index.ts**
   - Lines 1285-1306: submit-passport Lambda (no change needed)
   - Lines 1308-1329: ceramic-cache POST - use new functions
   - Lines 1331-1352: ceramic-cache PATCH (Python only, no change)
   - Lines 1354-1375: ceramic-cache DELETE (Python only, no change)
   - Add ceramic-cache score endpoint with new functions

5. **infra/aws/embed/index.ts**
   - Lines 16-34: embed stamps - refactor with new functions
   - Lines 35-52: embed validate-api-key - refactor
   - Lines 54-72: embed score - refactor

6. **infra/aws/embed/lambda_generic.ts**
   - Refactor `createEmbedLambdaGeneric` similar to buildHttpLambdaFn
   - Use extracted functions

### Rust Scorer Updates
7. **infra/aws/v2/rust-scorer.ts**
   - Remove duplicate listener rules (lines 191-513)
   - Keep Lambda and target group creation only
   - Export target groups for use in weighted routing

## Testing Checklist

- [ ] Deploy to staging with Rust disabled - verify Python-only works
- [ ] Deploy to staging with Rust at 100% - verify no conflicts
- [ ] Test weighted routing at 50/50 split
- [ ] Verify session stickiness works (1 hour duration)
- [ ] Test rollback scenario (100% Rust → 0% Rust)
- [ ] Monitor ALB metrics during transition
- [ ] Verify all 6 endpoints route correctly

## Risk Assessment

### Low Risk
- Changes are infrastructure-only, no application code changes
- Can be rolled back instantly by setting Rust percentage to 0
- Session stickiness ensures consistent user experience

### Medium Risk
- Requires changes to shared infrastructure functions
- Must coordinate deployment across multiple Lambda functions
- Testing required for all percentage combinations
- Slightly more complex refactoring than simple parameter approach

## Why This Approach is Better

### Problems with Skip Parameters
- **Code Smell**: Boolean parameters are an anti-pattern
- **Hidden Complexity**: "Skip" logic obscures what's actually happening
- **Tight Coupling**: Still bundles unrelated concerns together
- **Poor Testability**: Hard to test routing logic independently

### Benefits of Function Separation
1. **Single Responsibility**: Each function does one thing well
2. **Explicit Control**: Clear what's happening at each call site
3. **Better Testing**: Can test Lambda, target groups, and routing independently
4. **Flexibility**: Can mix and match components as needed
5. **Clean Architecture**: Follows SOLID principles
6. **Future-Proof**: Easy to add new routing strategies (canary, blue-green)

## Alternative Approaches Considered

1. **Add skipListenerRule parameter**:
   - ❌ Rejected: Boolean parameters are a code smell, doesn't fix coupling

2. **Different Priorities**: Use different priority numbers for Rust rules
   - ❌ Rejected: Would require complex priority management and could break routing

3. **Remove Python Rules**: Delete Python rules when Rust enabled
   - ❌ Rejected: Makes rollback difficult, requires downtime

4. **Separate ALBs**: Use different load balancers
   - ❌ Rejected: Too complex, expensive, and unnecessary

## Timeline Estimate

- **Phase 1 - Extract Functions**: 3-4 hours
- **Phase 2 - Refactor ALL Call Sites**: 5-6 hours
- **Phase 3 - Update Rust Config**: 1 hour
- **Phase 4 - Testing**: 2-3 hours
- **Total**: 11-14 hours of engineering time

This is more work upfront, but you get:
- **Zero tech debt** - no deprecated functions left behind
- **Consistent patterns** - every Lambda uses the same approach
- **Clean codebase** - actually smaller after removing old functions
- **Better architecture** - proper separation of concerns throughout

## Next Steps

1. Get approval for the refactoring approach
2. Create new routing.ts file with extracted functions
3. Refactor one endpoint as proof of concept
4. Update remaining endpoints incrementally
5. Test thoroughly in staging
6. Create deployment runbook
7. Schedule production deployment window