#!/bin/bash
# PostToolUse hook: snapshot working-context checkpoints to timeline
# Working-context is a circular buffer — old checkpoints get overwritten.
# Timeline preserves every checkpoint ever written (append-only).
# Only triggers on working-context.md writes/edits.

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

# ONLY working-context.md
case "$FILE_PATH" in
    */working-context.md) ;;
    *) exit 0 ;;
esac

# Determine project from path
PROJECT=""
case "$FILE_PATH" in
    */projects/*/*)
        PROJECT=$(echo "$FILE_PATH" | sed -n 's|.*/projects/\([^/]*\)/.*|\1|p')
        ;;
esac

# Determine timeline file location
if [ -n "$PROJECT" ]; then
    PROJ_DIR=$(dirname "$FILE_PATH" | sed -n "s|\(.*projects/${PROJECT}\).*|\1|p")
    TIMELINE_FILE="${PROJ_DIR}/timeline.md"
else
    TIMELINE_FILE="$HOME/obsidian_notes/timeline.md"
fi

# Create timeline file with frontmatter if it doesn't exist
if [ ! -f "$TIMELINE_FILE" ]; then
    mkdir -p "$(dirname "$TIMELINE_FILE")"
    cat > "$TIMELINE_FILE" << HEADER
---
date: $(date '+%Y-%m-%d')
tags: [claude_util, gemini_util, timeline]
type: log
status: active
---

# Project Timeline

Permanent record of all working-context checkpoints. Append-only — never edited.

HEADER
fi

# Extract the LAST checkpoint from the current file on disk
# (the file has already been written by the time PostToolUse fires)
# Output: 2 lines — line1 = header+goal, line2 = notable details
OUTPUT=$(python3 -c "
import re, sys

with open('$FILE_PATH', 'r') as f:
    content = f.read()

# Split into checkpoints
checkpoints = re.split(r'---CHECKPOINT---', content)
last = ''
for cp in reversed(checkpoints):
    stripped = cp.strip()
    if stripped:
        last = stripped
        break

if not last:
    print('(empty)\n(empty)')
    sys.exit(0)

lines = last.split('\n')

# Section-aware extraction
header = ''
goal_parts = []
progress_lines = []
bugs = []
decisions = []
opens = []
active_files = []

section = None

for line in lines:
    s = line.strip()

    if s.startswith('## Checkpoint'):
        header = s.lstrip('# ').strip()
        continue

    # Detect sections
    if s.startswith('### Current Goal'):
        section = 'goal'; continue
    elif s.startswith('### Plan'):
        section = 'plan'; continue
    elif s.startswith('### Progress') or s.startswith('### VCS Result'):
        section = 'progress'; continue
    elif s.startswith('### Bug') or s.startswith('### Key Fix') or s.startswith('### Root Cause'):
        section = 'bugs'; continue
    elif s.startswith('### Key Decision'):
        section = 'decisions'; continue
    elif s.startswith('### Active File'):
        section = 'files'; continue
    elif s.startswith('### Open') or s.startswith('### Blocked'):
        section = 'open'; continue
    elif s.startswith('### '):
        section = None; continue

    # Collect by section
    if section == 'goal' and s:
        if s.startswith('Then:'):
            goal_parts.append('then: ' + s[5:].strip().strip('\"')[:80])
        elif len(goal_parts) == 0:
            goal_parts.append(s.strip('\"')[:200])

    if section == 'progress' and s:
        # Pick lines with concrete results: [x], tables, numbers
        if s.startswith('- [x]') or s.startswith('|'):
            progress_lines.append(s[:120])
        elif s.startswith('1. [x]') or s.startswith('2. [x]') or s.startswith('3. [x]'):
            progress_lines.append(s[:120])
        elif s.startswith('- [ ]'):
            opens.append(s[5:].strip()[:80])
        elif s.startswith(('All ', 'MAX_', 'Sim time', 'Average', 'Result')):
            progress_lines.append(s[:120])

    if section == 'bugs' and s:
        if s.startswith('- **') or s.startswith('1. **') or s.startswith('* **'):
            bugs.append(s.lstrip('*- 0123456789.').strip('**').split('**')[0][:80])
        elif s.startswith('- ') and '**' in s:
            bugs.append(s.lstrip('- ').split('**')[0][:80])

    if section == 'decisions' and s:
        if s.startswith('- **'):
            decisions.append(s.lstrip('- ').strip('**').split('**')[0][:80])

    if section == 'open' and s:
        if s.startswith('- [ ]'):
            opens.append(s[5:].strip()[:80])
        elif s.startswith('- **') or s.startswith('- '):
            opens.append(s.lstrip('- ').strip('**').split('**')[0][:80])

# LINE 1: header + goal
line1 = header
if goal_parts:
    line1 += ' | ' + goal_parts[0]

# LINE 2: notable details — pick most interesting bits
details = []

# Progress highlights (max 2)
for p in progress_lines[:2]:
    # Clean up table rows and checkboxes
    clean = p.replace('- [x] ', '').replace('| ', ' ').replace(' |', '')
    if clean.strip():
        details.append(clean.strip()[:100])

# Bugs (max 2)
for b in bugs[:2]:
    details.append('BUG: ' + b)

# Decisions (max 1)
if decisions and len(details) < 3:
    details.append('DECISION: ' + decisions[0])

# Open items
if opens:
    details.append('left: ' + '; '.join(o[:60] for o in opens[:3]))

line2 = ' | '.join(details) if details else '(no notable details)'

print(line1)
print(line2)
" 2>/dev/null)

[ -z "$OUTPUT" ] && OUTPUT="(checkpoint parse failed)\n(empty)"

# Timestamp
TS=$(date '+%Y-%m-%d %H:%M')

# Ensure today's date header exists
TODAY=$(date '+%Y-%m-%d')
if ! grep -q "## $TODAY" "$TIMELINE_FILE"; then
    echo "" >> "$TIMELINE_FILE"
    echo "## $TODAY" >> "$TIMELINE_FILE"
fi

# Append 2-line entry
echo "- ${TS}" >> "$TIMELINE_FILE"
echo "$OUTPUT" | while IFS= read -r line; do
    echo "  ${line}" >> "$TIMELINE_FILE"
done

exit 0
