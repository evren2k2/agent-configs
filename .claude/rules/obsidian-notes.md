# Obsidian Vault Rules

## Context Loading — read what is relevant, delegate only breadth
At session start the hook provides the project name. Use `vault_project` to enumerate, then load by tier.

**Tier 1 — read it yourself, whole.** Notes the query names, plus strong `vault_semantic_search` hits. Read directly while the running total stays under ~20k tokens and each note is under ~8 KB. The median vault note is ~1.7k tokens and 62% are under 2k, so this is the normal path, not an exception.

**Tier 2 — read it yourself, in part.** For notes over ~8 KB (`agent/session-log.md`, `projects/rtlgen/decisions/tradeoffs-and-decisions.md`, `personal/deep-research-llm-for-chips/*`), neither read whole nor delegate: `vault_semantic_search` returns passages with line ranges — read just that range.

**Tier 3 — delegate breadth only.** Sweeping a large project (rtlgen is ~224k tokens across 94 notes) or "what else touches X". Require **pointers plus verbatim quotes of load-bearing lines** back — *"note X lines 40-58 has the timing numbers"* — never a paraphrase of technical values. The subagent routes; it does not compress. Prefer `general-purpose` when fidelity matters, since `Explore` reads excerpts by design.

**Never paraphrase a number, flag, path, or error string you could have read verbatim.** Delegating a fidelity read to save ~4k tokens on a 1M-token context is a bad trade.

## Vault Tools (always active — no skill invocation needed)

Six native MCP tools are registered and pre-approved. You MUST use one before `Read`-ing any vault note.

**Their callable ids carry the server prefix — `mcp__vault-mcp__vault_find`, `mcp__vault-mcp__vault_checkpoint`, and so on.** The bare `vault_*` names in this file are shorthand for reading; a host that defers MCP schemas advertises only the prefixed form, so a search for the short name comes back empty. That means unfetched, not missing — fetch the schema (`ToolSearch("select:mcp__vault-mcp__<tool>")`) before concluding a tool is unavailable, and never silently degrade to `Read`/`Grep` because a short name did not resolve.

| Goal | Tool | Key arg |
|------|------|---------|
| Find a note by keyword / name (BM25 lexical) | `vault_find` | `query` |
| Find passages about a concept (semantic) | `vault_semantic_search` | `query` |
| List all notes in a project | `vault_project` | `name` |
| Inspect a note's metadata + links | `vault_show` | `note` |
| See who links to/from a note | `vault_links` | `note` |
| Read a project's last checkpoint(s) verbatim | `vault_checkpoint` | `project` |

**Decision tree:**
- "I need to explore the current project" → `vault_project` first
- "I'm looking for a note by keyword, exact name, or project ID" → `vault_find` → then `vault_show` on the best hit → then `Read`
- "I'm searching by concept/meaning, or want the exact passages discussing X" → `vault_semantic_search` (returns matching paragraphs with file + line range, across all projects; judge hits by the cosine score)
- "I want to see a note's connections" → `vault_links`
- "I need note body content" → identify it with a vault tool first, then `Read`
- "The note is large and I need one part of it" → `vault_semantic_search`, then read the returned line range — this is Tier 2, and it beats both a whole-file read and a subagent summary
- "What was I doing here last session?" → `vault_checkpoint(project=…)`, not a `Read` of `working-context.md`; if the tool is genuinely unavailable, `python3 ~/.agent-configs/bin/checkpoint.py read --project <p>` gives the identical output over Bash
- "I need full-text search inside note bodies" → `Grep` (last resort only)

**Note key format:** lowercase-hyphenated stems. When a stem is ambiguous across projects, qualify it: `test-project/working-context`.

**Workflow — bootstrap project context:**
1. `vault_project(name=<project>)` → compact listing of all notes with status/type
2. **Read the intent set** — the `decisions/` notes (direction: goals, scope calls, and the givens you are not free to change), plus `vocabulary.md` if the listing shows one. Small by design, and what stops you acting plausibly instead of correctly. See *Knowledge Classes* below.
3. `vault_checkpoint(project=<project>)` if you need where the last session left off
4. Then pull from the detail set **only** as the task demands, per the tiers above — Tier 1 for anything under ~8 KB, Tier 2 for the big ones. Never bulk-read `implementation/`. Whole projects are readable at these sizes: only `rtlgen` (~224k tok) and `kahin-v1-internal` (~100k tok) need Tier 3; the other five are ≤39k tok in total.

## Write Policy (classify BEFORE writing)
The class of a note decides who authorizes it:

1. **Direction** — anything that sets project structure, goals, or direction, or records a decision (`type: decision | mission`, roadmaps, working-context goals). Write ONLY on user direction: propose a one-line summary, get approval, then write. Keep in `projects/<name>/decisions/` (or project root for `working-context.md`).
2. **Implementation** — technical findings from doing the work. Autonomous, but strictly need-to-know: weaknesses, non-obvious constraints, things that will clash with future work — never a broad dump of details the code already shows. Keep in `projects/<name>/implementation/` or `logs/`, isolated from direction notes.
3. **Plumbing** — `agent_util` files (session log, timeline, snapshots, checkpoints) and `inbox/` quick capture. Autonomous.

For classes 2-3 the quality bar still applies: write only when a future agent instance would genuinely benefit. Ask: "Would this save significant time or prevent re-discovery in a future session?"

**Write a note when:**
- A non-obvious solution was found (capture the reasoning, not just the fix)
- A meaningful connection between ideas surfaces
- The user explicitly asks to remember something
- Project context was built that would take >5 minutes to reconstruct

**Do NOT write when:** the interaction was trivial, the info is already in the codebase/git history/existing notes, or there's no reusable insight beyond what the commit message says.

## Knowledge Classes (what KIND of note this is)

The write policy above decides who authorizes a note. This decides where it lives and,
more importantly, **whether a new agent reads it up front or only when a question sends it
there**. The goal is that a fresh agent arrives holding the full intent of a project without
wading through detail that does not bear on the task.

Note: "intent set" / "detail set" here is about *what to read first*. It is unrelated to the
Tier 1/2/3 policy at the top of this file, which is about *how to read* a note once chosen.

### Intent set — read these first, every time
Small, stable, and the difference between an agent acting correctly and acting plausibly.

| Class | Answers | Lives in |
|---|---|---|
| **Direction** | what we are doing, what we chose to leave out, and what we are not free to change | `projects/<p>/decisions/` |
| **Vocabulary** | what this project's terms mean *here* | `projects/<p>/vocabulary.md` (optional) |

Direction covers two kinds of statement, and the difference is worth keeping visible even
though both are direction. A **choice** is ours and can be revisited — *"the x/y edge case is
out of scope."* A **given** is imposed from outside and is not ours to trade away — *"we must
not modify openram; a fresh clone has to reproduce"*, *"the scripts run manually on the Pi."*
Getting a choice wrong wastes work. Getting a given wrong breaks something beyond the project,
which is why givens are worth stating flatly rather than leaving implied. When a project
accumulates enough of them to scan on their own, put them in `decisions/constraints.md`.

Direction is almost always the user's to set, so it is a direction-class write: propose, get
approval, then write.

Add `vocabulary.md` only where a project uses terms a competent outsider would misread
(`Vmin`, `rechar`, `design_ev`). Most projects never need one.

### Detail set — retrieve on demand, never bulk-read
| Class | Answers | Lives in |
|---|---|---|
| **Implementation** | how it works; what a test actually validates | `projects/<p>/implementation/` |
| **Findings** | what the data showed, and what was already tried | `implementation/`, or `findings/` when a project is mostly experimental |
| **Operational** | how to run it, and what breaks when you do | `projects/<p>/operational.md` |

**Findings vs Implementation** depends on the kind of project. *Developmental* projects (a
tool, a repo, a flow) produce implementation knowledge: true until the code changes.
*Experimental* projects (a test chip, a study) produce findings — measured results that carry
their provenance (what was tried, on which units, in which session) and that get **superseded**
by later data rather than simply becoming wrong. A findings note that drops its provenance
cannot be superseded safely, because nothing records what it actually measured.

**Dispositions are not knowledge and never go in the vault.** "How to work" rules belong in
the `instincts.py` queue — see `instructions.md`.

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

Exceptions: `README.md` and `agent/` running logs (`session-log.md`, `open-questions.md`, `connections.md`, `pre-compact-snapshot.md`) — use minimal frontmatter with `tags: [agent_util]` instead of full schema.

## Agent Utility Tag
Files that exist solely for agent's internal use (session logs, snapshots, connections) MUST include `tags: [agent_util]` in their frontmatter. This lets the user filter them from Obsidian's Graph View with `-tag:agent_util`. Apply this tag to any new agent-only file in `agent/`.

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
Append to `~/obsidian_notes/agent/session-log.md` at the end of sessions that produced meaningful work. Skip trivial Q&A sessions.

```markdown
## YYYY-MM-DD
**Worked on:** [brief description]
**What worked:** [approaches that succeeded, with evidence]
**What failed:** [approaches that didn't work, and why]
**Key decisions:** [decisions made and rationale]
**Open:** [unresolved items, if any]
**Connections:** [[note1]] ← [[note2]] [brief description of link]
```

## Connections
Append to `~/obsidian_notes/agent/connections.md` only for genuine cross-domain links — not forced.

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
  - **Carve-out for agent/hook files.** `agent_util`-tagged stubs and other hook-generated files are *exempt* from the `project:` requirement — for them, folder location is the grouping, and `vault_project`'s `frontmatter_project_match: false` is informational, not a failure. Genuine project logs (e.g. a project's `timeline.md`) should still carry `project:`.
- **Folder depth**: projects may nest sub-folders as deep as needed — the vault tools handle arbitrary depth — but prefer 1–2 levels (e.g. `projects/my-project/{decisions,implementation,findings,logs,archive}/note.md`) for readability and a legible graph. `projects/my-project/note.md` is also fine.
- **Area promotion**: When a second project needs knowledge from the first, extract the shared concept to `areas/`.

## Archival
- Notes in `inbox/` older than 2 weeks should be filed or deleted.
- Notes referencing completed/abandoned projects should be marked with `status: archived` in frontmatter.
- Don't delete old notes — mark them archived so the history is preserved.

## Content Integrity
Only include information verified from source code, user input, existing notes, or tool output. If unsure, verify first or mark as uncertain — do not interpolate from training data.
