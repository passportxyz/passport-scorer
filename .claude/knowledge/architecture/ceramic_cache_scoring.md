# Ceramic Cache Scoring Integration

## Overview

The ceramic_cache module integrates with scoring at multiple points, creating performance bottlenecks through async_to_sync usage.

## Integration Points

### 1. Main Integration
`get_detailed_score_response_for_address()` calls `async_to_sync(handle_scoring_for_account)` - a major performance issue.

### 2. Endpoints Triggering Scoring
- **POST /ceramic-cache/stamps/bulk** - Add stamps and rescore
- **PATCH /ceramic-cache/stamps/bulk** - Update stamps and rescore
- **GET /ceramic-cache/score/{address}** - Get score

### 3. Performance Impact
The ceramic_cache scoring creates the same async_to_sync overhead problem as the embed Lambda, making it another critical performance bottleneck.

## Migration Strategy

### Short Term
Replace Python scoring call with HTTP call to Rust scorer

### Medium Term
Implement ceramic_cache endpoints in Rust

### Long Term
Full Rust migration

## Requirements for Rust Implementation

1. **Internal scoring endpoint** without auth (for ceramic_cache to call)
2. **Support for include_human_points** parameter
3. **InternalV2ScoreResponse** format compatibility

See: `api/ceramic_cache/api/v1.py`