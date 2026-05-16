---
name: vault-cli
description: Use the `vault` CLI to navigate the Obsidian vault by graph (wikilinks/backlinks), frontmatter (tag/status/type/project), or lexical search before reading any note. Cuts the cost of finding the right 2-3 notes among hundreds.
---

# vault CLI — Graph-Aware Vault Navigation

## When to use

Reach for `vault` (not Read/Grep) whenever you want to:

- **Find a note about a concept** → `vault find "<query>"` (BM25-ish ranker; the lightweight replacement for the never-implemented `mgrep`)
- **Inspect a single note's metadata + links without reading it** → `vault show <note>`
- **See who links to / from a note** → `vault links <note>`
- **Map a project** → `vault project <name>` (frontmatter + folder fallback)
- **Find all notes with given tag/status/type** → `vault query --tag X --status Y --type Z`
- **Expand a neighborhood** → `vault neighbors <note> --depth 2`
- **Find the connection between two ideas** → `vault path <a> <b>`
- **Spot vault-hygiene issues** → `vault orphans`, `vault stats`

**Rule of thumb**: shape the search with `vault` first; use Read only on the 1–3 candidates the CLI surfaces.

## Decision tree

| Question | Command |
|---|---|
| "I know the note name and want its content" | `Read` directly |
| "I know the note name, want metadata only" | `vault show <note>` |
| "I'm looking for a concept" | `vault find "..."` |
| "I want all notes in a project" | `vault project <name>` |
| "I want all active concept notes" | `vault query --status active --type concept` |
| "What links to / from this note?" | `vault links <note>` |
| "What's adjacent to this note in the graph?" | `vault neighbors <note> --depth 2` |
| "How are these two notes related?" | `vault path <a> <b>` |
| "What's the vault state?" | `vault stats` |

## Key conventions

- **Note keys** are lowercase-hyphenated stems: `minimax-algorithm`, not `Minimax Algorithm.md`.
- **Qualified keys**: when two notes share a stem (e.g. each project has its own `working-context.md`), the CLI uses `<folder>/<stem>` — e.g. `brawlstars-ranked-app/working-context`. Pass either the bare stem (CLI will disambiguate or error) or the qualified form.
- **`--json`** on every subcommand returns structured output — preferred when chaining via shell.
- **Index** is cached at `~/.cache/agent-vault/<vault-hash>/index.json`. It rebuilds incrementally on file mtime change, so writes by the agent are picked up automatically on the next call. Use `vault index --rebuild` only to force a full reparse after suspected drift.

## Patterns

### Bootstrap project context
```
vault project <name> --json | <pick 2-3 entries by status/title> → Read those files
```
Cheaper than reading all 13 notes in a project folder.

### Topic exploration
```
vault find "<topic>" --limit 5      # discover candidates
vault links <best-hit>              # see how it's connected
Read <best-hit>                     # only now read content
```

### Cross-project connection
```
vault path <note-in-project-a> <note-in-project-b>
# If a path exists, the projects are conceptually linked. The path notes
# are likely your bridge concepts (good candidates for promotion to areas/).
```

### Audit / hygiene
```
vault orphans                       # notes nothing points to
vault query --status active --project <name>   # what's still open in a project
vault stats                         # counts by type/status/tag
```

## What `vault` does NOT do

- Doesn't read note bodies (`first_paragraph` is the most you get). Use Read for content.
- Doesn't do semantic / embedding search. The ranker is lexical (BM25-ish over filename + title + tags + frontmatter + first paragraph). It works well because vault filenames and tags are descriptive — but if a note's terminology differs from yours, fall back to `vault find <synonym>` or `Grep` directly.
- Doesn't write to the vault. It's a query tool.

## Installation note

The CLI lives at `agent-configs/bin/vault` (Python 3 stdlib, no install). After running `setup.sh` / `setup.ps1`, `vault` is on PATH. On Windows the `vault.cmd` shim invokes it via the `py` launcher.
