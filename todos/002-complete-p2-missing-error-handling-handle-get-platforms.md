---
status: pending
priority: p2
issue_id: "002"
tags: [code-review, quality, consistency]
dependencies: []
---

# Missing Error Handling in handle_get_platforms

## Problem Statement

`handle_get_platforms()` in `api/embed/api.py` has no try/except error handling, unlike its sibling function `handle_get_embed_stamp_sections()` which wraps DB work in try/except and returns `[]` on failure. If the platforms query fails (database error, missing FK data), the entire `/internal/embed/config` endpoint will 500, even though weights and stamp_sections succeeded. Given known cold start and RDS Proxy connection acquisition issues in the embed Lambda, this is a real risk.

## Findings

- **Source**: TypeScript reviewer, Architecture strategist
- **Location**: `api/embed/api.py:251-311`
- **Sibling function with handling**: `api/embed/api.py:213-215`

## Proposed Solutions

### Option A: Add try/except in handle_get_platforms (Recommended)
```python
def handle_get_platforms(community_id, customization=None):
    try:
        # ... existing logic ...
    except Exception as e:
        log.error(f"Error fetching platforms for community {community_id}: {e}")
        return []
```
- **Pros**: Consistent with sibling function, graceful degradation
- **Cons**: None
- **Effort**: Small
- **Risk**: None

### Option B: Wrap at call site in handle_get_embed_config
- **Pros**: Keeps handle_get_platforms pure
- **Cons**: Inconsistent pattern across the file
- **Effort**: Small

## Recommended Action
Option A

## Technical Details
- **Affected files**: `api/embed/api.py`
- **Components**: Embed config endpoint

## Acceptance Criteria
- [ ] `handle_get_platforms()` returns empty list on database errors
- [ ] Error is logged with community_id context
- [ ] Config endpoint returns partial response (weights + sections) even if platforms fail
