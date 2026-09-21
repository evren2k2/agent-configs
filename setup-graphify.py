#!/usr/bin/env python3
"""setup-graphify.py — install the graphify code knowledge graph for Claude Code and agy.

Deliberately STANDALONE and SEPARATE from the vault installer (bin/agentcfg) so the two
stay modular — a graphify-only user never needs the vault tool, and vice versa:
  - vault only      -> run `agentcfg install`, never run this
  - graphify only   -> run this, never run agentcfg
  - both            -> run both; graphify's installer preserves any existing vault-mcp entry.

Per assistant:
  claude  per project: graphify's own `claude install --project` (skill, CLAUDE.md section,
          PreToolUse hooks) + a project .mcp.json entry pointing at graphify-out/graph.json.
  agy     once, globally: the `graphify` plugin under .antigravity/plugins/ (the same skill
          + references as Claude's, plus an mcp_config.json whose graph path is relative to
          the working directory — agy MCP servers are global, so the server follows the
          project you launch `agy` in). Linked into ~/.gemini/antigravity-cli/plugins/ and
          registered with `agy plugin install`, the same way agentcfg registers the vault
          plugins; running both installers is harmless.

Usage:
  python3 setup-graphify.py                    # GLOBAL: venv + PATH links + agy plugin
  python3 setup-graphify.py /path/to/project   # global (idempotent) + register claude there

Env overrides:
  GRAPHIFY_VENV     venv location              (default ~/.graphify-venv)
  GRAPHIFY_BIN_DIR  PATH dir for the symlinks  (default ~/.local/bin)
  GRAPHIFY_PKG      pip target                 (default graphifyy[mcp]; set a local path for a clone)
  PLATFORMS         assistants to wire up      (default "claude agy")
"""
import json, os, subprocess, sys
from pathlib import Path

HOME = Path.home()
WIN = os.name == "nt"
VENV = Path(os.environ.get("GRAPHIFY_VENV", HOME / ".graphify-venv"))
BIN_DIR = Path(os.environ.get("GRAPHIFY_BIN_DIR", HOME / ".local/bin"))
PKG = os.environ.get("GRAPHIFY_PKG", "graphifyy[mcp]")
PLATFORMS = os.environ.get("PLATFORMS", "claude agy").split()
REPO = Path(__file__).resolve().parent
AGY_PLUGIN_SRC = REPO / ".antigravity" / "plugins" / "graphify"
AGY_PLUGIN_DST = HOME / ".gemini" / "antigravity-cli" / "plugins" / "graphify"
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

# --- agy: one global plugin (skill + MCP), no per-project step ------------------------
def ensure_agy_plugin():
    """Link the repo's graphify plugin where agy discovers plugins and register it.

    Mirrors agentcfg's handling of the vault plugins (symlink, or a copy on Windows,
    then `agy plugin install <path>`). Idempotent; silent if agy is not installed.
    """
    if not AGY_PLUGIN_SRC.is_dir():
        print(f"[graphify] agy plugin source missing at {AGY_PLUGIN_SRC}; skipping agy")
        return
    AGY_PLUGIN_DST.parent.mkdir(parents=True, exist_ok=True)
    if AGY_PLUGIN_DST.is_symlink() or AGY_PLUGIN_DST.exists():
        if AGY_PLUGIN_DST.is_symlink() and AGY_PLUGIN_DST.resolve() == AGY_PLUGIN_SRC.resolve():
            print(f"[graphify] agy plugin already linked at {AGY_PLUGIN_DST}")
        elif WIN and AGY_PLUGIN_DST.is_dir():
            import shutil
            shutil.rmtree(AGY_PLUGIN_DST); shutil.copytree(AGY_PLUGIN_SRC, AGY_PLUGIN_DST)
            print(f"[graphify] agy plugin re-copied to {AGY_PLUGIN_DST} (Windows: re-run after repo edits)")
        else:
            print(f"[graphify] {AGY_PLUGIN_DST} exists and is not ours; leaving it alone")
            return
    else:
        if WIN:
            import shutil
            shutil.copytree(AGY_PLUGIN_SRC, AGY_PLUGIN_DST)
            print(f"[graphify] agy plugin copied to {AGY_PLUGIN_DST}")
        else:
            AGY_PLUGIN_DST.symlink_to(AGY_PLUGIN_SRC)
            print(f"[graphify] agy plugin linked {AGY_PLUGIN_DST} -> {AGY_PLUGIN_SRC}")
    import shutil as _sh
    if _sh.which("agy") is None:
        print("[graphify] agy not on PATH; plugin will register on first `agy plugin install` / `agentcfg update`")
        return
    try:
        subprocess.run(["agy", "plugin", "install", str(AGY_PLUGIN_DST)], check=True,
                       timeout=60, capture_output=True, text=True)
        print("[graphify] agy plugin registered (skill + graphify MCP server)")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[graphify] WARNING: `agy plugin install` failed: {getattr(e, 'stderr', e)}")


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
    # graphify's own installer: skill + CLAUDE.md section + PreToolUse hooks. agy is
    # handled once, globally, by the plugin (see ensure_agy_plugin) — its MCP server
    # resolves graphify-out/ relative to the working directory, so there is no
    # per-project step.
    for p in PLATFORMS:
        if p == "agy":
            continue
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
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    lines = existing.splitlines()
    with gi.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")   # don't glue our entry onto a final line lacking a newline
        for entry in ("graphify-out/", ".graphifyignore"):
            if entry not in lines:
                f.write(entry + "\n")
    print(f'[graphify] done. Build the graph:  graphify extract "{project}"   '
          "(code AST is free; docs/specs need a key or the in-session /graphify skill)")

def main():
    ensure_global()
    if "agy" in PLATFORMS:
        ensure_agy_plugin()
    positional = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not positional:
        print("[graphify] global install complete. Re-run with a project dir to register graphify there.")
        return
    register_project(Path(positional[0]).resolve())

if __name__ == "__main__":
    main()
