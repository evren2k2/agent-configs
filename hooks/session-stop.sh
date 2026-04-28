#!/bin/bash
# Claude Code Stop hook: remind about session log and pattern extraction
VAULT="$HOME/obsidian_notes"
SESSION_LOG="$VAULT/agent/session-log.md"

# Clean up session tag so next session doesn't inherit stale context
rm -f "$HOME/.claude/.session-topic" "$HOME/.gemini/.session-topic"

# Check if session log was updated today
TODAY=$(date +%Y-%m-%d)
if [ -f "$SESSION_LOG" ]; then
    if ! grep -q "## $TODAY" "$SESSION_LOG"; then
        echo "SESSION LOG REMINDER: If this was a meaningful session, consider appending to ~/obsidian_notes/agent/session-log.md with: what worked, what failed, key decisions, and connections made."
    fi
fi

# Remind about instinct extraction
echo "PATTERN CHECK: Did this session reveal any reusable pattern worth adding to ~/obsidian_notes/agent/instincts.yaml?"
