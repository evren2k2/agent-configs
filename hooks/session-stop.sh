#!/bin/bash
# Stop hook (Claude Code + agy): nudge to persist session knowledge — but only
# on turns that actually produced vault work. Stop fires at the end of EVERY
# turn and there is no "last turn" signal, so rather than firing blindly (or only
# once per session) we gate on an activity marker that validate-vault-write.sh
# drops whenever a real vault note is written/edited. On each Stop we emit the
# reminder iff such work happened since the last reminder, then consume the
# marker — so the nudge lands on stops that FOLLOW meaningful work (including the
# session's last one), never on trivial turns, and re-arms for each new batch of
# work instead of being capped at once per session.
#
# agy-compatible: identical stdin/stdout contract as before (additionalContext
# JSON, graceful key fallback); only the firing condition changed. The marker is
# set by an already-agy-bound PostToolUse hook, so no binding changes are needed.

INPUT=$(cat)

# Session key — MUST match the derivation in validate-vault-write.sh so we find
# the marker it wrote. Falls back to a per-day key when no session id is present
# (e.g. some agy invocations); both scripts fall back identically, so they pair.
KEY=$(echo "$INPUT" | python3 -c "import sys,json,hashlib
d=json.load(sys.stdin)
k=d.get('session_id') or d.get('transcript_path') or ''
print(hashlib.sha256(k.encode()).hexdigest()[:16] if k else '')" 2>/dev/null)
[ -z "$KEY" ] && KEY="day-$(date +%Y-%m-%d)"

MARK_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/agent-configs/stop-reminders"
ACTIVITY="$MARK_DIR/activity-$KEY"

[ -e "$ACTIVITY" ] || exit 0     # no vault work since the last reminder → stay quiet
rm -f "$ACTIVITY"                # consume it; the next vault write re-arms the reminder

MSG="SESSION LOG REMINDER: If this was a meaningful session, consider appending to ~/obsidian_notes/agent/session-log.md (what worked, what failed, key decisions, connections). PATTERN CHECK: did any reusable pattern emerge worth adding to ~/obsidian_notes/agent/instincts.yaml?"
python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":sys.argv[1]}}))' "$MSG"
