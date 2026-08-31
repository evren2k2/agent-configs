---
name: checkpoint
description: Use when context is getting heavy, at natural breakpoints between subtasks, or when the user asks to checkpoint — writes the agent's full working context to a recoverable file before compaction
---

# Checkpoint

Dump your current working context to a project-specific file in the vault so it survives compaction or session boundaries. Keeps the last 5.

## When to Use

- User says `/checkpoint`
- You sense context is getting large (long session, many tool calls)
- You're about to pivot to a different task
- Before the user runs `/compact`

## Writing — one call, not four

Pipe the entry body to `checkpoint.py write`. It appends, trims to the last 5, and
snapshots the entry to `timeline.md` in a single process:

```bash
cat <<'EOF' | python3 ~/.agent-configs/bin/checkpoint.py write --project <project>
## Checkpoint — YYYY-MM-DD HH:MM

**CWD:** /path/to/working/directory

### Current Goal
What you are trying to accomplish — quote the user's original request.

### Plan & Approach
The strategy you're following. Numbered steps if multi-step.
Mark which steps are [x] done vs [ ] remaining.

### Progress
What's been completed. Be specific — file paths, function names, test results.

### Key Decisions
Decisions made and WHY. Future you needs the rationale, not just the choice.

### Active Files
Files you're reading, editing, or monitoring. List paths.

### Open / Blocked
Anything unresolved, waiting on the user, or stuck. "None" if clear.
EOF
```

**Do not** read the file first, append with Edit, then re-read and rewrite to trim.
That is four full-context round trips for work that needs no model decision between
the steps: the body is already written, "keep the last 5" is a fixed rule, and the
timeline digest is derived from the body. The file work costs microseconds either
way — the turns are the entire cost. One call.

Omit `--project` to write the unscoped `agent/working-context.md`. `--keep N`
changes the retention count; `--no-timeline` skips the timeline snapshot.

## Reading — use the MCP tool

`vault_checkpoint(project="<project>")` returns the latest checkpoint **verbatim**.

- `n=3` for the last three, `n=0` for all
- `headers=true` for a one-line-per-checkpoint index
- omit `project` for `agent/working-context.md`

Do **not** `Read` the whole `working-context.md` for this, and do **not** delegate
the read to a subagent. The tool already returns only the entries, and a subagent
summary would paraphrase away the file paths, flag names and error strings that are
the reason to keep a checkpoint at all.

## Where It Goes

**Per-project:** `~/obsidian_notes/projects/<project>/working-context.md`

Determine the project from your CWD or the task at hand. Match against existing
vault project folders — `~/ECE_8893_FPGA/` → `--project ece8893-fpga`. A project
folder and conformant frontmatter are created if absent.

**Fallback:** no project match → omit `--project` (writes `agent/working-context.md`).

## Rules

- **One call.** See above.
- **Be concrete.** File paths, function names, error messages — not summaries.
- **Include the user's words.** Quote the original request so post-compact you doesn't reinterpret it.
- **30 seconds, not 5 minutes.** This is a quick dump, not a polished document.
- **The preamble is yours.** Prose above the first `---CHECKPOINT---` (mission, current
  goal, status) is hand-maintained and never touched by trimming. Edit it directly
  when the project's direction changes — that is a direction-class write, so it needs
  user approval per the vault write policy.

## How the pieces fit

`bin/checkpoint.py` owns the `---CHECKPOINT---` format — parsing, trimming, and the
2-line timeline digest — and is the only implementation of it. `hooks/update-timeline.sh`
calls it so checkpoints still written with the Write/Edit tools also reach the
timeline; `vault_checkpoint` calls it to read. `working-context.md` is a circular
buffer of 5; `timeline.md` is append-only and keeps every checkpoint ever written.
