# Rust Scorer Weighted Routing Configuration

## Overview

Implemented percentage-based load balancing for Rust scorer to replace header-based routing (X-Use-Rust-Scorer). This allows gradual rollout of the Rust implementation without client changes.

## Configuration

### Environment-Based Percentages
- **Staging/Review**: 100% Rust, 0% Python
- **Production**: 0% Rust, 100% Python (safe default)
- **Session stickiness**: 1 hour for consistent user experience

### Implementation Details

- Added `getRoutingPercentages()` function in rust-scorer.ts for environment-based percentages
- Updated all listener rules to use weighted target groups with forward.targetGroups array
- Python target groups looked up by well-known names:
  - l-passport-v2-stamp-score
  - embed-st-lambda-target-group
  - embed-rl-lambda-target-group
  - embed-gs-lambda-target-group
- Ceramic cache endpoints (Rust-only) conditionally created when routingPercentages.rust > 0
- Separate target group for internal ALB (l-passport-v2-rust-scorer-int) since AWS doesn't allow same target group on multiple ALBs

## Gradual Rollout Process

1. Test in staging/review at 100%
2. Production: Start at 5%, gradually increase (5% → 10% → 25% → 50% → 100%)
3. Monitor metrics:
   - TargetResponseTime
   - HTTPCode_Target_4XX_Count
   - HTTPCode_Target_5XX_Count
4. Instant rollback by setting rust: 0, python: 100

## Benefits

- No client changes needed (no special headers)
- Environment-specific control
- Gradual rollout capability
- Instant rollback if issues detected
- Session consistency via stickiness

## Technical Implementation

The weighted routing uses AWS ALB's native weighted target group feature:
```typescript
{
  type: "forward",
  forwardConfig: {
    targetGroups: [
      { targetGroupArn: rustTargetGroup.arn, weight: routingPercentages.rust },
      { targetGroupArn: pythonTargetGroup.arn, weight: routingPercentages.python }
    ],
    targetGroupStickinessConfig: {
      enabled: true,
      durationSeconds: 3600  // 1 hour
    }
  }
}
```

See: `infra/aws/v2/rust-scorer.ts`