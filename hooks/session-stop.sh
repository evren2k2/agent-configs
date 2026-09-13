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

# Two asks, deliberately separated by CLASS. The old
# single "did any reusable pattern emerge?" was asked at end-of-turn with session
# specifics at peak salience, so it returned a situation-specific technical lesson every
# time — 30 of 30 entries, none of which ever recurred, in a file nothing read. Knowledge
# and disposition need different questions because they come from different places:
# knowledge from what the work taught, disposition from where the USER had to correct us.
MSG="SESSION LOG REMINDER: If this was a meaningful session, consider appending to ~/obsidian_notes/agent/session-log.md (what worked, what failed, key decisions, connections).

KNOWLEDGE CHECK: did this session establish something durable about how a system behaves — a non-obvious constraint, a weakness, something that will clash with future work? That belongs in a vault project note (projects/<p>/implementation/), NOT in instincts. Skip it if the code, the commit, or an existing note already says it.

DISPOSITION CHECK: did the user CORRECT you this session — your scope, your rigor, an assumption, an unmeasured claim? Do not ask what the task taught you; that returns knowledge. Ask where you were corrected. If there was such a moment, name the one-line rule that would have prevented it and queue it:
  python3 ~/.agent-configs/bin/instincts.py propose --disposition '<the rule>' --origin '<quote the user verbatim>' --project <p>
A disposition is about HOW to work and must hold on any turn. The test: if the rule stops being true when you switch projects, it is knowledge — write the note instead. No correction this session means nothing to queue; that is the normal case.
Propose it even if you think it is already queued — an identical rule from a later session is counted as the re-trigger that earns promotion, which is the only way anything ever leaves the queue. \`instincts.py list\` shows what is pending."
python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":sys.argv[1]}}))' "$MSG"
