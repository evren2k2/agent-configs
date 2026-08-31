#!/bin/bash
# PostToolUse hook: snapshot working-context checkpoints to timeline.
# Working-context is a circular buffer — old checkpoints get overwritten.
# Timeline preserves every checkpoint ever written (append-only).
#
# This is now a thin shim. The ---CHECKPOINT--- parser and the timeline digest
# live in bin/checkpoint.py so there is exactly one implementation; see that
# file's header. Checkpoints written via `checkpoint.py write` update the
# timeline themselves (a Bash write does not fire PostToolUse Write|Edit), so
# this path only covers checkpoints still written with the Write/Edit tools.

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', d)
    print(ti.get('file_path', ''))
except: pass
" 2>/dev/null)

# ONLY working-context.md
case "$FILE_PATH" in
    */working-context.md) ;;
    *) exit 0 ;;
esac

python3 "$HOME/.agent-configs/bin/checkpoint.py" timeline --file "$FILE_PATH" >/dev/null 2>&1
exit 0
