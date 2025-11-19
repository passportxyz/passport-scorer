## 📚 Mim Knowledge System

@.claude/knowledge/INSTRUCTIONS.md

@.claude/knowledge/KNOWLEDGE_MAP_CLAUDE.md

## 🦀 Rust Scorer Development

Before compiling the Rust scorer, run this to increase file descriptor limit (didkit requires many open files):
```bash
ulimit -n 4096
```

To run comparison tests:
```bash
cd rust-scorer/comparison-tests && cargo run --release
```