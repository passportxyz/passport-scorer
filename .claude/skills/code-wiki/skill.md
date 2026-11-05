# Code Wiki

A persistent, agent-maintained knowledge base that lives at `/wiki/` in the repo root. Browsable on GitHub. All markdown.

## Structure

```
/wiki/
  index.md          ← loaded into context via CLAUDE.md
  architecture/     ← what & why: design, history, decisions
  development/      ← how: gotchas, setup, processes
```

`index.md` is a flat list of one-line entries. Each links to a wiki page with a terse description. This is the only file that goes into context (via `@wiki/index.md` in CLAUDE.md).

## Index Format

```markdown
- [Page Title](path/to/page.md) — terse description of what's in this page
```

One line per page. Description should be specific enough that you know when to read it.

## Terseness

This is the north star. Wiki pages must be:
- **Short.** Say it once. No restating.
- **Specific.** Code paths, table names, concrete details. Not generalities.
- **Scannable.** Headers, bullets, code blocks. No prose paragraphs.
- **No filler.** No "This document describes..." or "Overview" sections that restate the title.

A wiki page should read like a senior engineer's notes, not documentation.

## When to Read the Wiki

- **Before planning.** Check the index for pages related to what you're about to touch.
- **Before any big change.** Read relevant architecture pages so you don't contradict existing design.
- **When you hit something unexpected.** Grep the wiki before investigating from scratch.
- **When the index description sounds relevant.** Read the page.

Search: use `index.md` first. If that doesn't point you to what you need, grep `/wiki/`.

## When to Write to the Wiki

- **After completing a big task.** If you learned something non-obvious, add it.
- **When you discover a gotcha.** Write it up immediately.
- **When you find the wiki was wrong.** Fix it right then. Code is truth.
- **When you explain something to the user that isn't in the wiki.** That explanation probably belongs there.

Don't write wiki pages for things that are obvious from reading the code. Write them for things you'd forget in two weeks.

## When to Fix the Wiki

- **You read a page and it contradicts the code.** Fix it now. No asking.
- **A file/function/table it references doesn't exist.** Fix or remove the reference.
- **You notice a page is redundant with another.** Merge them, update the index.

These are factual corrections. Just do them.

## When to Ask the Human

- Reorganizing the wiki structure
- Deleting a page entirely
- Anything about design philosophy where you're unsure of intent

## Page Template

```markdown
# Title

One-line summary.

## Section

Content. Be terse.
```

No frontmatter. No metadata. No timestamps in the content — git handles history.

## Deep Maintenance

@code-wiki/maintenance.md
