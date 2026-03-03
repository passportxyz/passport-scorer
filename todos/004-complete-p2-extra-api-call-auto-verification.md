---
status: pending
priority: p2
issue_id: "004"
tags: [code-review, performance]
dependencies: []
---

# Extra Uncached API Call in Auto-Verification Handler

## Problem Statement

The `autoVerificationHandler` in `embed/src/handlers.ts` makes an additional HTTP call to `/internal/embed/config` on every auto-verification request to discover custom EVM credential IDs. This adds ~50-200ms latency per request (depending on Lambda cold-start state). The metadata handler already fetches this same config data in a separate user flow step, meaning the frontend already has this information.

## Findings

- **Source**: Architecture strategist, Performance oracle
- **Location**: `passport/embed/src/handlers.ts:112-128`
- **Impact**: Every auto-verification request gains an additional HTTP roundtrip
- **No caching**: Neither in-process nor Redis caching is applied

## Proposed Solutions

### Option A: Have frontend pass customEvmCredentialIds in request body (Recommended)
The frontend already has the config data from the metadata call. Pass the EVM credential IDs in the auto-verification request body instead of re-fetching.
- **Pros**: Eliminates extra API call entirely, zero latency impact
- **Cons**: Requires frontend change to pass data through
- **Effort**: Medium (changes request body schema)
- **Risk**: Low

### Option B: Add short-lived in-process cache keyed by scorerId
```typescript
const configCache = new Map<string, { ids: string[]; ts: number }>();
```
- **Pros**: No frontend change needed, simple
- **Cons**: Cache invalidation complexity, still makes the call on first request
- **Effort**: Small
- **Risk**: Low

### Option C: Add response-level caching to /internal/embed/config backend
```python
cache.set(f"embed_config_{community_id}", result, 60)
```
- **Pros**: Benefits all callers, not just auto-verification
- **Cons**: Doesn't eliminate the HTTP roundtrip from the embed service
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Option C as quick win (backend caching), Option A as longer-term improvement

## Technical Details
- **Affected files**: `passport/embed/src/handlers.ts`, `api/embed/api.py`

## Acceptance Criteria
- [ ] Auto-verification latency is not increased by this feature
