#!/bin/bash
# PostToolUse hook on the SHELL tool (Claude: Bash; agy: run_command, via hooks/agy-adapter.py).
#
# WHY THIS EXISTS
#   The intent ledger is carried forward by `checkpoint.py write`. Nothing forces an
#   agent to call it: on 2026-09-20/21 three checkpoints were appended with
#   `cat >> working-context.md <<EOF` and one-off python patches, so carry_intent()
#   never ran, the ledger became a pointer to "items 1–48 in the earlier checkpoint",
#   and the next session — reading only the newest entry — lost every binding item.
#   The Write|Edit hooks never saw those writes either: a shell heredoc is not a
#   Write. This hook closes that path: if the command mentioned a working-context.md,
#   run `checkpoint.py repair` on it. Repair is idempotent and silent on a sound file.
#
# CONTRACT
#   stdin: hook JSON; we only read tool_input.command. Exit 0 always — a repair
#   must never block the agent. Fixes are surfaced as additionalContext so the model
#   learns the file was normalised and that `checkpoint.py write` was the intended path.

INPUT=$(cat)

PROJECTS=$(echo "$INPUT" | python3 -c '
import sys, json, re
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cmd = str((d.get("tool_input") or d).get("command", ""))
if "working-context.md" not in cmd:
    sys.exit(0)
seen = []
for m in re.finditer(r"projects/([A-Za-z0-9._-]+)/working-context\.md", cmd):
    if m.group(1) not in seen:
        seen.append(m.group(1))
if re.search(r"agent/working-context\.md", cmd):
    seen.append("")                      # the unscoped agent-level file
print("\n".join(seen))
' 2>/dev/null)

[ -n "$PROJECTS" ] || exit 0

NOTES=""
while IFS= read -r P; do
    if [ -n "$P" ]; then
        OUT=$(python3 "$HOME/.agent-configs/bin/checkpoint.py" repair --project "$P" 2>/dev/null)
    else
        OUT=$(python3 "$HOME/.agent-configs/bin/checkpoint.py" repair 2>/dev/null)
    fi
    [ -n "$OUT" ] && NOTES+="$OUT"$'\n'
done <<< "$PROJECTS"

[ -n "$NOTES" ] || exit 0

MSG="CHECKPOINT REPAIRED — working-context.md was edited directly instead of through \`checkpoint.py write\`, so the file was normalised:
${NOTES}Next time pipe the entry body to \`python3 ~/.agent-configs/bin/checkpoint.py write --project <p>\` (see the checkpoint skill); it carries the User Intent ledger forward, inserts the record separator and updates the timeline in one call."
python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":sys.argv[1]}}))' "$MSG"
exit 0
