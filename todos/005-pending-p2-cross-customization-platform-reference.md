---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, data-integrity]
dependencies: []
---

# No Constraint Preventing Cross-Customization Platform Reference

## Problem Statement

The new `AllowList.platform` FK has no validation ensuring the referenced `CustomPlatform` belongs to the same `Customization`. An admin could accidentally assign an AllowList under Customization A to a CustomPlatform created for Customization B. The admin autocomplete widget shows ALL CustomPlatforms, not just those associated with the current Customization.

## Findings

- **Source**: Data integrity guardian
- **Location**: `api/account/models.py:742-748`, `api/account/admin.py:697`
- **Root cause**: `CustomPlatform` has no FK to `Customization` (the join is through `CustomCredential`)

## Proposed Solutions

### Option A: Add clean() validation on AllowList (Recommended)
```python
def clean(self):
    if self.platform and self.customization:
        # Verify platform is used by this customization's credentials
        if not self.customization.custom_credentials.filter(platform=self.platform).exists():
            raise ValidationError("Platform must belong to this customization")
```
- **Pros**: Catches misconfiguration at save time, admin-friendly error
- **Cons**: Only enforces in Django, not at DB level
- **Effort**: Small
- **Risk**: None

### Option B: Limit autocomplete queryset in admin
Override `formfield_for_foreignkey()` on `AllowListInline` to filter CustomPlatforms.
- **Pros**: Prevents the issue in the admin UI
- **Cons**: Only enforces in admin, not programmatic access
- **Effort**: Small

## Recommended Action
Option A (validation) + Option B (admin UX)

## Technical Details
- **Affected files**: `api/account/models.py`, `api/account/admin.py`

## Acceptance Criteria
- [ ] Saving AllowList with a platform from a different customization raises validation error
- [ ] Admin autocomplete only shows relevant platforms
