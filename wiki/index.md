# Passport Scorer Wiki

## Architecture

- [Scoring Flow](architecture/scoring-flow.md) — V2 scoring endpoint pipeline, event recording, ceramic cache integration, Rust migration requirements
- [API Endpoints](architecture/api-endpoints.md) — Complete map of all 15+ endpoints across V2, internal, embed, and ceramic-cache
- [API Authentication](architecture/api-authentication.md) — API key PBKDF2/SHA-256 dual-path verification, auto-migration, failed auth tracking
- [Rust Scorer](architecture/rust-scorer.md) — Implementation status for all 15 endpoints, three-layer architecture, performance targets
- [Lambda Infrastructure](architecture/lambda-infrastructure.md) — Pulumi deployment, ALB routing, priority ranges, Docker Lambda setup
- [Weighted Routing](architecture/weighted-routing.md) — Percentage-based Rust/Python load balancing, gradual rollout, session stickiness
- [Human Points](architecture/human-points.md) — Points system with 8 action types, scoring bonus, MetaMask OG, bulk operations
- [Internal API](architecture/internal-api.md) — 12 VPC-internal endpoints with SQL queries, schema details, auth notes
- [CGrants Endpoint](architecture/cgrants-endpoint.md) — Contributor statistics from grants + protocol sources, squelch handling
- [Scorer Tables](architecture/scorer-tables.md) — BinaryWeightedScorer vs WeightedScorer dual-table lookup pattern
- [Partner Dashboards](architecture/partner-dashboards.md) — Dashboard discovery via Customization model, TopNav integration
- [TopNav Dashboards](architecture/topnav-dashboards.md) — show_in_top_nav fields, API response, admin config
- [Embed Customization](architecture/embed-customization.md) — EmbedStampSection models, stamp metadata, /embed/config endpoint
- [Custom Stamps](architecture/custom-stamps.md) — Three-model credential framework, provider ID generation, frontend consumption

## Development

- [Gotchas](development/gotchas.md) — 17 gotchas: scorer_id vs community_id, nullifiers, Django schema, V2 never implemented, and more
- [Database Performance](development/database-performance.md) — LOWER() breaks indexes, RDS Proxy connection delays, Lambda cold starts, CONN_MAX_AGE
- [Infrastructure Gotchas](development/infrastructure-gotchas.md) — ALB listener priorities, rule conflicts, target group multi-ALB limitation
- [Patterns](development/patterns.md) — LIFO dedup retry, provider dedup, Django model patterns, custom credential system
- [Config](development/config.md) — Django database connections, OpenTelemetry ADOT sidecar setup
- [Dependencies](development/dependencies.md) — DIDKit for credential validation, Valkey/Redis for Django caching
- [Dev Setup](development/dev-setup.md) — Container/Ubuntu setup scripts with micromamba, PostgreSQL userspace
- [Setup Guide](development/setup-guide.md) — Modular setup scripts, SQLX offline mode, environment detection, troubleshooting
- [Rust Scorer Dev](development/rust-scorer-dev.md) — Three-layer architecture, testing strategy, comparison tests, code organization
