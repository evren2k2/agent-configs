#!/bin/bash
# Claude Code Stop hook: once per session, nudge to persist session knowledge.
# Stop fires at the end of every turn, so we throttle to one reminder per session
# via a session_id-keyed marker, and emit it as additionalContext JSON — plain
# stdout (and the old SessionEnd wiring) reach neither the model nor the user.

INPUT=$(cat)

# Identify the session; hash so the value is filesystem-safe. Fall back to a
# constant when absent so we err toward quiet (throttle) rather than spam.
KEY=$(echo "$INPUT" | python3 -c "import sys,json,hashlib
d=json.load(sys.stdin)
k=d.get('session_id') or d.get('transcript_path') or ''
print(hashlib.sha256(k.encode()).hexdigest()[:16] if k else 'default')" 2>/dev/null)
[ -z "$KEY" ] && KEY=default

MARK_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/agent-configs/stop-reminders"
mkdir -p "$MARK_DIR" 2>/dev/null
find "$MARK_DIR" -type f -mtime +7 -delete 2>/dev/null   # keep the marker dir bounded
MARK="$MARK_DIR/$KEY"
[ -e "$MARK" ] && exit 0                                  # already reminded this session
: > "$MARK"

MSG="SESSION LOG REMINDER: If this was a meaningful session, consider appending to ~/obsidian_notes/agent/session-log.md (what worked, what failed, key decisions, connections). PATTERN CHECK: did any reusable pattern emerge worth adding to ~/obsidian_notes/agent/instincts.yaml?"
python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":sys.argv[1]}}))' "$MSG"
