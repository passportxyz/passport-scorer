# ALB Listener Rule Priority Ordering

## How ALB Priorities Work

ALB listener rules are evaluated in order from LOWEST to HIGHEST priority number. More specific rules (e.g., with additional header conditions) must have LOWER priority numbers to be evaluated first.

## Current Priority Ranges (Updated Nov 24, 2025)

The project uses weighted routing (not header-based routing) with these priority ranges:
- **V2 API endpoints**: 2110-2112
- **Ceramic-cache endpoints**: 1030-1039
- **Internal embed endpoints**: 2104-2106

**Note**: Priorities were shifted Nov 24, 2025 to avoid AWS PriorityInUse conflicts with old listener rules.

## Example Configuration

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

See: `infra/aws/v2/rust-scorer.ts`, `infra/aws/embed/index.ts`
