#!/usr/bin/env python3
"""setup-graphify.py — install the graphify code knowledge graph for Claude Code.

Deliberately STANDALONE and SEPARATE from the vault installer (bin/agentcfg) so the two
stay modular — a graphify-only user never needs the vault tool, and vice versa:
  - vault only      -> run `agentcfg install`, never run this
  - graphify only   -> run this, never run agentcfg
  - both            -> run both; graphify's installer preserves any existing vault-mcp entry.

Usage:
  python3 setup-graphify.py                    # GLOBAL only: venv + put graphify on PATH
  python3 setup-graphify.py /path/to/project   # global (idempotent) + register graphify there

Env overrides:
  GRAPHIFY_VENV     venv location              (default ~/.graphify-venv)
  GRAPHIFY_BIN_DIR  PATH dir for the symlinks  (default ~/.local/bin)
  GRAPHIFY_PKG      pip target                 (default graphifyy[mcp]; set a local path for a clone)
  PLATFORMS         assistants to wire up      (default "claude"; agy excluded — no per-project MCP)
"""
import json, os, subprocess, sys
from pathlib import Path

HOME = Path.home()
WIN = os.name == "nt"
VENV = Path(os.environ.get("GRAPHIFY_VENV", HOME / ".graphify-venv"))
BIN_DIR = Path(os.environ.get("GRAPHIFY_BIN_DIR", HOME / ".local/bin"))
PKG = os.environ.get("GRAPHIFY_PKG", "graphifyy[mcp]")
PLATFORMS = os.environ.get("PLATFORMS", "claude").split()
VENV_BIN = VENV / ("Scripts" if WIN else "bin")
VENV_PY = VENV_BIN / ("python.exe" if WIN else "python")
GRAPHIFY = VENV_BIN / ("graphify.exe" if WIN else "graphify")
# Machine-agnostic launcher: prefer graphify-mcp on PATH, else ~/.graphify-venv; graph path is project-relative.
LAUNCHER = ('GM=$(command -v graphify-mcp 2>/dev/null || echo "$HOME/.graphify-venv/bin/graphify-mcp"); '
            'exec "$GM" graphify-out/graph.json')

def run(cmd, **kw):
    subprocess.run([str(c) for c in cmd], check=True, **kw)

# --- global: dedicated venv + package + symlinks on PATH (idempotent) -----------------
def ensure_global():
    if not GRAPHIFY.exists():
        print(f"[graphify] creating venv at {VENV}")
        run([sys.executable, "-m", "venv", VENV])
        run([VENV_PY, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        print(f"[graphify] installing {PKG}")
        run([VENV_PY, "-m", "pip", "install", PKG])
    else:
        print(f"[graphify] venv already present at {VENV}")
    if WIN:
        print(f"[graphify] Windows: ensure {VENV_BIN} is on PATH (or install via pipx/uv).")
        return
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("graphify", "graphify-mcp"):
        link = BIN_DIR / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(VENV_BIN / name)
    print(f"[graphify] linked graphify + graphify-mcp -> {BIN_DIR}")
    if str(BIN_DIR) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"[graphify] WARNING: {BIN_DIR} is not on PATH — add it to your shell profile")

# --- per-project registration (additive; preserves existing servers) ------------------
def _server(trust):
    e = {"command": "bash", "args": ["-c", LAUNCHER]}
    if trust:
        e["trust"] = True
    return e

def _merge_server(path: Path, key: str, val: dict):
    d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    d.setdefault("mcpServers", {})[key] = val
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")

def register_project(project: Path):
    print(f"[graphify] registering in {project} for: {' '.join(PLATFORMS)}")
    # graphify's own installer: skill + CLAUDE.md section + PreToolUse hooks
    for p in PLATFORMS:
        run([GRAPHIFY, p, "install", "--project"], cwd=project)
    # MCP server registration (launcher, project-relative graph), preserving existing servers
    if "claude" in PLATFORMS:
        _merge_server(project / ".mcp.json", "graphify", _server(trust=False))
        slp = project / ".claude" / "settings.local.json"
        s = json.loads(slp.read_text(encoding="utf-8")) if slp.exists() else {}
        en = s.setdefault("enabledMcpjsonServers", [])
        if "graphify" not in en:
            en.append("graphify")
        slp.parent.mkdir(parents=True, exist_ok=True)
        slp.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    # keep build artifacts out of git
    gi = project / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    with gi.open("a", encoding="utf-8") as f:
        for entry in ("graphify-out/", ".graphifyignore"):
            if entry not in lines:
                f.write(entry + "\n")
    print(f'[graphify] done. Build the graph:  graphify extract "{project}"   '
          "(code AST is free; docs/specs need a key or the in-session /graphify skill)")

def main():
    ensure_global()
    positional = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not positional:
        print("[graphify] global install complete. Re-run with a project dir to register graphify there.")
        return
    register_project(Path(positional[0]).resolve())

if __name__ == "__main__":
    main()
