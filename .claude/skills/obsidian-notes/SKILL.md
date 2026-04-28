---
name: obsidian-notes
description: Use when taking notes, recalling context, building connections, or treating the Obsidian vault as Claude's persistent memory across sessions
---

# Obsidian Notes — Claude's Persistent Memory

## When to Activate
- User asks to remember, note, or document something
- A non-obvious solution is found worth preserving
- Cross-domain connections surface
- Starting work on a topic that may have prior vault context
- End of a meaningful work session (session log)
- Before `/compact` (pre-compact checkpoint)
- User mentions the vault, notes, or Obsidian

---

## Philosophy

The vault is Claude's **external brain** — persistent, cross-session memory where thinking accumulates. Each session should leave the vault richer than it found it. Obsidian is the overflow for insight that would otherwise vanish at session end.

---

## Vault Structure

```
~/obsidian_notes/
├── inbox/       Quick capture. Process later. Default drop zone.
├── projects/    Time-bound work (grouped by project: frontmatter, no hub files).
│   └── <project>/   ← subfolder per project when 2+ notes exist
├── areas/       Durable domain knowledge (promoted from projects/ when reused).
├── library/     Atomic reference notes, papers, tools.
├── personal/    Goals, journal, personal context.
└── agent/       Agent's own synthesis, connections, open questions.
    ├── session-log.md      Running log (append-only)
    ├── open-questions.md   Unresolved questions (append-only)
    ├── connections.md      Cross-domain links (append-only)
    └── instincts.yaml      Learned behavioral patterns with confidence
```

### Subfolder Rules
- **1 note** → place directly in parent folder (`projects/some-topic.md`)
- **2+ notes** → create subfolder (`projects/project/architecture.md`)
- **No `_index.md` hub files.** Project grouping uses `project:` frontmatter. Agents find notes via `grep -r "project: <name>"`.
- **Do NOT create generic hub filenames** (`Home.md`, `_index.md`, `index.md`). Use descriptive project-prefixed names if a hub is needed (e.g., `ece8893-fpga-overview.md`).
- **Never** prefix-based flat naming (`projects/proj-arch.md`, `projects/proj-bugs.md`)
- **Max depth**: 2 levels (`projects/project/note.md`, never deeper)
- **Area promotion**: When a second project needs knowledge from the first, extract the shared concept to `areas/`.

---

## Quality Gate (MANDATORY before writing any note)

Before creating or modifying a vault note, check ALL of these:

- [ ] **Future value**: Would a future Claude instance genuinely benefit?
- [ ] **No duplication**: Not already in codebase, git history, or existing notes?
- [ ] **Frontmatter**: Has `date`, `tags`, `type`, and `status` in YAML frontmatter?
- [ ] **Wikilinks**: Contains at least one `[[wikilink]]` to related note?
- [ ] **Correct folder**: `projects/` for time-bound work, `areas/` for durable knowledge, `library/` for reference?
- [ ] **Filename**: Lowercase-hyphenated, no spaces/CamelCase?
- [ ] **Size**: Under 800 lines? (Split if larger, target 200-400)
- [ ] **Content**: Captures reasoning/tradeoffs, not just facts?

---

## Note Format

### Required Frontmatter

```markdown
---
date: 2026-04-01
tags: [ece, synthesis]
type: concept          # concept | decision | log | mission
status: active         # backlog | active | completed | archived
project: my-project    # optional, groups notes without hub files
---
```

Every note except running logs (`session-log.md`, `open-questions.md`, `connections.md`) MUST have frontmatter.

### Naming
- `YYYY-MM-DD-topic.md` — time-anchored notes
- `topic.md` or `topic-subtopic.md` — evergreen reference
- Lowercase-hyphenated only. No spaces, CamelCase, or uppercase.

### Content
- Use `[[wikilinks]]` to connect related notes
- Use headers to structure longer notes
- Prefer atomic, linkable notes over monolithic documents
- Capture reasoning and tradeoffs, not just conclusions

### Appending vs Overwriting
- **Prefer appending** — context accumulates over time
- Use `## YYYY-MM-DD` headers for timestamped additions
- Only overwrite when restructuring with user awareness

---

## Context Modes

Adapt behavior based on what the user needs:

### Capture Mode (default)
Quick notes, minimal processing, inbox-first. Use when the user shares something worth remembering but isn't doing deep work.

### Synthesis Mode
Deep reading of existing notes, cross-note connection building, gap identification. Activate when the user asks to "review", "connect", or "synthesize" vault content.

### Review Mode
Vault audit, quality checks, cleanup. Load the `obsidian-audit` skill instead.

---

## Session Log Pattern

At the end of meaningful sessions, append to `agent/session-log.md`:

```markdown
## YYYY-MM-DD
**Worked on:** [brief description]
**What worked:** [approaches that succeeded, with evidence]
**What failed:** [approaches that didn't work, and why]
**Key decisions:** [decisions made and rationale]
**Open:** [unresolved items]
**Connections:** [[note1]] ← [[note2]] [brief link description]
```

**Skip the log** if the session was trivial (quick Q&A, simple edit).

---

## Connection-Building

When writing a note, always ask: **"What other notes does this connect to?"**

### connections.md Format (with confidence)

```markdown
## YYYY-MM-DD
**Connection:** [[note1]] ↔ [[note2]]
**Insight:** [the cross-domain link — what makes this non-obvious]
**Confidence:** high/medium/low
**Evidence:** [what supports this]
```

Only add genuine cross-domain connections. Forced connections degrade signal.

---

## Instincts (Learned Patterns)

`agent/instincts.yaml` tracks behavioral patterns learned across sessions. Each instinct has a confidence score (0.0-1.0) that evolves:
- **Increases** when the pattern is validated in practice
- **Decreases** when contradicted
- **Pruned** below 0.3 confidence

When you notice a reusable pattern, add it. When an instinct proves wrong, lower its confidence or remove it.

---

## Pre-Compact Checkpoint

Before any `/compact`, save context that would be lost:

1. Ensure any in-progress vault notes are written and saved.
2. If working on a project, note the current task state, key file paths, and next steps in the session log or as a quick `inbox/` note.
3. Use a descriptive compact summary: `/compact Focus on implementing X next`

**What survives compaction:** CLAUDE.md, tasks, memory files, git state, disk files.
**What's lost:** Intermediate reasoning, file contents read, conversation history.

---

## Retrieval Pattern

When searching the vault for context, use the **Grep tool** (not bash grep) with iterative retrieval:

1. **First pass**: Search by frontmatter — Grep tool with `pattern: "project: <name>"`, `path: ~/obsidian_notes/`, `glob: "*.md"`. Or keyword search with `pattern: "keyword"`.
2. **Evaluate**: Are results sufficient? Check wikilinks in found notes for related content.
3. **Follow links**: Read linked notes for deeper context.
4. **Max 3 cycles** — if not found by then, the vault doesn't have it.

Also check:
- `agent/session-log.md` — what was done before
- `agent/open-questions.md` — unresolved items

---

## Sync

Cron handles everything. After writing files:
- No manual push needed — cron runs every 5 min
- Force immediate sync: `~/obsidian_notes/scripts/server-sync.sh`
- Check sync log: `tail ~/obsidian_notes/scripts/sync.log`
