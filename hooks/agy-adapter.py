#!/usr/bin/env python3
"""agy-adapter — run the Claude Code hook scripts under agy's hook contract.

agy (antigravity CLI) loads `plugins/<name>/hooks.json` and speaks a different
protocol from Claude Code (agy's embedded "Lifecycle Hooks" docs):
  * input is JSON on stdin with `conversationId`, `workspacePaths`, `transcriptPath`,
    and for tool events `toolCall: {name, args}` — agy names (`write_to_file`,
    `run_command`) and agy argument keys (`TargetFile`, `CommandLine`);
  * the command runs in the folder holding hooks.json, not the workspace;
  * output is JSON on stdout: PreInvocation injects `{"injectSteps":
    [{"ephemeralMessage": ...}]}`, PostToolUse must print `{}`, and Stop may answer
    `{"decision": "continue", "reason": ...}` to keep the agent going.

Until 2026-10-07 none of this was bridged and agy loaded zero hooks. This adapter
translates each event into the Claude-style stdin the scripts already read
(`session_id`, `transcript_path`, `tool_input.file_path|command`), runs them in the
workspace, and wraps what they print. PostToolUse cannot speak to the model in agy,
so its messages (validation failures, stale-note and repair notices) are queued per
conversation and delivered by the next PreInvocation. Session-start text is injected
once per conversation. Any failure prints `{}` — a hook must never block the agent.

usage: agy-adapter.py <PreInvocation|PostToolUse|Stop> <script.sh> [script.sh ...]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
STATE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "agent-configs" / "agy-hooks"
FILE_KEYS = ("TargetFile", "AbsolutePath", "FilePath", "file_path")
CMD_KEYS = ("CommandLine", "command")


def _arg(args: dict, keys) -> str:
    for k in keys:
        v = args.get(k)
        if isinstance(v, str) and v:
            # agy transcripts show args JSON-encoded a second time ("\"/path\"").
            if v.startswith('"'):
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            return v
    return ""


def claude_payload(d: dict, workspace: str) -> dict:
    """The Claude Code hook input the scripts read."""
    tc = d.get("toolCall") or {}
    args = tc.get("args") or {}
    tool_input = {}
    path = _arg(args, FILE_KEYS)
    if path:
        tool_input["file_path"] = path if os.path.isabs(path) else os.path.join(workspace, path)
    cmd = _arg(args, CMD_KEYS)
    if cmd:
        tool_input["command"] = cmd
    return {"session_id": d.get("conversationId", ""), "transcript_path": d.get("transcriptPath", ""),
            "cwd": workspace, "tool_name": tc.get("name", ""), "tool_input": tool_input}


def run(script: str, payload: dict, workspace: str) -> str:
    """Run one hook script; return the message it meant for the model, or ''."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    try:
        p = subprocess.run(["bash", str(HOOKS / script)], input=json.dumps(payload), text=True,
                           capture_output=True, cwd=workspace, env=env, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = p.stdout.strip()
    if not out:
        return ""
    try:
        return json.loads(out).get("hookSpecificOutput", {}).get("additionalContext", "") or ""
    except (ValueError, AttributeError):
        return out              # plain text (session-start.sh) is the message itself


def _key(conversation: str) -> str:
    return hashlib.sha256(conversation.encode()).hexdigest()[:16] if conversation else "no-conversation"


def main() -> int:
    event, scripts = sys.argv[1], sys.argv[2:]
    try:
        d = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        d = {}
    workspace = next(iter(d.get("workspacePaths") or []), "") or os.getcwd()
    if not os.path.isdir(workspace):
        workspace = os.getcwd()
    payload = claude_payload(d, workspace)
    key = _key(d.get("conversationId", ""))
    STATE.mkdir(parents=True, exist_ok=True)
    import time
    for f in STATE.iterdir():                 # one marker per conversation: keep it bounded
        if time.time() - f.stat().st_mtime > 7 * 86400:
            f.unlink(missing_ok=True)
    queue = STATE / f"queue-{key}"

    if event == "PreInvocation":
        msgs = []
        started = STATE / f"started-{key}"
        if not started.exists():
            started.touch()
            msgs += [m for s in scripts if (m := run(s, payload, workspace))]
        if queue.exists():
            msgs.append(queue.read_text(encoding="utf-8").strip())
            queue.unlink()
        out = {"injectSteps": [{"ephemeralMessage": "\n\n".join(msgs)}]} if msgs else {}
    elif event == "PostToolUse":
        msgs = [m for s in scripts if (m := run(s, payload, workspace))]
        if msgs:
            with queue.open("a", encoding="utf-8") as f:
                f.write("\n\n".join(msgs) + "\n\n")
        out = {}
    elif event == "Stop":
        msgs = [m for s in scripts if (m := run(s, payload, workspace))]
        out = {"decision": "continue", "reason": "\n\n".join(msgs)} if msgs else {}
    else:
        out = {}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:            # never block the agent
        print("{}")
        raise SystemExit(0)
