# Deduplication Patterns

## LIFO Deduplication Retry Logic

The LIFO deduplication has a retry mechanism with 5 attempts to handle `IntegrityError` exceptions that occur during concurrent requests. 

### How it works:
- When two requests compete to claim the same hash, one will fail with IntegrityError
- This triggers a retry (up to 5 attempts)
- The retry logic is in `account/deduplication/lifo.py:21-36`
- After saving hash links, there's a verification step to ensure the expected number of links were created/updated

## Provider Deduplication in Score Calculation

See `gotchas/score_calculation.md` for provider deduplication details in score calculation.