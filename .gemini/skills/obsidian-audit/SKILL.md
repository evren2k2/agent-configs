---
name: obsidian-audit
description: Audit the Obsidian vault for organizational health — broken links, naming violations, misplaced notes, sync status, stale content, and connection quality
---

# Obsidian Vault Audit

Run this periodically or after large note-creation sessions to ensure the vault stays healthy and useful.

## When to Run
- After any session that creates 3+ notes
- Weekly if the vault is actively growing
- When the user asks to review vault health
- When sync issues are suspected
- After a subagent creates vault content (verify it followed conventions)

## Audit Checklist

Perform each check in order. Report findings in the scorecard at the end.

### 1. Sync Health

```bash
crontab -l | grep server-sync
tail -20 ~/obsidian_notes/scripts/sync.log
git -C ~/obsidian_notes status
git -C ~/obsidian_notes log --oneline origin/main..HEAD
git -C ~/obsidian_notes log --oneline HEAD..origin/main
```

**Pass:** Cron active, no stuck uncommitted files, local and remote in sync.

### 2. Folder Placement

```bash
find ~/obsidian_notes -name "*.md" -not -path "*/.obsidian/*" -not -path "*/.git/*" | sort
```

Check every file:
- `inbox/` — unsorted, temporary. Anything >2 weeks old is stale.
- `projects/` — time-bound work (grouped by `project:` frontmatter, no hub files).
- `areas/` — durable domain knowledge (promoted from projects/ when reused).
- `library/` — atomic reference notes, papers, tools.
- `personal/` — goals, journal, personal context.
- `agent/` — session-log, open-questions, connections, instincts, context files.

**Flag:** Any `.md` in vault root (except README.md). Any note mismatching its folder's purpose.

### 3. Subfolder Structure & Frontmatter Grouping

- Projects with 2+ notes MUST use a subfolder (e.g., `projects/teknofest/`)
- **No `_index.md` hub files.** Project grouping uses `project:` frontmatter.
- Every note in `projects/` MUST have a `project:` field in frontmatter.
- No prefix-based flat naming (`projects/proj-arch.md`, `projects/proj-bugs.md`)
- Do NOT create generic hub filenames (`Home.md`, `_index.md`, `index.md`). Use descriptive project-prefixed names.

**Flag:** Notes in `projects/` missing `project:` frontmatter. Collision-prone filenames (`Home.md`, `_index.md`, `index.md`). Multiple notes with same prefix in a flat folder.

### 4. Naming Conventions

Every `.md` file should be:
- `YYYY-MM-DD-topic.md` (time-anchored) or `topic.md` / `topic-subtopic.md` (evergreen)
- **Lowercase-hyphenated only**

**Flag:** Spaces, CamelCase, uppercase (except README.md), generic names (`notes.md`, `temp.md`).

### 5. Frontmatter Validation (CRITICAL)

**Every note** (except README.md and `agent/` running logs) MUST have YAML frontmatter:

```yaml
---
date: YYYY-MM-DD
tags: [category, ...]
type: concept          # concept | decision | log | mission
status: active         # backlog | active | completed | archived
project: my-project    # required for notes in projects/
---
```

```bash
# Notes with type/status reported as "?" are missing frontmatter (or have malformed
# frontmatter the indexer couldn't parse).
vault query --type "?" --json
vault query --status "?" --json
# Fallback raw scan:
for f in $(find ~/obsidian_notes -name "*.md" -not -path "*/.obsidian/*" -not -path "*/.git/*"); do
    if ! head -1 "$f" | grep -q "^---"; then
        echo "MISSING FRONTMATTER: $f"
    fi
done
```

**Flag:** Missing frontmatter, missing `date`, empty `tags`, missing `type` or `status`. This was the #1 failure in stress testing — enforce strictly.

### 6. Wikilink Integrity

```bash
grep -roh '\[\[[^]]*\]\]' ~/obsidian_notes/ --include="*.md" | sort -u
```

For each wikilink, verify target exists. Classify as:
- **Broken**: Target doesn't exist and wasn't intentional
- **Pending**: Aspirational link to a note not yet created (acceptable)

**Flag:** Broken links. Also flag notes with ZERO outgoing wikilinks (orphan sources).

### 7. Orphaned Notes (Informational)

A note is orphaned if:
- Not linked FROM any other note
- Not a `agent/` system file or README

**This is a flag for review, NOT an automatic fix.** Only add a link if there's a genuine conceptual connection. Standalone reference notes (especially in `library/`) are often legitimately orphaned — they're found by search, not by graph traversal. Do NOT add forced links just to pass the audit.

```bash
# Authoritative orphan list (built from the cached graph index):
vault orphans
# Use --json to feed into a hygiene script.
```

**Flag:** Orphaned notes that should be linked. `inbox/` notes are exempt.

### 8. Content Quality

Read a sample of notes and check:
- **Reasoning present**: Does the note explain WHY, not just WHAT?
- **Tradeoffs documented**: Are alternatives and decisions captured?
- **Non-obvious insights**: Would this save a future Claude >5 minutes?
- **Not a README restatement**: Does it add value beyond what's in the source repo?

**Flag:** Notes that merely restate source material without adding reasoning or connections.

### 9. Note Size

```bash
find ~/obsidian_notes -name "*.md" -not -path "*/.obsidian/*" -not -path "*/.git/*" -exec wc -l {} + | sort -rn | head -10
```

- **Target**: 200-400 lines
- **Flag**: >800 lines (should be split)
- **Flag**: <10 lines (should be merged into another note)

### 10. Stale Content & Inbox Hygiene

Check `agent/session-log.md`:
- Open items from >2 weeks ago that were never resolved?

Check `agent/open-questions.md`:
- Questions now answered (in codebase or vault)?
- Questions no longer relevant?

Check `inbox/`:
- Items sitting >2 weeks without processing?

**Flag:** Stale open questions, unprocessed inbox items, outdated log entries.

### 11. Connection Quality

Read `agent/connections.md`:
- Are connections genuine cross-domain links (not forced)?
- Do they include confidence levels?
- Are any stale or invalidated?

### 12. Folder Depth

- Max 2 levels from a top-level folder: `projects/project/note.md`
- **Flag:** `projects/project/sub/note.md` or deeper

### 13. Volume Check

- **3-8 notes** per project subfolder is healthy
- **1 note** in a subfolder → should it just be in the parent?
- **15+ notes** → should it be split into sub-topics?

### 14. CLAUDE.md / Rules Freshness

- Does `~/.gemini/GEMINI.md` accurately reflect current vault structure?
- Does `~/.gemini/rules/obsidian-notes.md` match actual conventions being followed?
- Are any instructions stale or contradictory?

---

## Report Format

```markdown
## Vault Audit Report — YYYY-MM-DD

| # | Check | Status | Issues |
|---|-------|--------|--------|
| 1 | Sync Health | PASS/FAIL | ... |
| 2 | Folder Placement | PASS/WARN | ... |
| 3 | Subfolder Structure | PASS/FAIL | ... |
| 4 | Naming Conventions | PASS/WARN | ... |
| 5 | Frontmatter | PASS/FAIL | ... |
| 6 | Wikilink Integrity | PASS/WARN | N broken, M pending |
| 7 | Orphaned Notes | PASS/WARN | ... |
| 8 | Content Quality | PASS/WARN | ... |
| 9 | Note Size | PASS/WARN | ... |
| 10 | Stale Content | PASS/WARN | ... |
| 11 | Connection Quality | PASS/WARN | ... |
| 12 | Folder Depth | PASS/FAIL | ... |
| 13 | Volume | PASS/WARN | ... |
| 14 | Rules Freshness | PASS/WARN | ... |

**Score: X / 14**

### Action Items
1. [P0] Critical issue...
2. [P1] Important issue...
3. [P2] Nice-to-have...
```

---

## Scoring Guide

- **12-14**: Healthy vault, well-maintained
- **9-11**: Good shape, minor cleanup needed
- **6-8**: Significant gaps — fix before creating more notes
- **Below 6**: Instruction stack has systemic gaps — escalate to rules/skill updates
