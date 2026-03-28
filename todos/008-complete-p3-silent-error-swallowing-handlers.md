---
status: pending
priority: p3
issue_id: "008"
tags: [code-review, observability, security]
dependencies: []
---

# Silent Error Swallowing in Auto-Verification Config Fetch

## Problem Statement

The `autoVerificationHandler` in `embed/src/handlers.ts` has a bare `catch {}` block that swallows ALL errors silently when fetching the embed config for custom EVM credentials. This removes observability for network errors, 500s, auth failures, or malformed responses.

## Findings

- **Source**: Security sentinel, Architecture strategist
- **Location**: `passport/embed/src/handlers.ts:126-128`

## Proposed Solutions

### Option A: Add warning log (Recommended)
```typescript
} catch (err) {
    console.warn("Failed to fetch embed config for custom EVM credentials:", err);
}
```
- **Pros**: Preserves non-fatal behavior while adding observability
- **Cons**: None
- **Effort**: Small

## Technical Details
- **Affected files**: `passport/embed/src/handlers.ts`

## Acceptance Criteria
- [ ] Config fetch failures are logged with context
- [ ] Auto-verification still succeeds when config fetch fails
