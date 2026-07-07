#!/bin/bash
# PostToolUse hook: validate writes to obsidian vault
# Reads JSON from stdin, checks file conventions

INPUT=$(cat)

# Extract file_path from tool input JSON
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', d)
    print(ti.get('file_path', ''))
except: pass
" 2>/dev/null)

# Only validate writes to obsidian_notes
case "$FILE_PATH" in
    */obsidian_notes/*) ;;
    *) exit 0 ;;
esac

# Skip non-md files
case "$FILE_PATH" in
    *.md) ;;
    *.yaml|*.yml|*.sh|*.log) exit 0 ;;
    *) exit 0 ;;
esac

BASENAME=$(basename "$FILE_PATH")

# Skip system files that are exempt from conventions
case "$BASENAME" in
    session-log.md|open-questions.md|connections.md|README.md) exit 0 ;;
esac

# Skip scripts directory
case "$FILE_PATH" in
    */scripts/*) exit 0 ;;
esac

# Signal to the Stop hook that meaningful vault work happened. Keyed identically
# to session-stop.sh so the marker written here is the one it consumes. Set for
# any real vault note (past the exempt/system/script filters above), whether or
# not the validation below passes — a write is work either way.
AKEY=$(echo "$INPUT" | python3 -c "import sys,json,hashlib
d=json.load(sys.stdin)
k=d.get('session_id') or d.get('transcript_path') or ''
print(hashlib.sha256(k.encode()).hexdigest()[:16] if k else '')" 2>/dev/null)
[ -z "$AKEY" ] && AKEY="day-$(date +%Y-%m-%d)"
ADIR="${XDG_CACHE_HOME:-$HOME/.cache}/agent-configs/stop-reminders"
mkdir -p "$ADIR" 2>/dev/null
find "$ADIR" -type f -mtime +7 -delete 2>/dev/null       # keep the marker dir bounded
: > "$ADIR/activity-$AKEY"

ERRORS=""

# Check 1: Frontmatter exists
if [ -f "$FILE_PATH" ]; then
    FIRST_LINE=$(head -1 "$FILE_PATH")
    FIRST_LINE="${FIRST_LINE#$'\xEF\xBB\xBF'}"   # strip a leading UTF-8 BOM (read elsewhere via utf-8-sig)
    if [ "$FIRST_LINE" != "---" ]; then
        ERRORS+="MISSING FRONTMATTER: File does not start with YAML frontmatter (---). Every vault note MUST have frontmatter with date, tags, type, status.\n"
    fi
fi

# Check 2: Filename is lowercase-hyphenated (allow digits, dots for dates)
if echo "$BASENAME" | grep -qE '[A-Z ]'; then
    ERRORS+="BAD FILENAME: '$BASENAME' contains uppercase or spaces. Must be lowercase-hyphenated (e.g., my-note.md).\n"
fi

# Check 3: No collision-prone generic names
case "$BASENAME" in
    _index.md|index.md|Home.md|home.md)
        ERRORS+="COLLISION-PRONE FILENAME: '$BASENAME' will collide if multiple projects use the same name. Use a descriptive project-prefixed name instead.\n"
        ;;
esac

# Check 4: Has at least one wikilink
if [ -f "$FILE_PATH" ]; then
    if ! grep -q '\[\[' "$FILE_PATH"; then
        ERRORS+="NO WIKILINKS: File has no [[wikilinks]]. Every vault note must link to at least one related note.\n"
    fi
fi

if [ -n "$ERRORS" ]; then
    # PostToolUse plain stdout is invisible to the model; emit additionalContext
    # JSON (exit 0, non-blocking) so Claude actually sees the validation result.
    MSG=$(printf 'VAULT WRITE VALIDATION FAILED for %s:\n%b\nFix these issues in the file you just wrote.' "$BASENAME" "$ERRORS")
    python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":sys.argv[1]}}))' "$MSG"
fi
