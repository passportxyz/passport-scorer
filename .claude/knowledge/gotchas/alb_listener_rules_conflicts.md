# ALB Listener Rule Conflicts and Solutions

## [2025-11-24] ALB Listener Rule Creation in Lambda Functions

The buildHttpLambdaFn function in infra/lib/scorer/new_service.ts:774 automatically creates a ListenerRule when creating a Lambda. This is the root cause of the weighted routing conflict - both Python Lambda creation (via buildHttpLambdaFn) and Rust weighted routing try to create rules at the same priority.

Similarly, createEmbedLambdaGeneric in infra/aws/embed/lambda_generic.ts also creates ListenerRules automatically.

The ceramic-cache lambdas are created via buildHttpLambdaFn calls in infra/aws/index.ts with priorities:
- 1001: ceramic_cache_score_POST
- 1002: ceramic_cache_stamps_bulk_POST
- 1003: ceramic_cache_stamps_bulk_PATCH
- 1004: ceramic_cache_stamps_bulk_DELETE

These automatic rule creations conflict with the weighted routing rules that need to be at the same priorities to replace them.

## [2025-11-24] ALB Listener Rule Priority Conflicts

When refactoring infrastructure, old listener rules can persist in AWS even after code is removed. This causes "PriorityInUse" errors when trying to create new rules with the same priorities.

Solution: Shift all conflicting priorities to new values rather than manually cleaning up AWS resources.

Priority changes made:
- V2 API: 2021→2110, 2023→2112
- Ceramic Cache: 1000-1010 → 1011-1020
- Embed (internal ALB): 2100-2103 → 2104-2106

This allows clean deployment in both staging and production without downtime or manual AWS cleanup.

See: `infra/lib/scorer/new_service.ts`, `infra/lib/scorer/routing-rules.ts`, `infra/aws/v2/rust-scorer.ts`, `infra/aws/index.ts`