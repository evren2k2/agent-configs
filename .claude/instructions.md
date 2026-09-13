# Claude User Instructions

## Identity & Notes Vault

My Obsidian vault is Claude's persistent memory. When Claude learns something, makes a connection, solves a problem, or builds context across sessions — it lives here.

**Vault:** `~/obsidian_notes/` → `git@github.com:evren2k2/obsidian_notes.git`
**Project Mapping:** Project names from repositories (e.g., `TestOne_Two`) must be mapped to lowercase-hyphenated equivalents (e.g., `testone-two`) for the vault. Always look for project folders in `~/obsidian_notes/projects/<mapped-name>/`.
**Sync:** Cron auto-commits every 5 min. Write files, no manual push needed.

**Folders:**
- `inbox/` — Quick capture, unprocessed thoughts
- `projects/` — Active, time-bound work (grouped by `project:` frontmatter, no hub files)
- `areas/` — Durable domain knowledge (promoted from projects when reused)
- `library/` — Atomic reference notes, papers, tools
- `personal/` — Goals, journal, personal context
- `agent/` — Agent meta-layer (session log, connections, open questions)

**Conventions:** `YYYY-MM-DD-topic.md` or `topic.md`. Lowercase-hyphenated filenames only. Use `[[wikilinks]]` to connect ideas.
**Permissions:** Never delete notes without confirming. Prefer appending to overwriting.

## Context Loading (Native MCP Tools)

The SessionStart hook provides the project name. Use vault MCP tools (`vault_*`) to find what matters before reading anything.

**Session start workflow:**
1. Map repo name to vault-safe equivalent (lowercase, underscores/spaces → hyphens).
2. `vault_project(name=<project>)` → enumerate notes with status/type.
3. Read the notes that actually bear on the task **yourself** — the median note is ~1.7k tokens. For notes over ~8 KB, use `vault_semantic_search` and read the returned line range. Delegate to a subagent only for breadth, and require verbatim quotes back, never a paraphrase of numbers, paths or error strings.

See `rules/obsidian-notes.md` for the three tiers and the tool decision tree.

## Note Quality Gate

Before writing ANY note to the vault, verify:
0. **Write class** — Direction/decision content (project structure, goals, decisions) requires explicit user approval before writing. Implementation notes are autonomous but need-to-know only (weaknesses, future clashes — not detail dumps). Plumbing (`agent_util`, `inbox/`) is autonomous.
1. **Future value** — Would a future Claude instance genuinely benefit? (not just "nice to have")
2. **No duplication** — Is this already in the codebase, git history, or existing notes?
3. **Frontmatter present** — Every note MUST have `date`, `tags`, `type`, and `status` in YAML frontmatter
4. **Wikilinks included** — Link to concepts, not parents. No hub/index files.
5. **Correct folder** — `projects/` for time-bound work, `areas/` for durable knowledge, `library/` for reference
6. **Lowercase-hyphenated filename** — No spaces, CamelCase, or uppercase

## Standard Patterns

**New project (2+ notes):** Create `projects/<project>/` subfolder. Each note gets `project: <name>` in frontmatter. No `_index.md` — use frontmatter queries to find project notes.
**Area promotion:** When a second project needs knowledge from the first, extract it to `areas/`.
**Quick capture:** Drop in `inbox/`, process later.
**Decision record:** Use `type: decision`. Include the decision, alternatives considered, rationale, and who decided. Requires user-approved direction before writing.
**Session summary:** Use structured template (see obsidian-notes skill).

## Git Commits

- **No AI co-author trailer.** Do *not* append `Co-Authored-By: Claude ...` or any "Generated with Claude Code" line to commits. This overrides the harness default, which otherwise adds one.
- **Match the repo's convention.** Read `git log` first and follow the existing commit style (subject format, conventional-type prefix, body/no-body, tense). Infer it per-repo — don't impose a default.

## Knowledge vs Dispositions

Two different things get learned in a session. They are stored differently because they are *triggered* differently.

**Knowledge** — what is true about a system. *"Cosim reports 0 mismatches when an InPort is left undriven."* *"The signoff metric disagrees with the violation report because it counts only the worst path."* A specific situation brings it back, so it can sit in a **vault note** and be retrieved on demand. That is where it goes, per the write policy in `rules/obsidian-notes.md` — never in instincts.

**Dispositions** — how to work. *"Never state an estimate you have not measured."* *"Verify a claim against the source before asserting it."* There is no situation to search on: the trigger is *any turn*. A disposition therefore does nothing unless it is already in context, which is why they are few, short, and capped.

These live in `~/obsidian_notes/agent/instincts.yaml`, a capped **staging queue** managed by `bin/instincts.py`:

```bash
python3 ~/.agent-configs/bin/instincts.py propose --disposition '<rule>' --origin '<verbatim user correction>' --project <p>
python3 ~/.agent-configs/bin/instincts.py list
```

The source of a disposition is a **user correction** — a moment your scope, your rigor, an assumption, or an unmeasured claim had to be fixed — not a retrospective on what the task taught. Asking "what did I learn?" reliably returns knowledge; asking "where was I corrected?" is what surfaces a disposition.

The test: if the rule stops being true when you switch projects, it is knowledge. Write the note instead.

Queued dispositions do nothing until promoted into `rules/learned-dispositions.md`, which every session loads. Promotion requires the disposition to have re-triggered in a later session *and* the user's approval — it is a direction-class write. Never edit that rules file by hand; use `instincts.py promote --apply`.

Propose a disposition even when you suspect it is already queued: an identical rule proposed in a later session is counted as the re-trigger that earns promotion (a same-day repeat is not), so `propose` alone closes the loop.
# graphify
- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.
