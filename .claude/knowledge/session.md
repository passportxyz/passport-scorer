### [15:10] [tools] log-analyzer DEBUG level support
**Details**: The log-analyzer tool has been updated to handle DEBUG level tracing logs that contain SQL query information. The tool now:

1. Safely handles fields without "message" key using .get() instead of indexing
2. Falls back to "summary" field for SQL queries  
3. Displays SQL queries with timing information in format: [SQL elapsed_time] summary
4. Prevents panics when encountering logs with different field structures

The DEBUG logs contain SQL query details with fields like:
- summary: Brief SQL description
- db.statement: Full SQL query
- elapsed: Execution time
- rows_affected/rows_returned: Query results

This allows performance analysis of database operations in addition to application flow.
**Files**: rust-scorer/src/bin/log-analyzer.rs
---

