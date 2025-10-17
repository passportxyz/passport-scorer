# 🧠 Knowledge Remembering Protocol

You have access to the remember tool. You MUST use it PROACTIVELY to capture ALL discoveries about this project.

Use remember with these parameters:
- **category**: Type of knowledge (use descriptive categories like: architecture, pattern, dependency, workflow, config, gotcha, convention, api, database, testing, security, etc.)
- **topic**: Brief title of what you learned
- **details**: Specific information discovered
- **files**: Related file paths (optional)

✅ CAPTURE when discovering:
- How things actually work in this project
- Architecture, patterns, or conventions
- Configuration details or requirements
- Dependencies, integrations, or APIs
- Non-obvious behaviors or gotchas
- Workflows, processes, or project-specific details

❌ DON'T capture:
- Issues you're actively fixing in this session
- Requirements for the current in-flight issue
- Temporary debugging output
- Generic programming knowledge (not project-specific)

When in doubt, capture it - better to remember too much than miss important discoveries.

## ⚠️ Remember Knowledge First

Unless explicitly prompted by the user, do not create minor dev/LLM-facing documentation. Use remember instead.

## ⚠️ Automatic Mim Processing
After making commits with significant remembered knowledge, **run this command yourself**:
```bash
./mim-coalesce
```
This processes the `.claude/knowledge/session.md` file into organized documentation.
