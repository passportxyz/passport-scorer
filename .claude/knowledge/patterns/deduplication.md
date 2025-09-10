# Deduplication Patterns

## LIFO Deduplication Retry Logic

The LIFO deduplication has a retry mechanism with 5 attempts to handle `IntegrityError` exceptions that occur during concurrent requests. 

### How it works:
- When two requests compete to claim the same hash, one will fail with IntegrityError
- This triggers a retry (up to 5 attempts)
- The retry logic is in `account/deduplication/lifo.py:21-36`
- After saving hash links, there's a verification step to ensure the expected number of links were created/updated

## Stamp Score Calculation - Provider Deduplication

When calculating scores, only the first stamp from each provider contributes to the score:

- If multiple stamps exist with the same provider, subsequent ones get a score of 0
- This happens in `scorer_weighted/computation.py` where it checks `if stamp.provider not in scored_providers`
- The `earned_points` dict tracks each provider's weight, setting duplicates to 0
- Implementation in `scorer_weighted/computation.py:46-69` and `scorer_weighted/computation.py:164-188`