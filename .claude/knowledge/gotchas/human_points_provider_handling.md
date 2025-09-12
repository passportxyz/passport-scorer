# Human Points Provider Field Handling

## [2025-09-12] Django CharField NULL vs Empty String Behavior

The registry_humanpoints table provider field is defined as NOT NULL in the database, but Django's CharField with `null=False` has special NULL handling behavior:

- When Django saves a record with `provider=None`, it automatically converts to empty string `''`
- This is Django ORM's default behavior for CharField fields with null=False
- The database constraint allows empty strings but not NULL values

### Rust Implementation Requirements

The Rust implementation must match this Django behavior:
- Use empty strings `""` instead of NULL for provider field
- This applies to actions like scoring bonus where provider should be "empty"
- Provider-based actions (like staking) should still use actual provider names

### Affected Actions

Actions that should use empty string provider:
- **SCORING_BONUS (SCB)**: Empty string provider
- **METAMASK_OG (MTA)**: Empty string provider

Actions that use actual provider names:
- **HUMAN_KEYS (HKY)**: Provider from stamp
- **IDENTITY_STAKING_* (ISB/ISS/ISG)**: Provider from stamp
- **COMMUNITY_STAKING_* (CSB/CSE/CST)**: Provider from stamp
- **HUMAN_TECH_* stamps**: Provider from stamp

See `rust-scorer/src/human_points/processing.rs`, `api/registry/models.py`