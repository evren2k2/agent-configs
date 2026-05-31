---
name: santa-method
description: Use before shipping high-stakes output (pre-tapeout RTL, verification infra, production scripts) that needs independent adversarial review. Requires reviewer backends configured in santa-method.json — if none are configured, do not use.
---

# Santa Method

Two independent reviewers, each with a different angle, must both PASS before output ships. Catches hallucinations, missing edge cases, tautological tests, and single-reviewer blind spots.

## Step 0 — read the config (required)

Read `~/.agent-configs/santa-method.json`. It defines the reviewer backends:

```json
{ "reviewers": [
  { "name": "codex", "command": "... {focus} ... {files} ..." }
] }
```

If `reviewers` is empty or the file is missing, **stop**: tell the user santa-method has no backend configured and point them to that file. Do not invent a reviewer.

## When to use

- Pre-tapeout RTL (timing/synthesis-critical), verification infra (testbench, SVA, cocotb), production scripts, or any code that ships without human review.
- Skip for: drafts, exploration, quick fixes, docs, Makefiles, config, and anything with deterministic verification (use build/lint/test instead).

## Workflow

1. Finish the deliverable. Untracked files are fine if the command uses a working-tree scope.
2. Pick two **divergent** review angles:
   - **A — defects:** bugs, tautological checks, race conditions, protocol violations.
   - **B — design:** tradeoffs, assumptions, failure modes, coverage gaps.
   With ≥2 reviewers in config, use two different ones; with one, run it twice — once per angle.
3. Run both **in parallel** — two `Bash` calls in one message, each `run_in_background: true`. Substitute `{focus}` (the angle) and `{files}` (specific paths) into each `command`.
4. **Gate:** both PASS → ship. Either FAIL → fix every issue, then re-run fresh (no shared context).
5. Max 3 iterations, then escalate to the user.

## Signals

- Both reviewers converging on one finding = high confidence.
- Reviewers do static analysis only — they can't run sims or builds. Run those yourself first.
- Severity reads hot; a flagged "high" may be a medium.

## RTL / verification checklist

Port widths and connectivity · no implicit nets · AXI valid/ready handshakes · reset values on all flops (no X-prop) · non-trivial SVA covering every handshake · error-path coverage that distinguishes PASS from a pre-silicon bug · CDC synchronizers.

## Configuring a backend

Add an entry to `reviewers` in `santa-method.json`. Example (codex via the openai-codex plugin):

```json
{ "reviewers": [
  { "name": "codex",
    "command": "CODEX=\"$(find ~/.claude/plugins/cache/openai-codex -name codex-companion.mjs -print -quit)\" && node \"$CODEX\" adversarial-review --wait --scope working-tree --reasoning-effort=high \"{focus} in {files}\"" }
] }
```

Notes: keep `{focus}` in double quotes (special chars break bash). Use a channel that accepts free-text focus — codex's `adversarial-review` does; its built-in `review` and `codex-rescue` channels do not.
