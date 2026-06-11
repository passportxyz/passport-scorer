# Weighted Routing Strategy

Percentage-based load balancing for gradual Rust scorer rollout without client changes.

## Configuration

Environment-based percentages in `infra/aws/v2/rust-scorer.ts`:
- **Staging/Review**: 100% Rust, 0% Python
- **Production**: 0% Rust, 100% Python (safe default)
- **Session stickiness**: 1 hour for user consistency

## Endpoints with Weighted Routing (6 Total)

- GET /v2/stamps/{scorer_id}/score/{address} (priority 2112)
- POST /ceramic-cache/stamps/bulk (priority 1032)
- POST /ceramic-cache/score/{address} (priority 1031)
- POST /internal/embed/stamps/{address} (priority 2104)
- GET /internal/embed/validate-api-key (priority 2105)
- GET /internal/embed/score/{scorer_id}/{address} (priority 2106)

Note: ceramic-cache/score uses POST method (not GET).

## Listener Rule Configuration

Single ALB listener rule per endpoint with weighted forward:

```typescript
{
  type: "forward",
  forwardConfig: {
    targetGroups: [
      { targetGroupArn: rustTargetGroup.arn, weight: percentRust },
      { targetGroupArn: pythonTargetGroup.arn, weight: percentPython }
    ],
    targetGroupStickinessConfig: {
      enabled: true,
      durationSeconds: 3600
    }
  }
}
```

Weights must sum to 100. Object-based lookup: `rustPercentages[environment] || 0`

## Gradual Rollout Process

1. Test in staging/review at 100% Rust
2. Production rollout steps:
   - 5% Rust, 95% Python
   - 10% Rust, 90% Python
   - 25% Rust, 75% Python
   - 50% Rust, 50% Python
   - 100% Rust, 0% Python
3. Monitor metrics between each step
4. Instant rollback: Set rust: 0, python: 100

## Monitoring Metrics

- TargetResponseTime: P50, P95, P99 latency
- HTTPCode_Target_4XX_Count: Client errors
- HTTPCode_Target_5XX_Count: Server errors
- Request count per target
- Connection count per target

Alarms threshold-based with PagerDuty integration.

## Implementation Details

Python target groups looked up by well-known names:
- l-passport-v2-stamp-score
- l-cc-v1-st-bulk-POST-0
- l-cc-v1-score-POST-0
- embed-st-lambda-target-group
- embed-rl-lambda-target-group
- embed-gs-lambda-target-group

Rust maintains separate target groups for public and internal ALBs (AWS constraint).

## Problem Resolution

Initial implementation tried to create rules at same priorities as Python, causing AWS PriorityInUse conflict. Solution: Priority ranges shifted to new values:
- V2 API: 2110-2112 (was 2021-2023)
- Ceramic Cache: 1030-1039 (was 1001-1010)
- Embed: 2104-2106 (was 2100-2103)

This enables clean deployment without manual AWS resource cleanup.

## Benefits

- No client code changes (no X-Use-Rust-Scorer header needed)
- Environment-specific control
- Instant rollback capability
- Session stickiness maintains user experience
- Metrics-driven incremental deployment
