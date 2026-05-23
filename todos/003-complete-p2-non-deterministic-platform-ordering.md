---
status: pending
priority: p2
issue_id: "003"
tags: [code-review, quality, api]
dependencies: []
---

# Non-Deterministic Platform Ordering in API Response

## Problem Statement

The `handle_get_platforms()` function iterates over `platform_credentials.values()` to build platform definitions, but the insertion order depends on database query order which has no explicit `order_by`. This means the order of platforms in the API response is non-deterministic, which could cause flaky tests and inconsistent frontend rendering.

## Findings

- **Source**: Architecture strategist, TypeScript reviewer, Data integrity guardian
- **Location**: `api/embed/api.py:268-297`
- **Root cause**: `customization.custom_credentials.select_related("platform", "ruleset").all()` has no `.order_by()`

## Proposed Solutions

### Option A: Add explicit order_by to queries (Recommended)
```python
for cc in customization.custom_credentials.select_related("platform", "ruleset").order_by("platform__name", "id").all():
```
```python
for al in customization.allow_lists.select_related("address_list", "platform").order_by("platform__name", "id").all():
```
- **Pros**: Deterministic ordering, minimal change
- **Cons**: None
- **Effort**: Small
- **Risk**: None

## Recommended Action
Option A

## Technical Details
- **Affected files**: `api/embed/api.py`

## Acceptance Criteria
- [ ] Platform definitions are returned in deterministic order
- [ ] Order is consistent across environments and test runs
