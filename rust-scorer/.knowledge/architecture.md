# Clean Architecture Pattern for Rust API

## Core Principle

Handlers should be THIN - just pick auth, call shared logic, format response

## Three-Layer Architecture

### 1. API Layer (api/)
HTTP concerns only:
- Thin handlers that just orchestrate
- Authentication decisions
- Request parsing and response formatting
- NO business logic

### 2. Domain Layer (domain/)
Shared business logic:
- Pure business logic, no HTTP types
- Takes primitives or domain types as input
- Returns domain types (Result<T, DomainError>)
- Used by BOTH internal and external handlers
- Examples: scoring.rs, bans.rs, stakes.rs, weights.rs

### 3. Data Layer (db/)
Database operations:
- Raw SQL queries in db/queries/
- Database result types in db/models/
- Transaction management

## Benefits

- **Shared logic** = no duplication (ban checking used by 3+ endpoints)
- **Thin handlers** = easy to test (can mock domain layer)
- **Clean boundaries** = maintainable (changes don't cascade)
- **Future flexibility** = easy to add GraphQL/gRPC (new handlers, same logic)

## Example Flow

```
External API → Handler (auth required) → domain::scoring::calculate() → db::queries
Internal API → Handler (no auth) → domain::scoring::calculate() → db::queries
```

Both use exact same business logic, just different auth at handler level.

## Module Organization Pattern

- Flat file structure in each layer (handlers/, domain/, db/queries/)
- Domain-specific query modules in `db/queries/` (bans.rs, stakes.rs, cgrants.rs)
- Domain models separate from Django models in `db/models/`
- Internal API types in `models/internal/`

## Implementation Principles

1. **LIVE MIGRATION** - exact behavior match, no logic changes
2. Clean separation of concerns (handlers → domain → database)
3. Reuse existing connection pool and infrastructure
4. Group related endpoints in same module (e.g., all stake endpoints in stakes.rs)

## Key Design Decisions

- All internal endpoints in same Lambda as existing rust-scorer (simpler deployment)
- No authentication needed for internal endpoints (internal ALB handles this)
- Match Python's empty data behavior exactly (return empty arrays, not 404s)
- Use prepared statements and recommend indexes for performance

See: `INTERNAL_API_RUST_MIGRATION_GUIDE.md`
