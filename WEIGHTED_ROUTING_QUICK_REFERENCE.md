# Weighted Routing - Quick Reference

## Status at a Glance

**Overall Progress**: 30% Complete
- ✅ Infrastructure created (routing-utils.ts, routing-rules.ts)
- ✅ V2 API refactored (separates Lambda/TG creation from routing)
- ❌ Ceramic Cache (9 endpoints) - still using old pattern
- ❌ Embed (3 endpoints) - still using old pattern
- ❌ App API (2 endpoints) - still using old pattern
- ❌ Central routing not wired up
- 🐛 Critical bugs in rust-scorer.ts

## Critical Bugs to Fix First

### Bug in `infra/aws/v2/rust-scorer.ts` (Line 186)

**Current Code (BROKEN):**
```typescript
  // Return the target groups for use in centralized routing
  return {
    rustScorer: rustScorerTargetGroup,
    rustScorerInternal: internalTargetGroup,  // ❌ UNDEFINED!
  };
}
```

**Fix Required:**
Add internal target group creation BEFORE the return statement (around line 177).

**Add This Code (15 lines):**
```typescript
  // Create Lambda target group for internal ALB (embed endpoints)
  const rustScorerInternalTargetGroup = new aws.lb.TargetGroup("l-passport-v2-rust-scorer-int", {
    name: "l-passport-v2-rust-scorer-int",
    targetType: "lambda",
    tags: { ...defaultTags, Name: "l-passport-v2-rust-scorer-int" },
  });

  // Grant ALB permission to invoke the Lambda
  const rustScorerInternalLambdaPermission = new aws.lambda.Permission("withLb-passport-v2-rust-scorer-int", {
    action: "lambda:InvokeFunction",
    function: rustScorerLambda.name,
    principal: "elasticloadbalancing.amazonaws.com",
    sourceArn: rustScorerInternalTargetGroup.arn,
  });

  // Attach Lambda to internal target group
  const rustScorerInternalTargetGroupAttachment = new aws.lb.TargetGroupAttachment(
    "lambdaTargetGroupAttachment-passport-v2-rust-scorer-int",
    {
      targetGroupArn: rustScorerInternalTargetGroup.arn,
      targetId: rustScorerLambda.arn,
    },
    {
      dependsOn: [rustScorerInternalLambdaPermission],
    }
  );

  // Return the target groups for use in centralized routing
  return {
    rustScorer: rustScorerTargetGroup,
    rustScorerInternal: rustScorerInternalTargetGroup,  // ✅ NOW DEFINED!
  };
```

## Work Breakdown

### Phase 1: Fix Critical Bug (30 min)
- [ ] Add internal target group creation to rust-scorer.ts
- [ ] Verify typescript compilation succeeds
- File: `infra/aws/v2/rust-scorer.ts`

### Phase 2: Refactor Ceramic Cache Endpoints (2-3 hours)
Files affected:
- `infra/aws/index.ts` (lines 1285-1492)

9 endpoints to refactor:
1. submit-passport (Priority 1000)
2. cc-v1-score-POST (Priority 1001)
3. cc-v1-st-bulk-POST (Priority 1002)
4. cc-v1-st-bulk-PATCH (Priority 1003)
5. cc-v1-st-bulk-DELETE (Priority 1004)
6. cc-v1-score-GET (Priority 1006)
7. cc-v1-st-GET (Priority 1007)
8. passport-analysis-GET (Priority 1012)
9. cc-weights-GET (Priority 1015)

Replace old pattern:
```typescript
buildHttpLambdaFn({
  name: "submit-passport-0",
  dockerCmd: ["aws_lambdas.submit_passport.submit_passport.handler"],
  listenerPriority: 1000,
  httpListenerRulePaths: [...],
  // ...
}, alarmConfigurations);
```

With new pattern:
```typescript
const submitPassportLambda = createLambdaFunction({
  name: "submit-passport",
  dockerImage: dockerLambdaImage,
  dockerCommand: ["aws_lambdas.submit_passport.submit_passport.handler"],
  // ... other params from old call
});

const submitPassportTargetGroup = createLambdaTargetGroup({
  name: "submit-passport-tg",
  lambda: submitPassportLambda,
  vpcId: vpcId,
});

// Collect for later routing setup
pythonSubmitPassport: submitPassportTargetGroup,
```

### Phase 3: Refactor Embed Endpoints (1 hour)
Files affected:
- `infra/aws/embed/index.ts` (entire file)
- Delete: `infra/aws/embed/lambda_generic.ts` (after refactor)

3 endpoints using `createEmbedLambdaGeneric()`:
1. embed-st (Priority 2100)
2. embed-rl (Priority 2101)
3. embed-gs (Priority 2103)

Replace with new pattern using `createLambdaFunction()` + `createLambdaTargetGroup()`

### Phase 4: Refactor App API Endpoints (30 min)
Files affected:
- `infra/aws/app_api/index.ts` (entire file)
- Delete: `infra/aws/app_api/lambda_generic.ts` (after refactor)

2 endpoints using `createAppLambdaGeneric()`:
1. cc-nonce (Priority 5010)
2. cc-auth (Priority 5020)

Replace with new pattern using `createLambdaFunction()` + `createLambdaTargetGroup()`

### Phase 5: Wire Up Central Routing (1 hour)
Files affected:
- `infra/aws/index.ts` (add routing configuration call)
- `infra/lib/scorer/routing-rules.ts` (update TargetGroups interface)

1. Add all target groups to `TargetGroups` interface
2. Call `configureAllRouting()` with all collected target groups
3. Remove any remaining manual listener rule creation from index.ts

### Phase 6: Cleanup (15 min)
Delete old functions:
- [ ] Delete `buildHttpLambdaFn()` from `infra/lib/scorer/new_service.ts`
- [ ] Delete `createEmbedLambdaGeneric()` from `infra/aws/embed/lambda_generic.ts`
- [ ] Delete file: `infra/aws/embed/lambda_generic.ts`
- [ ] Delete file: `infra/aws/app_api/lambda_generic.ts`

## Key Functions to Know

### In routing-utils.ts

```typescript
// Creates Lambda only (no routing)
createLambdaFunction(args: {
  name: string;
  dockerImage: pulumi.Input<string>;
  dockerCommand?: pulumi.Input<string[]>;
  environment?: pulumi.Input<{ [key: string]: pulumi.Input<string> }>;
  memorySize?: number;
  timeout?: number;
  roleArn: pulumi.Input<string>;
  securityGroupIds: pulumi.Input<string>[];
  subnetIds: pulumi.Input<string>[];
  architectures?: string[];
  ephemeralStorageSize?: number;
  tracingConfig?: aws.types.input.lambda.FunctionTracingConfig;
}): aws.lambda.Function

// Creates target group + ALB permissions
createLambdaTargetGroup(args: {
  name: string;
  lambda: aws.lambda.Function;
  vpcId: pulumi.Input<string>;
  healthCheck?: {...};
}): aws.lb.TargetGroup

// Simple single-target routing
createListenerRule(args: {
  name: string;
  listenerArn: pulumi.Output<string>;
  priority: number;
  targetGroupArn: pulumi.Output<string>;
  conditions: aws.types.input.lb.ListenerRuleCondition[];
}): aws.lb.ListenerRule

// Weighted multi-target routing with stickiness
createWeightedListenerRule(args: {
  name: string;
  listenerArn: pulumi.Output<string>;
  priority: number;
  targetGroups: Array<{
    arn: pulumi.Output<string>;
    weight: number;
  }>;
  conditions: aws.types.input.lb.ListenerRuleCondition[];
  stickinessEnabled?: boolean;
  stickinessDuration?: number;
}): aws.lb.ListenerRule
```

### In routing-rules.ts

```typescript
// Configure ALL routing rules in one centralized location
configureAllRouting(args: {
  publicListener: aws.lb.Listener;
  internalListener?: aws.lb.Listener;
  targetGroups: TargetGroups;
  stack: string;
  envName: string;
}): void

// Get environment-based routing percentages
getRoutingPercentages(stack: string): { rust: number; python: number }
// Returns: {rust: 100, python: 0} for staging/review
//          {rust: 0, python: 100} for production
```

## Testing the Refactor

After each phase:
```bash
cd infra
npm run build
npm run preview
```

Before deploying:
```bash
npm run up
```

## Common Mistakes to Avoid

1. **Don't create listener rules in Lambda creation functions anymore**
   - ❌ Old: `buildHttpLambdaFn()` creates rules
   - ✅ New: Only create Lambda + target group, rules go in `configureAllRouting()`

2. **Don't forget VPC ID for target group creation**
   - ❌ `createLambdaTargetGroup({ name: "...", lambda: ... })`
   - ✅ `createLambdaTargetGroup({ name: "...", lambda: ..., vpcId: ... })`

3. **Don't pass listener rules to createLambdaFunction**
   - ❌ `createLambdaFunction({ ..., lbRulePriority: 2100 })`
   - ✅ Use `configureAllRouting()` to set priorities

4. **Don't forget to collect target groups for routing**
   - ✅ Return all target groups from creation functions
   - ✅ Pass them to `configureAllRouting()`

## Performance Targets

After full refactoring, the new architecture enables:
- Weighted routing (0% Rust in prod, 100% in staging)
- Session stickiness (1-hour sticky sessions)
- Gradual Rust rollout (0% → 5% → 10% → 25% → 50% → 100%)
- No more ALB priority conflicts
- Easier maintenance (all rules in one place)

## Related Files for Reference

- Full analysis: `/workspace/project/WEIGHTED_ROUTING_CURRENT_STATE.md`
- Implementation guide: `/workspace/project/WEIGHTED_ROUTING_IMPLEMENTATION_GUIDE.md`
- New infrastructure: `/workspace/project/infra/lib/scorer/routing-utils.ts`
- Routing rules: `/workspace/project/infra/lib/scorer/routing-rules.ts`
- V2 API example: `/workspace/project/infra/aws/v2/index.ts`

