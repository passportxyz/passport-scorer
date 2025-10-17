# Type Conversion Requirements

## Type Conversions Between Modules

Multiple type conversions are needed between modules:

1. **ValidatedCredential → ValidStamp**: From auth module to internal model for scoring
2. **StampData → ValidStamp**: From LIFO result for bulk_insert_stamps
3. **StampData → StampInfo**: For insert_dedup_events conversion
4. **DjangoScoreFields.stamps**: Must be HashMap<String, DjangoStampScore>, not JSON value
5. **ceramic_cache entries → Vec<serde_json::Value>**: For validate_credentials_batch

These conversions are necessary because each module uses its own types optimized for its purpose, requiring translation at boundaries.

## Implementation Pattern

Each module maintains its own optimized types:
- Auth module: ValidatedCredential for credential validation
- LIFO module: StampData for deduplication results
- Database module: ValidStamp for persistence
- Event module: StampInfo for event recording

Translation happens at module boundaries to maintain separation of concerns.

See `rust-scorer/src/api/handler.rs`