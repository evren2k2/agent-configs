---
name: checkpoint
description: Use when context is getting heavy, at natural breakpoints between subtasks, or when the user asks to checkpoint — writes the agent's full working context, and the full record of what the user asked for, to a recoverable file before compaction
---

# Checkpoint

Dump your working context to a project-specific file in the vault so it survives
compaction or a session boundary. Keeps the last 5.

A checkpoint is not a status report. It is **a briefing for the next agent**, and its
job is to answer four questions in this order:

1. **What did the user actually ask for** — everything, in their words, including the
   corrections they made along the way.
2. **What was being worked on, and how.**
3. **What did the user clarify, decide, or reject** — and what changed as a result.
4. **What must the next agent read to rebuild this context** without losing the intent.

Question 1 is the one that decays fastest and matters most. Progress can be
re-derived from the repo; intent cannot be re-derived from anything.

## When to Use

- User says `/checkpoint`
- You sense context is getting large (long session, many tool calls)
- You're about to pivot to a different task
- Before the user runs `/compact`

## The intent ledger is the point

`### User Intent` is a numbered, chronological, **verbatim** record of everything the
user has specified this project — not a summary of it. It is append-only and it is
**carried forward into every checkpoint**, so the newest checkpoint is always
self-sufficient. `checkpoint.py write` copies the previous ledger in automatically
when your new body doesn't include one; you only ever have to write the *new* items.

What goes in it:

- The original ask, quoted.
- Every clarification, constraint, and correction — in the user's words, not yours.
  *"far too dense"*, *"takes way longer than I expected and longer than you claimed"*
  are the load-bearing kind. Paraphrasing them into "user requested a more compact
  table" destroys the signal.
- Every binding definition the user supplied, marked as binding.
- Every approach the user rejected, and their stated reason.
- Preferences about how the work is done (what to commit, what not to touch, style).
- For each item: what it changed. An instruction whose consequence isn't recorded
  gets re-litigated by the next agent.

Write them as the user said them. Where you must compress, compress your own words
and keep theirs. If you are unsure whether something belongs, it belongs.

## Writing — one call, not four

Pipe the entry body to `checkpoint.py write`. It appends, carries the intent ledger
forward, trims to the last 5, and snapshots the entry to `timeline.md` in one process:

```bash
cat <<'EOF' | python3 ~/.agent-configs/bin/checkpoint.py write --project <project>
## Checkpoint — YYYY-MM-DD HH:MM (one-line topic)

**CWD:** /path/to/working/directory

### User Intent
New items only — the previous ledger is carried forward automatically. Number them
continuing from the last one. Quote the user. Note what each item changed.

### Current Goal
What the ledger adds up to right now. One short paragraph. If the goal has drifted
from the original ask, say so and say why — the drift is itself intent.

### Progress
What's done and how it was done: approach, file paths, function names, test results,
measured numbers. Mark remaining steps [ ] and completed ones [x].

### Key Decisions
Decisions made and WHY. Future you needs the rationale, not just the choice.
Attribute each one — user's call, or yours.

### Ruled Out
Approaches tried or proposed and abandoned, with the reason and who killed them.
This is what stops the next agent from cheerfully re-proposing a dead end.

### Rebuild List
The ordered recipe for re-learning this context. For each item say what it gives you:
- `vault_checkpoint(project=<p>)` — this entry
- vault notes by key, most load-bearing first
- source files to read, with what to look for in each
- commands to run to see current state (test suite, git log, a query)
- what NOT to redo, because it's already settled above

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
changes the retention count; `--no-timeline` skips the timeline snapshot;
`--no-carry` suppresses the automatic intent carry-forward (you almost never want
this — use it only when you are deliberately rewriting the ledger in full).

Keep the section names above verbatim. `bin/checkpoint.py` derives `timeline.md`'s
digest by matching `### Current Goal`, `### Progress`, `### Key Decision` and
`### Open` as literal prefixes; renaming them degrades every future timeline entry
to "(no notable details)".

## Reading — `vault_checkpoint`, and what to do when you can't see it

The callable id is **`mcp__vault-mcp__vault_checkpoint`**. `vault_checkpoint` is the
short name this doc uses; it is not the string your tool list holds. A host that defers
MCP schemas advertises only the prefixed name, so a search for the short one comes back
empty — that is the tool being unfetched, not absent. Fetch its schema
(`ToolSearch("select:mcp__vault-mcp__vault_checkpoint")`), then call it.

    mcp__vault-mcp__vault_checkpoint(project="<project>")  →  latest checkpoint, verbatim

- `n=3` for the last three, `n=0` for all
- `headers=true` for a one-line-per-checkpoint index
- omit `project` for `agent/working-context.md`

**If the tool is genuinely unavailable here, fall back to Bash — never to `Read`.**
Same parser, same output, pre-approved, no MCP required:

```bash
python3 ~/.agent-configs/bin/checkpoint.py read --project <project> -n 1
```

`-n` mirrors the tool's `n`. `--headers` mirrors `headers=true` but applies `-n` first,
so pass `-n 0 --headers` to get the tool's whole-file index rather than one line.

The two things to avoid are `Read`-ing the whole `working-context.md` — it carries a
hand-maintained preamble and up to 5 entries you did not ask for — and delegating the
read to a subagent, whose summary paraphrases away the file paths, flag names and
error strings that are the reason to keep a checkpoint at all. **Never delegate a
checkpoint read.** The intent ledger is verbatim user language; a subagent hands you
its gist, which is exactly the thing the ledger exists to prevent.

## Acting on a checkpoint you just read

Work the Rebuild List before you touch anything. Then re-read `### User Intent` and
treat every item as still binding unless the user has since said otherwise — a
constraint from item 3 is not stale just because item 17 is more recent. If the
current request appears to contradict a ledger item, surface the conflict rather than
silently picking one.

## Where It Goes

**Per-project:** `~/obsidian_notes/projects/<project>/working-context.md`

Determine the project from your CWD or the task at hand. Match against existing
vault project folders — `~/ECE_8893_FPGA/` → `--project ece8893-fpga`. A project
folder and conformant frontmatter are created if absent.

**Fallback:** no project match → omit `--project` (writes `agent/working-context.md`).

## Rules

- **One call.** See above.
- **The ledger is verbatim.** Quote the user. Never compress their words into yours.
- **New intent items every time.** If the user said anything specifying, correcting,
  constraining, or rejecting since the last checkpoint, it goes in the ledger. A
  checkpoint with no new intent items after a conversational session is a checkpoint
  that lost something.
- **Be concrete everywhere else.** File paths, function names, error messages, measured
  numbers — not summaries.
- **A few minutes, not thirty seconds.** The old version of this skill said 30 seconds;
  that produced checkpoints that recorded state and lost intent. The ledger carries
  forward for free, so the recurring cost stays small — spend the time on the new items.
- **The preamble is yours.** Prose above the first `---CHECKPOINT---` (mission, current
  goal, status) is hand-maintained and never touched by trimming. Edit it directly
  when the project's direction changes — that is a direction-class write, so it needs
  user approval per the vault write policy.

## How the pieces fit

`bin/checkpoint.py` owns the `---CHECKPOINT---` format — parsing, trimming, the intent
carry-forward, and the 2-line timeline digest — and is the only implementation of it.
`hooks/update-timeline.sh` calls it so checkpoints still written with the Write/Edit
tools also reach the timeline; `vault_checkpoint` calls it to read.

`working-context.md` is a circular buffer of 5; `timeline.md` is append-only and keeps
a 2-line digest of every checkpoint ever written. **Neither is a durable store of
intent on its own** — the digest is far too lossy, and the buffer drops the 6th-oldest
entry. Intent survives because the ledger is carried forward into the newest entry,
which is the one that is always present. That is why dropping the ledger from a
checkpoint is the one mistake this skill cannot recover from.
