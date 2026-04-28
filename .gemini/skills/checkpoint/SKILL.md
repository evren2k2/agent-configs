---
name: checkpoint
description: Use when context is getting heavy, at natural breakpoints between subtasks, or when the user asks to checkpoint — writes the agent's full working context to a recoverable file before compaction
---

# Checkpoint

Dump your current working context to a project-specific file in the vault so it survives compaction or session boundaries. Keeps last 5 checkpoints.

## When to Use

- User says `/checkpoint`
- You sense context is getting large (long session, many tool calls)
- You're about to pivot to a different task
- Before the user runs `/compact`

## Where to Write

**Per-project:** `~/obsidian_notes/projects/<project>/working-context.md`

Determine the project from your CWD or the task at hand. Match against existing vault project folders:
- Working in `~/ECE_8893_FPGA/` → `projects/ece8893-fpga/working-context.md`
- Working in `~/teknofest_chip_design/` → create `projects/teknofest/working-context.md`

**Fallback:** If no project matches, use `~/obsidian_notes/agent/working-context.md`

## Format

Each checkpoint is separated by a `---CHECKPOINT---` marker. Append a new entry, then trim to keep only the last 5.

```markdown
---CHECKPOINT---
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
```

## Rules

- **Append + trim to 5.** Don't overwrite the file — append a new `---CHECKPOINT---` entry, then trim older entries so only the last 5 remain.
- **Be concrete.** File paths, function names, error messages — not summaries.
- **Include the user's words.** Quote the original request so post-compact you doesn't reinterpret it.
- **30 seconds, not 5 minutes.** This is a quick dump, not a polished document.

## Session Tag

After writing the checkpoint, **always** write a one-line session tag file:

```bash
echo "<topic>" > ~/.gemini/.session-topic
```

Where `<topic>` is the parenthetical from your checkpoint header. For example, if your header is `## Checkpoint — 2026-04-14 (SVA protocol checkers)`, write:

```bash
echo "SVA protocol checkers" > ~/.gemini/.session-topic
```

This tag tells the pre-compact hook which checkpoint to recover if compaction fires. Without it, the hook can only list checkpoint headers and the post-compact agent must figure out which is relevant via a subagent.

## Trimming

After appending, read the file back, split on `---CHECKPOINT---`, keep the last 5 entries, and rewrite the file.
