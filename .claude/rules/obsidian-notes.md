# Obsidian Vault Rules

## Context Loading
At session start, the hook provides the project name, checkpoint headers, and a compact vault project listing (note names + type/status, no bodies). For note **content**, spawn an Explore subagent to read `working-context.md` and 1-2 related notes. The subagent returns a concise summary (~25 lines) to main context. Do NOT read full vault notes directly in main context — always delegate to subagent.

## Vault Search
For vault queries, prefer the `vault` CLI (see the `vault-cli` skill) — it returns compact metadata + link summaries from a cached graph index, letting you pick 2-3 notes to Read instead of grepping dozens of files. Default routing:
- Concept search → `vault find "<query>"`
- Project map → `vault project <name>`
- Frontmatter filter → `vault query --tag X --status Y --type Z`
- Graph navigation → `vault links <note>`, `vault neighbors <note> --depth 2`
- Single-note metadata → `vault show <note>`

Fall back to `Grep` only when you need full-text patterns inside note bodies. Spawn a subagent for queries that will produce noisy results — the subagent returns a short summary while the index stays out of main context. Direct Read in main context is only appropriate for a single known-path file.

## When to Write Notes (Quality Bar)
Write to the vault only when a future Claude instance would genuinely benefit. Ask: "Would this save significant time or prevent re-discovery in a future session?"

**Write a note when:**
- A non-obvious solution was found (capture the reasoning, not just the fix)
- A meaningful connection between ideas surfaces
- The user explicitly asks to remember something
- Project context was built that would take >5 minutes to reconstruct
- A decision was made with rationale worth preserving

**Do NOT write a note when:**
- The interaction was trivial (quick question, simple file edit)
- The information is already in the codebase, git history, or existing notes
- The note would just restate what the commit message says
- It's a one-off debugging session with no reusable insight

## Frontmatter (REQUIRED)
**Every note MUST have YAML frontmatter.** This is non-negotiable. Notes without frontmatter fail audit.

```yaml
---
date: YYYY-MM-DD
tags: [domain, subdomain]
type: concept          # concept | decision | log | mission
status: active         # backlog | active | completed | archived
project: my-project    # optional, groups notes without hub files
---
```

Exceptions: `README.md`, `claude/session-log.md`, `claude/open-questions.md`, `claude/connections.md`, `claude/pre-compact-snapshot.md` (running logs — use minimal frontmatter with `tags: [claude_util]` instead of full schema).

## Claude Utility Tag
Files that exist solely for Claude's internal use (session logs, snapshots, connections) MUST include `tags: [claude_util]` in their frontmatter. This lets the user filter them from Obsidian's Graph View with `-tag:claude_util`. Apply this tag to any new Claude-only file in `claude/`.

## Filename Conventions (REQUIRED)
- **Lowercase-hyphenated only**: `lab1-loop-optimization.md`, not `Lab1_LoopOptimization.md`
- **Time-anchored**: `YYYY-MM-DD-topic.md` for dated notes
- **Evergreen**: `topic.md` or `topic-subtopic.md` for reference notes
- **No spaces, CamelCase, or uppercase** (except `README.md`)

## Note Size Limits
- **Target**: 200-400 lines per note
- **Maximum**: 800 lines — split if larger
- **Minimum useful**: 10 lines — if shorter, consider appending to an existing note instead

## Wikilinks (REQUIRED)
Every note MUST contain at least one `[[wikilink]]` to a related note. Orphaned notes are invisible to the graph and to future retrieval.

**Link to concepts, not parents.** No `_index.md` hub files. Cross-project links are the highest-value connections. A note should link to 1-3 related notes max — forced links degrade signal.

## Session Log
Append to `~/obsidian_notes/claude/session-log.md` only at the end of sessions that produced meaningful work. Most sessions should NOT get a log entry. If the session was just a quick Q&A, skip it.

Use the structured template:
```markdown
## YYYY-MM-DD
**Worked on:** [brief description]
**What worked:** [approaches that succeeded, with evidence]
**What failed:** [approaches that didn't work, and why — saves future re-discovery]
**Key decisions:** [decisions made and rationale]
**Open:** [unresolved items, if any]
**Connections:** [[note1]] ← [[note2]] [brief description of link]
```

## Connections
Add to `~/obsidian_notes/claude/connections.md` only when a genuine cross-domain link is discovered — not forced. Include confidence:

```markdown
## YYYY-MM-DD
**Connection:** [[note1]] ↔ [[note2]]
**Insight:** [the actual cross-domain link]
**Confidence:** high/medium/low
**Evidence:** [what supports this connection]
```

## Folder Organization
- When unsure where to put a note, use `inbox/`.
- When a project has 2+ notes, create a subfolder (e.g., `projects/teknofest/`).
- Never use filename prefixes as a substitute for folders.
- **No `_index.md` hub files.** Project grouping uses `project:` frontmatter. Find notes with the Grep tool: `pattern: "project: <name>"`, `path: ~/obsidian_notes/`, `glob: "*.md"`.
- **Max depth**: 2 levels from a top-level folder. `projects/my-project/note.md` is fine. Never deeper.
- **Area promotion**: When a second project needs knowledge from the first, extract the shared concept to `areas/`.

## Archival
- Notes in `inbox/` older than 2 weeks should be filed or deleted.
- Notes referencing completed/abandoned projects should be marked with `status: archived` in frontmatter.
- Don't delete old notes — mark them archived so the history is preserved.

## Content Integrity
Only include information verified from source code, user input, existing notes, or tool output. Do not interpolate from training data — if unsure whether something is true for this specific project, verify it first or note the uncertainty explicitly.
