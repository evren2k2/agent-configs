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

ERRORS=""

# Check 1: Frontmatter exists
if [ -f "$FILE_PATH" ]; then
    FIRST_LINE=$(head -1 "$FILE_PATH")
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
    echo -e "VAULT WRITE VALIDATION FAILED for $BASENAME:\n$ERRORS\nFix these issues in the file you just wrote."
fi
