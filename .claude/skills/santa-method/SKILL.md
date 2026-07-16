---
name: santa-method
description: Use before shipping high-stakes output (pre-tapeout RTL, verification infra, production scripts) that needs independent adversarial review. Requires reviewer backends configured in santa-method.json — if none are configured, do not use.
---

# Santa Method

Two independent reviewers, each with a different angle, must both PASS before output ships. Catches hallucinations, missing edge cases, tautological tests, and single-reviewer blind spots.

## Step 0 — read the config (required)

Read `~/.agent-configs/santa-method.json` (gitignored, machine-local; copied from the tracked `santa-method.json.example`). It defines the reviewer backends:

```json
{ "reviewers": [
  { "name": "codex", "command": "... {focus} ... {files} ..." }
] }
```

If `reviewers` is empty or the file is missing, **stop**: tell the user santa-method has no backend configured — they can `cp santa-method.json.example santa-method.json` and fill in a reviewer. Do not invent a reviewer.

## When to use

- Pre-tapeout RTL (timing/synthesis-critical), verification infra (testbench, SVA, cocotb), production scripts, or any code that ships without human review.
- Skip for: drafts, exploration, quick fixes, docs, Makefiles, config, and anything with deterministic verification (use build/lint/test instead).

## Workflow

1. Finish the deliverable. Untracked files are fine if the command uses a working-tree scope.
2. Pick two **divergent** review angles:
   - **A — defects:** bugs, tautological checks, race conditions, protocol violations.
   - **B — design:** tradeoffs, assumptions, failure modes, coverage gaps.
   With ≥2 reviewers in config, use two different ones; with one, run it twice — once per angle.
3. Run both **in parallel** — two `Bash` calls in one message, each `run_in_background: true`. Substitute `{focus}` (the angle) and `{files}` (specific paths) into each `command`, and redirect each reviewer's full output to its own log file (append `> /tmp/santa-<name>-<angle>.log 2>&1`) so the verdict is captured whole, not scraped from scrollback.
4. **Wait for each reviewer to fully exit, then read its log file end-to-end.** Do not judge from a partial/incremental read — the verdict is the LAST line (`VERDICT: PASS` / `VERDICT: FAIL`). If a log ends without a `VERDICT:` line, the run was **truncated, not a verdict** (see *Truncated / incomplete runs*): re-run that reviewer, don't infer PASS/FAIL.
5. **Gate:** both PASS → ship. Either FAIL → fix every issue, then re-run fresh (no shared context).
6. Max 3 iterations, then escalate to the user.

## Signals

- Both reviewers converging on one finding = high confidence.
- Reviewers do static analysis only — they can't run sims or builds. Run those yourself first.
- Severity reads hot; a flagged "high" may be a medium.

## Truncated / incomplete runs

A reviewer whose output ends **without** a final `VERDICT:` line did not finish — treat it as a failed run to retry, never as a silent PASS. Two causes, both fixable:

- **The reviewer self-truncated on its own print timeout.** `agy -p` defaults to `--print-timeout 5m0s`; a thorough adversarial review routinely exceeds it, so agy prints a partial response and exits before the verdict. Fix: raise it in the backend command — `agy --print-timeout 20m -p "…"`. (`claude -p` has no such cap.)
- **The output was read before the process finished.** Reading background scrollback incrementally can catch a partial tail. Fix: redirect each reviewer to a log file (Workflow step 3), wait for full exit, then read the whole file (Workflow step 4).

If a reviewer still truncates after raising its timeout, narrow `{files}` (fewer paths per run) or split the review.

## RTL / verification checklist

Port widths and connectivity · no implicit nets · AXI valid/ready handshakes · reset values on all flops (no X-prop) · non-trivial SVA covering every handshake · error-path coverage that distinguishes PASS from a pre-silicon bug · CDC synchronizers.

## Configuring a backend

Add an entry to `reviewers` in the gitignored, machine-local `santa-method.json` (copy it from the tracked `santa-method.json.example`); to share a backend every repo user has, add it to `santa-method.json.example` instead. Subscription CLIs work well (`agy --print-timeout 20m -p "..."`, `claude -p --model <model-you-have> "..."` — end the prompt with "End with exactly one line: VERDICT: PASS or VERDICT: FAIL"). For `agy`, `--print-timeout` matters: its 5-minute default truncates long reviews before the verdict (see *Truncated / incomplete runs*). Example (codex via the openai-codex plugin):

```json
{ "reviewers": [
  { "name": "codex",
    "command": "CODEX=\"$(find ~/.claude/plugins/cache/openai-codex -name codex-companion.mjs -print -quit)\" && node \"$CODEX\" adversarial-review --wait --scope working-tree --reasoning-effort=high \"{focus} in {files}\"" }
] }
```

Notes: keep `{focus}` in double quotes (special chars break bash). Use a channel that accepts free-text focus — codex's `adversarial-review` does; its built-in `review` and `codex-rescue` channels do not.
