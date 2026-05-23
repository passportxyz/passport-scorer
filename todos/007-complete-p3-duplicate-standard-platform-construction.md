---
status: pending
priority: p3
issue_id: "007"
tags: [code-review, simplicity, typescript]
dependencies: []
---

# Duplicate Standard Platform Object Construction in metadata.ts

## Problem Statement

In `embed/src/metadata.ts`, the standard platform fallback has two code paths (lines 177-189 and 199-211) that construct nearly identical objects. The only differences are `icon`, `credentials`, and `displayWeight`. The 7 other properties are copy-pasted identically.

## Findings

- **Source**: Code simplicity reviewer, TypeScript reviewer
- **Location**: `passport/embed/src/metadata.ts:171-211`

## Proposed Solutions

### Option A: Merge into single code path (Recommended)
Handle missing `platformData` by defaulting providers to `[]`:
```typescript
const providers = platformData?.providers || [];
const icon = platformData?.PlatformDetails?.icon ? await getIcon(...) : "";
const credentials = providers.map(...);
return { platformId, name, description, ..., icon, credentials, displayWeight };
```
- **Pros**: Eliminates ~12 lines of duplication
- **Cons**: Slightly less explicit about the "no providers" case
- **Effort**: Small
- **Risk**: None (behavior identical)

## Technical Details
- **Affected files**: `passport/embed/src/metadata.ts`

## Acceptance Criteria
- [ ] Standard platform construction appears only once
- [ ] Tests still pass
