# Log Analyzer Tool

## Rust Tracing Log Performance Analyzer

Created a Rust binary `log-analyzer` that parses JSON tracing logs to generate performance analysis reports.

### Features

1. **ASCII flame chart** with elapsed time, delta times, and nested span visualization
2. **Color-coded performance indicators** 
   - Red for >50ms gaps
   - Yellow for >10ms gaps
3. **Performance bottleneck detection** (ignores startup time, only shows gaps during request processing)
4. **Span duration analysis**
5. **Folded stack format** for flamegraph generation with inferno

### Usage

```bash
cargo build --release --bin log-analyzer && ./rust-scorer/target/release/log-analyzer log
```

### Key Insights from Rust Scorer Analysis

- 4.2 second delay in API key validation (likely cold start DB connection issue)
- Actual scoring operations only take ~175ms after initial connection
- The logs show flat span structure (only one span level) because the Rust code doesn't create nested spans

### Compatibility

Works generically with any JSON tracing logs from tracing-subscriber configured with:
```rust
.json()
.with_current_span(true)
.with_span_list(true)
```

### Files

- `rust-scorer/src/bin/log-analyzer.rs` - Tool implementation

## [2025-09-12] Tool Removal

The custom log-analyzer tool will be removed as part of the telemetry migration. It was a custom tool built to parse JSON tracing logs and generate ASCII flame charts, but it's being replaced with proper OpenTelemetry distributed tracing that exports to Jaeger/X-Ray for professional visualization.

See `rust-scorer/TELEMETRY_IMPLEMENTATION_PLAN.md`