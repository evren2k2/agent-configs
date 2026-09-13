#!/usr/bin/env python3
"""checkpoint — append / trim / read working-context checkpoints in one process.

WHY A SCRIPT AND NOT A SEQUENCE OF AGENT TOOL CALLS
    Appending an entry, trimming to the last N, and snapshotting the entry to
    timeline.md share one input and need no model decision between them: the body
    is already composed by the caller, "keep the last N" is a fixed rule, and the
    project name comes from the caller. Done as agent tool calls that is four
    full-context round trips (read, append, re-read, rewrite); done here it is
    one. The file work was never the cost — the turns were.

    Corollary worth knowing: a write performed here does NOT fire Claude Code's
    PostToolUse Write|Edit hooks, so `hooks/update-timeline.sh` would never see it.
    That is why `write` appends to timeline.md itself rather than relying on the
    hook. The hook remains for checkpoints still written with the Write/Edit tools.

THE ---CHECKPOINT--- PARSER LIVES HERE AND NOWHERE ELSE
    It was previously reimplemented three times (python in update-timeline.sh, awk
    in pre-compact.sh, grep in session-start.sh). `hooks/update-timeline.sh` and
    the `vault_checkpoint` MCP tool in bin/vault-mcp.py both call in here now.

DOCUMENT SHAPE
    working-context.md is a preamble (frontmatter + prose the agent maintains by
    hand) followed by zero or more entries separated by a `---CHECKPOINT---` line.
    Trimming only ever drops entries; the preamble is never touched.

USAGE
    checkpoint.py write  --project NAME [--keep 5] [--no-timeline]   # body on stdin
    checkpoint.py read   --project NAME [-n 1] [--headers]
    checkpoint.py list
    checkpoint.py timeline --file PATH        # snapshot PATH's last entry (hook path)
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent
if str(BIN_DIR) not in sys.path:
    sys.path.append(str(BIN_DIR))

from vault import vault_root, _atomic_write_text  # root resolution + durable writes

SEP = "---CHECKPOINT---"
DEFAULT_KEEP = 5

# A separator counts only when it is the WHOLE line. Notes legitimately mention the
# marker in prose — projects/kahin-v1-internal/working-context.md documents the
# ordering convention with an inline `---CHECKPOINT---` — and a substring split there
# tears the hand-maintained preamble into bogus "entries" that trimming then deletes.
SEP_RE = re.compile(r"(?m)^---CHECKPOINT---[ \t]*\r?$")


# ------------------------------------------------------------------ locating files
def context_path(vault: Path, project: str | None) -> Path:
    """Per-project working context, or the agent-level fallback when unscoped."""
    if project:
        return vault / "projects" / project / "working-context.md"
    return vault / "agent" / "working-context.md"


def project_of(path: Path) -> str | None:
    parts = path.resolve().parts
    if "projects" in parts:
        i = parts.index("projects")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def timeline_path(ctx: Path) -> Path:
    """timeline.md sits beside working-context.md for a project, else at vault root."""
    return ctx.parent / "timeline.md" if project_of(ctx) else vault_root() / "timeline.md"


# ------------------------------------------------------------------ the parser
def split_document(text: str) -> tuple[str, list[str]]:
    """-> (preamble, entries). Entries are stripped and never empty.

    Splits only on a line that is exactly the separator; see SEP_RE.
    """
    parts = SEP_RE.split(text)
    if len(parts) == 1:
        return text, []
    return parts[0], [e.strip() for e in parts[1:] if e.strip()]


def join_document(preamble: str, entries: list[str]) -> str:
    parts = [preamble.rstrip()] if preamble.strip() else []
    parts += [f"{SEP}\n{e.strip()}" for e in entries]
    return "\n\n".join(parts) + "\n"


def entry_header(entry: str) -> str:
    for line in entry.splitlines():
        s = line.strip()
        if s.startswith("## Checkpoint"):
            return re.sub(r"^##\s*Checkpoint\s*[-—]*\s*", "", s)
    return "(no header)"


# ------------------------------------------------------------------ intent ledger
# The `### User Intent` ledger is the verbatim record of everything the user has
# specified. Progress can be re-derived from the repo; intent cannot be re-derived
# from anything, so it is the one section that must never fall out of the 5-entry
# buffer. Carrying it forward on every write makes the newest checkpoint
# self-sufficient, which is what lets the buffer stay small.
INTENT_HEADING = "### User Intent"
_INTENT_RE = re.compile(r"(?im)^###\s+User\s+Intent\b[^\n]*\n")


def intent_body(entry: str) -> str:
    """The ledger items from `entry`, without the heading. '' when absent."""
    m = _INTENT_RE.search(entry)
    if not m:
        return ""
    rest = entry[m.end():]
    nxt = re.search(r"(?m)^###\s", rest)
    return (rest[:nxt.start()] if nxt else rest).strip()


def carry_intent(body: str, entries: list[str]) -> str:
    """Splice the most recent prior ledger into `body`.

    Prior items always sort above the new ones, so the ledger stays chronological.
    When `body` has no ledger section at all we insert one ahead of its first
    `### ` heading — the ledger leads the entry by convention.
    """
    prior = ""
    for e in reversed(entries):
        prior = intent_body(e)
        if prior:
            break
    if not prior:
        return body

    m = _INTENT_RE.search(body)
    if m:
        new_items = intent_body(body)
        if prior in new_items:              # already carried by the caller
            return body
        merged = prior + ("\n" + new_items if new_items else "")
        rest = body[m.end():]
        nxt = re.search(r"(?m)^###\s", rest)
        tail = rest[nxt.start():] if nxt else ""
        return body[:m.end()] + merged + "\n\n" + tail

    nxt = re.search(r"(?m)^###\s", body)
    block = f"{INTENT_HEADING}\n{prior}\n\n"
    if nxt:
        return body[:nxt.start()] + block + body[nxt.start():]
    return body.rstrip() + "\n\n" + block.rstrip() + "\n"


# ------------------------------------------------------------------ timeline digest
def timeline_lines(entry: str) -> tuple[str, str]:
    """Compress one entry to the 2-line timeline form.

    Ported verbatim in behavior from the inline python that used to live in
    hooks/update-timeline.sh, so existing timeline.md files stay format-stable.
    Line 1 = header + goal. Line 2 = progress / bugs / decisions / open items.
    """
    header, goal_parts = "", []
    progress_lines: list[str] = []
    bugs: list[str] = []
    decisions: list[str] = []
    opens: list[str] = []
    section = None

    for line in entry.splitlines():
        s = line.strip()

        if s.startswith("## Checkpoint"):
            header = s.lstrip("# ").strip()
            continue

        if s.startswith("### Current Goal"):
            section = "goal"; continue
        elif s.startswith("### Plan"):
            section = "plan"; continue
        elif s.startswith("### Progress") or s.startswith("### VCS Result"):
            section = "progress"; continue
        elif s.startswith("### Bug") or s.startswith("### Key Fix") or s.startswith("### Root Cause"):
            section = "bugs"; continue
        elif s.startswith("### Key Decision"):
            section = "decisions"; continue
        elif s.startswith("### Active File"):
            section = "files"; continue
        elif s.startswith("### Open") or s.startswith("### Blocked"):
            section = "open"; continue
        elif s.startswith("### "):
            section = None; continue

        if section == "goal" and s:
            if s.startswith("Then:"):
                goal_parts.append("then: " + s[5:].strip().strip('"')[:80])
            elif len(goal_parts) == 0:
                goal_parts.append(s.strip('"')[:200])

        if section == "progress" and s:
            if s.startswith("- [x]") or s.startswith("|"):
                progress_lines.append(s[:120])
            elif s.startswith(("1. [x]", "2. [x]", "3. [x]")):
                progress_lines.append(s[:120])
            elif s.startswith("- [ ]"):
                opens.append(s[5:].strip()[:80])
            elif s.startswith(("All ", "MAX_", "Sim time", "Average", "Result")):
                progress_lines.append(s[:120])

        if section == "bugs" and s:
            if s.startswith("- **") or s.startswith("1. **") or s.startswith("* **"):
                bugs.append(s.lstrip("*- 0123456789.").strip("**").split("**")[0][:80])
            elif s.startswith("- ") and "**" in s:
                bugs.append(s.lstrip("- ").split("**")[0][:80])

        if section == "decisions" and s and s.startswith("- **"):
            decisions.append(s.lstrip("- ").strip("**").split("**")[0][:80])

        if section == "open" and s:
            if s.startswith("- [ ]"):
                opens.append(s[5:].strip()[:80])
            elif s.startswith("- "):
                opens.append(s.lstrip("- ").strip("**").split("**")[0][:80])

    line1 = header + (" | " + goal_parts[0] if goal_parts else "")

    details: list[str] = []
    for p in progress_lines[:2]:
        clean = p.replace("- [x] ", "").replace("| ", " ").replace(" |", "").strip()
        if clean:
            details.append(clean[:100])
    for b in bugs[:2]:
        details.append("BUG: " + b)
    if decisions and len(details) < 3:
        details.append("DECISION: " + decisions[0])
    if opens:
        details.append("left: " + "; ".join(o[:60] for o in opens[:3]))

    return line1, (" | ".join(details) if details else "(no notable details)")


def append_timeline(ctx: Path, entry: str, stamp: str | None = None) -> Path:
    """Append the 2-line digest of `entry` to the timeline beside `ctx`."""
    tl = timeline_path(ctx)
    project = project_of(ctx)
    today = date.today().isoformat()
    stamp = stamp or f"{today} {time.strftime('%H:%M')}"

    if not tl.exists():
        tl.parent.mkdir(parents=True, exist_ok=True)
        fm = [
            "---", f"date: {today}", "tags: [agent_util, timeline]",
            "type: log", "status: active",
        ]
        if project:                       # genuine project logs carry project:
            fm.append(f"project: {project}")
        fm += [
            "---", "",
            "# Project Timeline", "",
            "Permanent record of all working-context checkpoints. Append-only — never edited.",
            "",
        ]
        _atomic_write_text(tl, "\n".join(fm))

    text = tl.read_text(encoding="utf-8")
    add = ""
    if f"## {today}" not in text:
        add += f"\n## {today}\n"
    line1, line2 = timeline_lines(entry)
    add += f"- {stamp}\n  {line1}\n  {line2}\n"
    _atomic_write_text(tl, text.rstrip("\n") + "\n" + add)
    return tl


# ------------------------------------------------------------------ commands
NEW_CONTEXT = """---
date: {today}
tags: [working-context]
type: mission
status: active
{project_line}---

# {title} — Working Context

Checkpoints follow, newest last. Written by `bin/checkpoint.py`, which keeps the
last {keep}; `timeline.md` keeps every one permanently.
"""


def cmd_write(args) -> int:
    body = sys.stdin.read().strip()
    if not body:
        print("checkpoint: refusing to write an empty entry (body comes from stdin)",
              file=sys.stderr)
        return 2

    ctx = context_path(vault_root(), args.project)
    if ctx.exists():
        preamble, entries = split_document(ctx.read_text(encoding="utf-8"))
    else:
        ctx.parent.mkdir(parents=True, exist_ok=True)
        name = args.project or "agent"
        preamble = NEW_CONTEXT.format(
            today=date.today().isoformat(),
            project_line=f"project: {args.project}\n" if args.project else "",
            title=name, keep=args.keep,
        )
        entries = []

    if not body.lstrip().startswith("## Checkpoint"):
        body = (f"## Checkpoint — {date.today().isoformat()} "
                f"{time.strftime('%H:%M')}\n\n{body}")

    if not getattr(args, "no_carry", False):
        carried = carry_intent(body, entries)
        if carried != body:
            print("intent ledger carried forward from the previous checkpoint")
            body = carried

    entries.append(body)
    dropped = max(0, len(entries) - args.keep)
    entries = entries[-args.keep:]

    _atomic_write_text(ctx, join_document(preamble, entries))
    print(f"checkpoint written: {ctx}  ({len(entries)} kept"
          + (f", {dropped} trimmed" if dropped else "") + ")")

    if not args.no_timeline:
        print(f"timeline updated:   {append_timeline(ctx, body)}")
    return 0


def cmd_read(args) -> int:
    ctx = context_path(vault_root(), args.project)
    if not ctx.exists():
        print(f"checkpoint: no working context at {ctx}", file=sys.stderr)
        return 1

    _, entries = split_document(ctx.read_text(encoding="utf-8"))
    if not entries:
        print(f"checkpoint: {ctx} has no checkpoints yet", file=sys.stderr)
        return 1

    picked = entries[-args.n:] if args.n > 0 else entries
    if args.headers:
        for e in picked:
            print(entry_header(e))
        return 0

    print(f"# {ctx}  ({len(picked)} of {len(entries)} checkpoints, newest last)\n")
    print(f"\n\n{SEP}\n\n".join(picked))
    return 0


def cmd_list(args) -> int:
    vault = vault_root()
    found = False
    for ctx in sorted(vault.glob("projects/*/working-context.md")) + \
            [vault / "agent" / "working-context.md"]:
        if not ctx.exists():
            continue
        _, entries = split_document(ctx.read_text(encoding="utf-8"))
        label = project_of(ctx) or "agent"
        for e in entries:
            print(f"  {label}: {entry_header(e)}")
            found = True
    return 0 if found else 1


def cmd_timeline(args) -> int:
    """Hook path: snapshot the last entry of an already-written file."""
    ctx = Path(args.file)
    if not ctx.exists():
        return 0
    _, entries = split_document(ctx.read_text(encoding="utf-8"))
    if not entries:
        return 0
    append_timeline(ctx, entries[-1])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="checkpoint", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="append an entry (body on stdin), trim, snapshot")
    w.add_argument("--project", help="vault project name; omit for agent/working-context.md")
    w.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    w.add_argument("--no-timeline", action="store_true")
    w.add_argument("--no-carry", action="store_true",
                   help="do not carry the previous checkpoint's User Intent ledger "
                        "forward (only when deliberately rewriting it in full)")
    w.set_defaults(fn=cmd_write)

    r = sub.add_parser("read", help="print the last N checkpoints verbatim")
    r.add_argument("--project")
    r.add_argument("-n", type=int, default=1, help="how many, newest last (0 = all)")
    r.add_argument("--headers", action="store_true", help="headers only, one per line")
    r.set_defaults(fn=cmd_read)

    l = sub.add_parser("list", help="one line per checkpoint across all projects")
    l.set_defaults(fn=cmd_list)

    t = sub.add_parser("timeline", help="snapshot a written file's last entry")
    t.add_argument("--file", required=True)
    t.set_defaults(fn=cmd_timeline)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
