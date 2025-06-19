# Human Points Program - Indexer Implementation Spec

## Overview
Modify the existing Rust indexer to track on-chain minting events for the Human Points Program.

## Scope
The indexer will track two types of on-chain events:
1. **Passport Mints** - Track mints across multiple chains
2. **Holonym SBT Mints** - Track only on Optimism

## Database Integration
Write directly to the `HumanPoints` table in the scorer database:

```sql
INSERT INTO registry_humanpoints (address, action, points, timestamp, tx_hash)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT DO NOTHING;
```

## Event Types to Track

### 1. Passport Mints
- **Action**: `passport_mint`
- **Points**: 300 per mint (per chain)
- **Chains**: [TO BE FILLED - list of chains where passport can be minted]
- **Contract**: [TO BE FILLED]
- **Event**: [TO BE FILLED]

### 2. Holonym SBT Mints
- **Action**: `holonym_mint`
- **Points**: 1000 per mint
- **Chain**: Optimism only
- **Contract**: [TO BE FILLED]
- **Event**: [TO BE FILLED]

## Implementation Notes

### Multiplier Handling
- Check if minting address exists in `HumanPointsMultiplier` table
- If exists, multiply points by the multiplier value before insertion
- Query: `SELECT multiplier FROM registry_humanpointsmultiplier WHERE address = $1`

### Data to Extract from Events
- `address`: The minter's address (convert to lowercase)
- `tx_hash`: Transaction hash for deduplication
- `timestamp`: Block timestamp
- `chain_id`: For identifying which chain the mint occurred on

### Database Writes
- Use the existing database connection pool
- Batch inserts where possible for efficiency
- Handle conflicts gracefully (ON CONFLICT DO NOTHING)
- Log successful point additions for monitoring

### Example Flow
```rust
// Pseudo-code
on_passport_mint_event(event) {
    let address = event.minter.to_lowercase();
    let multiplier = get_multiplier(address).unwrap_or(1);
    let points = 300 * multiplier;
    
    insert_points(
        address,
        "passport_mint",
        points,
        event.timestamp,
        event.tx_hash
    );
}
```

## Configuration
Add configuration for:
- Enable/disable points tracking
- Points values per action type
- Contract addresses per chain
- Event signatures

## Temporary Nature
This implementation is temporary for the points program duration. Consider:
- Feature flag to enable/disable points tracking
- Easy way to stop indexing without breaking existing functionality
- Clean separation from core indexing logic

## Testing
- Test duplicate handling (same tx_hash)
- Test multiplier application
- Test multi-chain passport mint tracking
