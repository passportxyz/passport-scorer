# Deduplication Patterns

## LIFO Deduplication Retry Logic

The LIFO deduplication has a retry mechanism with 5 attempts to handle `IntegrityError` exceptions that occur during concurrent requests. 

### How it works:
- When two requests compete to claim the same hash, one will fail with IntegrityError
- This triggers a retry (up to 5 attempts)
- The retry logic is in `account/deduplication/lifo.py:21-36`
- After saving hash links, there's a verification step to ensure the expected number of links were created/updated

## Provider Deduplication in Score Calculation

Only the first stamp per provider contributes weight - subsequent stamps with the same provider get weight=0 and are added to deduped_stamps list. This is critical for correct scoring and matches Python behavior.

### Implementation Details:
- Provider deduplication occurs during score calculation after LIFO deduplication
- When multiple stamps have the same provider, only the first one gets its full weight
- Subsequent stamps with the same provider are marked with weight=0
- Deduped stamps are tracked in a separate deduped_stamps list
- This ensures fair scoring where users can't inflate scores with multiple stamps from the same provider

See `rust-scorer/src/scoring/calculation.rs`