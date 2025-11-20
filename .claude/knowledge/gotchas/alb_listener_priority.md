# ALB Listener Rule Priority Ordering

## How ALB Priorities Work

ALB listener rules are evaluated in order from LOWEST to HIGHEST priority number. More specific rules (e.g., with additional header conditions) must have LOWER priority numbers to be evaluated first.

## Header-Based Routing Pattern

For header-based routing to work correctly:
- **Rust endpoints with X-Use-Rust-Scorer header**: priorities 2090-2093 (evaluated first)
- **Python endpoints without header requirement**: priorities 2100-2103 (evaluated second)

If the priorities were reversed, the less specific Python rules would match first and the Rust rules would never be evaluated.

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
