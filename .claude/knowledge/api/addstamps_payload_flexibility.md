# AddStampsPayload scorer_id Type Flexibility

## Type Handling

The AddStampsPayload struct accepts scorer_id as either a string or integer to handle clients that send it in either format. This improves API compatibility with clients that serialize scorer_id differently.

## Implementation

### Initial Approach (Abandoned)
Used a custom deserializer `deserialize_scorer_id` that accepts both i64 integers and strings that can be parsed to i64.

### Current Approach (Explicit)
AddStampsPayload now explicitly handles scorer_id accepting both string and integer from JSON (matching Python's Pydantic behavior) but stores it as String type. The handler code explicitly calls `parse_scorer_id()` to convert to i64, making the type conversion visible and intentional rather than magic.

This is more explicit than Python's implicit coercion while maintaining API compatibility.

See: `rust-scorer/src/models/v2_api.rs`, `rust-scorer/src/api/embed.rs`, `rust-scorer/src/models/tests.rs`
