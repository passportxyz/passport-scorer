# AWS Target Groups Cannot Span Multiple Load Balancers

## The Problem

AWS does not allow a single Lambda target group to be associated with more than one Application Load Balancer. When the same Lambda needs to serve requests from multiple ALBs (e.g., public and internal/private ALBs), you must create separate target groups for each ALB.

## Solution

- Create one target group per ALB
- Attach the same Lambda function to both target groups (with separate permissions)
- Use the appropriate target group ARN in listener rules for each ALB

## Example for Rust Scorer

- **rustScorerTargetGroup** (l-passport-v2-rust-scorer) - for public ALB endpoints (v2/stamps, ceramic-cache)
- **rustScorerInternalTargetGroup** (l-passport-v2-rust-scorer-int) - for internal ALB endpoints (embed)

## Error Message

```
TargetGroupAssociationLimit: The following target groups cannot be associated with more than one load balancer
```

See: `infra/aws/v2/rust-scorer.ts`
