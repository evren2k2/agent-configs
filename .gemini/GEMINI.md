# Gemini User Instructions

## Identity & Notes Vault

My Obsidian vault is Gemini's persistent memory. When Gemini learns something, makes a connection, solves a problem, or builds context across sessions — it lives here.

**Vault:** `~/obsidian_notes/` → `git@github.com:evren2k2/obsidian_notes.git`
**Project Mapping:** Project names from repositories (e.g., `TestOne_Two`) must be mapped to lowercase-hyphenated equivalents (e.g., `testone-two`) for the vault. Always look for project folders in `~/obsidian_notes/projects/<mapped-name>/`.
**Sync:** Cron auto-commits every 5 min. Write files, no manual push needed.

**Folders:**
- `inbox/` — Quick capture, unprocessed thoughts
- `projects/` — Active, time-bound work (grouped by `project:` frontmatter, no hub files)
- `areas/` — Durable domain knowledge (promoted from projects when reused)
- `library/` — Atomic reference notes, papers, tools
- `personal/` — Goals, journal, personal context
- `Gemini/` — Agent meta-layer (session log, connections, open questions)

**Conventions:** `YYYY-MM-DD-topic.md` or `topic.md`. Lowercase-hyphenated filenames only. Use `[[wikilinks]]` to connect ideas.
**Permissions:** Never delete notes without confirming. Prefer appending to overwriting.

## Context Loading (Native MCP Tools)

Vault context is loaded via native MCP tools (`vault_*`) to keep main context clean. The SessionStart hook provides the project name, checkpoint headers, and a compact vault project listing.

**When starting project work or after compaction:**
1. Map the current repository name to its vault-safe equivalent (lowercase, underscores/spaces to hyphens).
2. Use the **`vault_project`** tool to enumerate all notes in the project and see their status/type.
3. Spawn an Explore subagent to read the most relevant 2-3 notes (usually `working-context.md` and high-priority issues) and return a structured summary.
4. The subagent returns only the summary — main context never ingests full vault notes.

**When you need specific vault info:** You MUST use the native vault tools. Never use `read_file` on a vault note until you have first identified it using a vault tool.
- **Search concepts** → `vault_find`
- **Map project** → `vault_project`
- **Inspect metadata/links** → `vault_show`
- **Analyze graph** → `vault_links`

## Available Skills

| Skill | When to use |
|-------|-------------|
| **Native Tools** | Use `vault_find`, `vault_project`, `vault_show`, `vault_links` for all vault navigation. **Do not use shell commands.** |
| `obsidian-notes` | Taking notes, recalling context, building connections, persistent memory |
| `obsidian-audit` | Vault health checks — after creating 3+ notes, weekly, or on request |
| `project-archaeology` | Reverse-engineer an existing codebase into trustworthy vault documentation (runs once per project) |
| `doc-coauthoring` | Co-authoring documentation, proposals, specs |

## Note Quality Gate

Before writing ANY note to the vault, verify:
1. **Future value** — Would a future Gemini instance genuinely benefit? (not just "nice to have")
2. **No duplication** — Is this already in the codebase, git history, or existing notes?
3. **Frontmatter present** — Every note MUST have `date`, `tags`, `type`, and `status` in YAML frontmatter
4. **Wikilinks included** — Link to concepts, not parents. No hub/index files.
5. **Correct folder** — `projects/` for time-bound work, `areas/` for durable knowledge, `library/` for reference
6. **Lowercase-hyphenated filename** — No spaces, CamelCase, or uppercase

## Standard Patterns

**New project (2+ notes):** Create `projects/<project>/` subfolder. Each note gets `project: <name>` in frontmatter. No `_index.md` — use frontmatter queries to find project notes.
**Area promotion:** When a second project needs knowledge from the first, extract it to `areas/`.
**Quick capture:** Drop in `inbox/`, process later.
**Decision record:** Use `type: decision`. Include the decision, alternatives considered, rationale, and who decided.
**Session summary:** Use structured template (see obsidian-notes skill).

## Santa Method Verification

For high-stakes output (pre-tapeout RTL, verification infrastructure, production scripts): invoke `santa-method` skill. Two independent reviewer agents must both PASS before shipping. Max 3 fix iterations, then escalate.

## Instincts

Learned behavioral patterns live in `~/obsidian_notes/Gemini/instincts.yaml`. Each instinct has a `project:` field (`global` or project name). When a project-scoped instinct is validated at confidence >= 0.8 in 2+ projects, promote it to `project: global`.
