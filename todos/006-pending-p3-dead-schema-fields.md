---
status: pending
priority: p3
issue_id: "006"
tags: [code-review, simplicity, yagni]
dependencies: []
---

# Dead Schema Fields in PlatformDefinitionSchema

## Problem Statement

`PlatformDefinitionSchema` has 3 fields that are never populated by any backend code: `documentation_link`, `popup_url`, and `requires_sdk_flow`. They always serialize as their defaults (None/False). This is a YAGNI violation that adds noise to the API contract and suggests capabilities that don't exist.

## Findings

- **Source**: Code simplicity reviewer
- **Location**: `api/embed/api.py:152-156`
- **Evidence**: No model field, no lookup, nothing populates these fields for custom platforms

## Proposed Solutions

### Option A: Remove the 3 dead fields (Recommended)
Remove `documentation_link`, `popup_url`, `requires_sdk_flow` from `PlatformDefinitionSchema`.
- **Pros**: Honest API contract, less noise
- **Cons**: Frontend type definition would need updating if it reads these
- **Effort**: Small
- **Risk**: Low (frontend reads undefined which equals current null/false defaults)

## Technical Details
- **Affected files**: `api/embed/api.py`, `passport/embed/src/metadata.ts`

## Acceptance Criteria
- [ ] PlatformDefinitionSchema only contains fields that are actually populated
