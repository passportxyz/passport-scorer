### [07:23] [gotcha] Human Points provider field nullability
**Details**: The registry_humanpoints table has a non-null constraint on the provider column, but some human points actions (like scoring bonus and provider-based actions) should have NULL provider values. The Rust implementation is incorrectly trying to insert NULL values where they should be allowed. Need to check the actual Django table schema to understand the correct constraint.
**Files**: rust-scorer/src/human_points/processing.rs
---

### [07:35] [gotcha] Django CharField NULL handling
**Details**: Django CharFields with null=False convert None values to empty strings ('') when saving to the database. This is a Django ORM behavior. In the registry_humanpoints table, the provider field is NOT NULL, so when Django saves records with provider=None, they become empty strings in the database. The Rust implementation must use empty strings, not NULL, to match this behavior.
**Files**: rust-scorer/src/human_points/processing.rs
---

