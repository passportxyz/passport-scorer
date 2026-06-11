# Scorer Configuration Tables

Two functionally identical tables support binary and weighted scorers.

## Tables

- **scorer_weighted_binaryweightedscorer** (newer)
- **scorer_weighted_weightedscorer** (older, still in use)

Both have identical fields:
- scorer_ptr_id: References community.id
- weights: JSON field with provider weights
- threshold: Decimal threshold for binary scoring

## Historical Context

System only does binary scoring now, but both tables maintained for backward compatibility. Django's model inheritance creates this split in the database. WeightedScorer and BinaryWeightedScorer are functionally identical in Python.

## Implementation Requirements

Must check BOTH tables:

1. Try BinaryWeightedScorer first
2. Fall back to WeightedScorer if not found

Necessary because some scorers (e.g., scorer 4) are only in WeightedScorer table. Future cleanup should consolidate to single table.

## Lookup Pattern

```sql
SELECT weights, threshold FROM scorer_weighted_binaryweightedscorer
WHERE scorer_ptr_id = %(community_id)s

-- If not found:
SELECT weights, threshold FROM scorer_weighted_weightedscorer
WHERE scorer_ptr_id = %(community_id)s
```

Implementation: `rust-scorer/src/db/read_ops.rs`
