# Wiki Deep Maintenance

Periodic verification that the wiki matches reality. Not scheduled — triggered when the human asks or when you notice significant drift.

## Quick Check

Scan `index.md`. For each page:
1. Does the linked file exist?
2. Does the one-line description still fit?

Fix broken links and stale descriptions immediately.

## Deep Verification

Use haiku subagents in parallel — one per wiki page. Each agent:
1. Reads the wiki page
2. Checks referenced files, functions, tables against the codebase (read, grep, git)
3. Reports: **accurate**, **needs update** (with specifics), or **obsolete**

Collect results. Apply fixes for clear inaccuracies. Flag ambiguous cases for the human.

## Post-Maintenance

Update `index.md` to reflect any added, merged, or removed pages. Keep it alphabetical within sections.
