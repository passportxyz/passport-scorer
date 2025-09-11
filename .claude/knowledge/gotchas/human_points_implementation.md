# Human Points Implementation Gotchas

## [2025-09-11] Human Points Implementation Details

Phase 6 implementation requirements clarified:

1. **Environment Variables**: Should be read from env using simple `std::env::var` approach (not complex config systems)
   - HUMAN_POINTS_ENABLED
   - HUMAN_POINTS_START_TIMESTAMP  
   - HUMAN_POINTS_MTA_ENABLED

2. **MetaMask OG List**: Directly query `account_addresslist` and `account_addresslistmember` tables with hardcoded queries, no fancy object modeling needed

3. **Human Keys Behavior**: Maintain exact Python behavior:
   - Use latest nullifier as tx_hash
   - Provider as dedup key
   - Only one Human Keys action per provider

4. **Transaction Consistency**: Keep Human Points operations within same transaction as score persistence for consistency

5. **Bulk Operations**: Use PostgreSQL UNNEST for bulk inserts rather than individual insert loops for performance

6. **Points Calculation**: 
   - Must exclude HIM actions from total points
   - Default multiplier is 1 (not 2 as documentation might suggest elsewhere)
   - Chain-specific actions use format: action_chainid in breakdown

See `rust-scorer/src/human_points/`