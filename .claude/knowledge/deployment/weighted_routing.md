# Rust Scorer Weighted Routing Configuration

## Overview

Implemented percentage-based load balancing for Rust scorer to replace header-based routing (X-Use-Rust-Scorer). This allows gradual rollout of the Rust implementation without client changes.

## Configuration

### Environment-Based Percentages
- **Staging/Review**: 100% Rust, 0% Python
- **Production**: 0% Rust, 100% Python (safe default)
- **Session stickiness**: 1 hour for consistent user experience

### Implementation Details

- Object-based lookup instead of switch: `rustPercentages[environment] || 0`
- Updated all listener rules to use weighted target groups with forward.targetGroups array
- Python target groups looked up by well-known names:
  - l-passport-v2-stamp-score
  - l-cc-v1-st-bulk-POST-0 (ceramic cache stamps bulk POST)
  - l-cc-v1-score-POST-0 (ceramic cache score POST)
  - embed-st-lambda-target-group
  - embed-rl-lambda-target-group
  - embed-gs-lambda-target-group
- Ceramic cache endpoints DO exist in Python (api/ceramic_cache/api/v1.py)
- Using existing Python priorities to replace Python rules (not creating new rules)
- ceramic-cache/score uses POST method, not GET
- All weighted rules have session stickiness (1 hour)
- Separate target group for internal ALB (l-passport-v2-rust-scorer-int) since AWS doesn't allow same target group on multiple ALBs

### Listener Rule Priorities (Updated Nov 24, 2025)

**Priority Shift**: All priorities shifted to avoid AWS PriorityInUse conflicts

Current listener rule priorities:
1. V2 stamps score (GET /v2/stamps/*/score/*): priority **2112**, target: l-passport-v2-stamp-score
2. Ceramic-cache stamps bulk (POST): priority **1032**, target: l-cc-v1-st-bulk-POST-0
3. Ceramic-cache score (POST): priority **1031**, target: l-cc-v1-score-POST-0
4. Embed stamps (POST /internal/embed/stamps/*): priority **2104**, target: embed-st-lambda-target-group
5. Embed validate-api-key (GET): priority **2105**, target: embed-rl-lambda-target-group
6. Embed score (GET): priority **2106**, target: embed-gs-lambda-target-group

**Note**: Priority numbers shifted from old ranges (2023→2112, 1001-1010→1030-1039, 2100-2103→2104-2106) to enable clean deployment without manual AWS cleanup.

### Implementation Challenges

**Critical Blocker Resolved**: AWS ALB doesn't allow two listener rules with the same priority. The initial implementation tried to create rules at the same priorities as existing Python rules, which would cause AWS errors.

**Solution Applied**: Refactored Lambda creation functions (buildHttpLambdaFn and createEmbedLambdaGeneric) to optionally skip listener rule creation, allowing manual creation of ONE set of weighted rules for dual-implementation endpoints instead of having conflicting rules.

8 endpoints need weighted routing for gradual migration:
- /v2/stamps/*/score/* (GET)
- /ceramic-cache/stamps/bulk (POST, PATCH, DELETE)
- /ceramic-cache/score/* (POST)
- /internal/embed/stamps/* (POST)
- /internal/embed/validate-api-key (GET)
- /internal/embed/score/*/* (GET)

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