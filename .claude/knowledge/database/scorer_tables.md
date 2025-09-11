# Scorer Configuration Tables

## WeightedScorer vs BinaryWeightedScorer Tables

There are two scorer configuration tables that are functionally identical:
- **scorer_weighted_binaryweightedscorer**
- **scorer_weighted_weightedscorer**

Both have the same fields:
- scorer_ptr_id (references community.id)
- weights (JSON field)
- threshold (decimal)

### Historical Context

This is a historical artifact: The system only does binary scoring now, but supports old weighted scorers for backward compatibility. Django's inheritance makes this weird in the database with two separate tables:
- scorer_weighted_binaryweightedscorer (newer)
- scorer_weighted_weightedscorer (older, but still used)

In Python, WeightedScorer inherits from BinaryWeightedScorerMixin and they're functionally identical now.

### Implementation Requirements

The Rust implementation needs to check BOTH tables:
1. Try BinaryWeightedScorer first
2. Fall back to WeightedScorer if not found

This is necessary because some scorers (like scorer 4) are in the WeightedScorer table, not BinaryWeightedScorer. This will be cleaned up in the future but for now both need to be supported.

See `rust-scorer/src/db/read_ops.rs`, `api/scorer_weighted/models.py`