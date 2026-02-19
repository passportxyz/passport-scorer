---
status: pending
priority: p2
issue_id: "001"
tags: [code-review, rust, cleanup]
dependencies: []
---

# Redundant `%23` Replacement in Rust Handler

## Problem Statement

The Rust handler at `rust-scorer/src/api/handlers/internal.rs:208` still performs a manual `provider_id.replace("%23", "#")` replacement. However, Axum's `Path` extractor already automatically URL-decodes path parameters before they reach the handler. This means the `.replace()` call is a no-op that will never match anything.

The domain-layer double-decoding was correctly fixed in this PR (removed `urlencoding::decode()` from `domain/allow_list.rs`), but the handler-level replace was left behind. This creates confusion about Axum's URL decoding behavior and suggests the replacement is necessary when it is not.

## Findings

- **Python reviewer**: Flagged as IMPORTANT - "misleading, suggests the decoding is necessary when it is not"
- **Architecture strategist**: Flagged as MUST FIX - "undermines the fix's intent, creates inconsistent URL decoding behavior"
- **Pattern recognition**: Noted as matching Python's pattern at `api/account/api.py:643`, but Axum handles decoding differently than Django Ninja
- **Security sentinel**: Confirmed both Rust and Python paths produce correct results, but Rust replace is dead code
- **Simplicity reviewer**: Noted as pre-existing pattern, out of scope for this review

## Proposed Solutions

### Option A: Remove the replace (Recommended)
**Pros**: Cleaner code, eliminates dead code, matches Axum's built-in behavior
**Cons**: Minor divergence from Python handler pattern
**Effort**: Small (1 line removal + optional comment)
**Risk**: Very low - Axum path decoding is well-documented behavior

### Option B: Add a comment explaining it's defensive
**Pros**: Documents the Axum behavior difference for future developers
**Cons**: Keeps dead code in the codebase
**Effort**: Small (1 comment addition)
**Risk**: None

## Recommended Action

Option A - Remove the line and add a brief comment if needed.

## Technical Details

**Affected files**: `rust-scorer/src/api/handlers/internal.rs:208`

```rust
// Current (dead code):
let provider_id = provider_id.replace("%23", "#");

// Recommended: Remove the line. Axum's Path extractor already URL-decodes.
```

## Acceptance Criteria

- [ ] The `%23` replacement is removed from `internal.rs:208`
- [ ] Optional: Brief comment explaining Axum auto-decodes path parameters
- [ ] Comparison tests still pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-02-12 | Created | Identified during code review of NFT stamp feature |

## Resources

- PR branch: `3868-custom-nft-stamp`
- Axum Path extractor docs: automatically percent-decodes path parameters
- Python equivalent: `api/account/api.py:643` (Django Ninja does NOT auto-decode, so Python needs the replace)
