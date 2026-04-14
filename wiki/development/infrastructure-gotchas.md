# Infrastructure Gotchas

AWS ALB listener rules, Lambda target groups, and deployment configuration issues.

## ALB Listener Rule Priority Ordering

ALB listener rules are evaluated in order from LOWEST to HIGHEST priority number. More specific rules (e.g., with additional header conditions) must have LOWER priority numbers to be evaluated first.

### Current Priority Ranges (Updated Nov 24, 2025)

The project uses weighted routing (not header-based routing) with these priority ranges:
- **V2 API endpoints**: 2110-2112
- **Ceramic-cache endpoints**: 1030-1039
- **Internal embed endpoints**: 2104-2106

Priorities were shifted Nov 24, 2025 to avoid AWS PriorityInUse conflicts with old listener rules.

### Example Configuration

```typescript
// Rust rule (more specific) - LOWER priority number
listener.addTargetGroups("RustScorer", {
  priority: 2090,
  conditions: [
    elbv2.ListenerCondition.pathPatterns(["/v2/stamps/*/score/*"]),
    elbv2.ListenerCondition.httpHeader("X-Use-Rust-Scorer", ["true"])
  ],
  targetGroups: [rustScorerTargetGroup]
});

// Python rule (less specific) - HIGHER priority number
listener.addTargetGroups("PythonScorer", {
  priority: 2100,
  conditions: [
    elbv2.ListenerCondition.pathPatterns(["/v2/stamps/*/score/*"])
  ],
  targetGroups: [pythonScorerTargetGroup]
});
```

See `infra/aws/v2/rust-scorer.ts`, `infra/aws/embed/index.ts`.

## ALB Listener Rule Creation Conflicts

The buildHttpLambdaFn function in infra/lib/scorer/new_service.ts:774 automatically creates a ListenerRule when creating a Lambda. This is the root cause of the weighted routing conflict - both Python Lambda creation (via buildHttpLambdaFn) and Rust weighted routing try to create rules at the same priority.

Similarly, createEmbedLambdaGeneric in infra/aws/embed/lambda_generic.ts also creates ListenerRules automatically.

The ceramic-cache lambdas are created via buildHttpLambdaFn calls in infra/aws/index.ts with priorities:
- 1001: ceramic_cache_score_POST
- 1002: ceramic_cache_stamps_bulk_POST
- 1003: ceramic_cache_stamps_bulk_PATCH
- 1004: ceramic_cache_stamps_bulk_DELETE

These automatic rule creations conflict with the weighted routing rules that need to be at the same priorities to replace them.

## ALB Listener Rule Priority Conflicts

When refactoring infrastructure, old listener rules can persist in AWS even after code is removed. This causes "PriorityInUse" errors when trying to create new rules with the same priorities.

**Solution**: Shift all conflicting priorities to new values rather than manually cleaning up AWS resources.

### Priority Shift History

1. **First shift**: V2 API (2021→2110, 2023→2112), Ceramic Cache (1000-1010 → 1011-1020), Embed (2100-2103 → 2104-2106)
2. **Second shift (2025-11-24)**: Ceramic Cache range shifted again (1011-1020 → 1030-1039) to skip ALL old rules

### Current Priority Assignments

- **V2 API**: 2110 (models-score), 2112 (stamps-score)
- **Ceramic Cache**: 1030-1039 (submit, score, stamps bulk, weights, etc.)
- **Embed (internal ALB)**: 2104-2106
- **App API**: 3000-3001

### Old Priorities to Avoid

1001-1020, 2021, 2023, 2100-2103

### Long-term Fix

Delete old AWS listener rules manually or via AWS CLI when safe to do so. This allows clean deployment in both staging and production without downtime or manual AWS cleanup. See `infra/lib/scorer/new_service.ts`, `infra/lib/scorer/routing-rules.ts`, `infra/aws/v2/rust-scorer.ts`, `infra/aws/index.ts`.

## Target Groups Cannot Span Multiple Load Balancers

AWS does not allow a single Lambda target group to be associated with more than one Application Load Balancer. When the same Lambda needs to serve requests from multiple ALBs (e.g., public and internal/private ALBs), you must create separate target groups for each ALB.

### Solution

- Create one target group per ALB
- Attach the same Lambda function to both target groups (with separate permissions)
- Use the appropriate target group ARN in listener rules for each ALB

### Example for Rust Scorer

- **rustScorerTargetGroup** (l-passport-v2-rust-scorer) - for public ALB endpoints (v2/stamps, ceramic-cache)
- **rustScorerInternalTargetGroup** (l-passport-v2-rust-scorer-int) - for internal ALB endpoints (embed)

### Error Message

```
TargetGroupAssociationLimit: The following target groups cannot be associated with more than one load balancer
```

See `infra/aws/v2/rust-scorer.ts`.
