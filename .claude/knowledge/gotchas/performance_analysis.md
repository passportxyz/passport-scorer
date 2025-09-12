# Performance Analysis Gotchas

## [2025-09-12] Flamegraphs vs Distributed Tracing for Production Analysis

Flamegraphs are CPU sampling profilers - they show where CPU time is spent but completely ignore I/O wait time. This makes them useless for analyzing I/O-heavy services like the rust-scorer which spends most time waiting on database queries.

For production latency analysis of I/O-bound services, you need:
1. Distributed tracing (OpenTelemetry) with wall-clock timing of operations
2. Simple structured logging with explicit timing measurements
3. Observability platforms (Datadog, AWS X-Ray, etc) that show waterfall charts with milliseconds

The tokio tracing spans show async runtime internals, not business logic timing. Need to explicitly create child spans or use timing measurements for each I/O operation to get useful data.

See `rust-scorer/PRACTICAL_TRACING.md`