#!/bin/bash
# Claude Code Stop hook: remind about session log and pattern extraction

# Clean up session tag so next session doesn't inherit stale context
rm -f "$HOME/.claude/.session-topic" "$HOME/.gemini/.session-topic"

# Session log reminder (no daily throttle)
echo "SESSION LOG REMINDER: If this was a meaningful session, consider appending to ~/obsidian_notes/agent/session-log.md with: what worked, what failed, key decisions, and connections made."

# Remind about instinct extraction
echo "PATTERN CHECK: Did this session reveal any reusable pattern worth adding to ~/obsidian_notes/agent/instincts.yaml?"
