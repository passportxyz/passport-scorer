# Score Calculation Gotchas

## Score Calculation Implementation Details

### Weight Lookup with Customization Support
The load_scorer_config function checks for customization overrides first via load_customization, then falls back to base scorer weights. **Important**: Customization uses custom weights but still takes threshold from base scorer.


### Binary Score Calculation
Exactly matches Python - returns Decimal(1) if raw_score >= threshold, else Decimal(0). Uses >= operator for threshold comparison (not just >).

### Decimal Type with Proper Precision
All weights and scores use rust_decimal::Decimal type for exact precision matching Python's Decimal. Will need 5 decimal place formatting when converting to API response.

### Earliest Expiration Tracking
Tracks the earliest expires_at timestamp from all valid stamps to set the score's expiration date.

### Clean Model Architecture
Scoring logic works with clean StampData models from LIFO result, applies weights, and builds ScoringResult that can be translated to Django format at boundaries.

See `rust-scorer/src/scoring/calculation.rs`