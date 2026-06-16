#!/usr/bin/env bash
# setup-graphify.sh — install the graphify code knowledge graph for Claude Code + Gemini CLI.
#
# Deliberately SEPARATE from the vault install (`agentcfg`) so the two are modular:
#   - vault only      -> run `agentcfg install`, never run this
#   - graphify only   -> run this, never run agentcfg
#   - both            -> run both; graphify's installer preserves any existing
#                        vault-mcp entry when it touches shared MCP config files.
#
# Usage:
#   ./setup-graphify.sh                    # GLOBAL only: venv + put graphify on PATH
#   ./setup-graphify.sh /path/to/project   # global (idempotent) + register graphify in that project
#   PLATFORMS="claude gemini" GRAPHIFY_PKG="graphifyy[mcp]" ./setup-graphify.sh /path/to/project
#
# Env overrides:
#   GRAPHIFY_VENV     venv location               (default ~/.graphify-venv)
#   GRAPHIFY_BIN_DIR  PATH dir for the symlinks   (default ~/.local/bin)
#   GRAPHIFY_PKG      pip target                  (default graphifyy[mcp]; set a local path to install a clone)
#   PLATFORMS         assistants to wire up       (default "claude gemini"; agy excluded — no per-project MCP scope)
set -euo pipefail

VENV="${GRAPHIFY_VENV:-$HOME/.graphify-venv}"
BIN_DIR="${GRAPHIFY_BIN_DIR:-$HOME/.local/bin}"
PKG="${GRAPHIFY_PKG:-graphifyy[mcp]}"
PLATFORMS="${PLATFORMS:-claude gemini}"

# ---------------------------------------------------------------------------
# 1. GLOBAL: dedicated venv + package + symlinks on PATH (idempotent)
# ---------------------------------------------------------------------------
if [ ! -x "$VENV/bin/graphify" ]; then
  echo "[graphify] creating venv at $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  echo "[graphify] installing $PKG"
  "$VENV/bin/pip" install "$PKG"
else
  echo "[graphify] venv already present at $VENV (skipping install)"
fi

mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/graphify"     "$BIN_DIR/graphify"
ln -sf "$VENV/bin/graphify-mcp" "$BIN_DIR/graphify-mcp"
echo "[graphify] linked graphify + graphify-mcp -> $BIN_DIR"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "[graphify] WARNING: $BIN_DIR is not on PATH — add it to your shell profile so the CLI/hooks resolve" ;;
esac

# ---------------------------------------------------------------------------
# 2. PER-PROJECT (only if a project dir was given)
# ---------------------------------------------------------------------------
PROJECT="${1:-}"
if [ -z "$PROJECT" ]; then
  echo "[graphify] global install complete. Re-run with a project dir to register graphify there."
  exit 0
fi
PROJECT="$(cd "$PROJECT" && pwd)"
echo "[graphify] registering graphify in $PROJECT for: $PLATFORMS"
cd "$PROJECT"

# 2a. graphify's own installer: skill + CLAUDE.md/GEMINI.md section + PreToolUse/BeforeTool hooks
for p in $PLATFORMS; do
  "$VENV/bin/graphify" "$p" install --project
done

# 2b. Register the MCP server with a machine-agnostic launcher, preserving existing servers
LAUNCHER='GM=$(command -v graphify-mcp 2>/dev/null || echo "$HOME/.graphify-venv/bin/graphify-mcp"); exec "$GM" graphify-out/graph.json'
"$VENV/bin/python" - "$PROJECT" "$LAUNCHER" "$PLATFORMS" <<'PY'
import json, os, sys
proj, launcher, platforms = sys.argv[1], sys.argv[2], sys.argv[3].split()

def entry(trust):
    e = {"command": "bash", "args": ["-c", launcher]}
    if trust:
        e["trust"] = True
    return e

def load(path):
    return json.load(open(path)) if os.path.exists(path) else {}

def dump(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(json.dumps(obj, indent=2) + "\n")

if "claude" in platforms:
    mcp = load(os.path.join(proj, ".mcp.json"))
    mcp.setdefault("mcpServers", {})["graphify"] = entry(trust=False)
    dump(os.path.join(proj, ".mcp.json"), mcp)
    # enable the project server (no tool-allow wildcard — that needs explicit user opt-in)
    slp = os.path.join(proj, ".claude", "settings.local.json")
    s = load(slp)
    en = s.setdefault("enabledMcpjsonServers", [])
    if "graphify" not in en:
        en.append("graphify")
    dump(slp, s)

if "gemini" in platforms:
    gp = os.path.join(proj, ".gemini", "settings.json")
    g = load(gp)  # preserves graphify's hook + any vault-mcp entry
    g.setdefault("mcpServers", {})["graphify"] = entry(trust=True)
    dump(gp, g)

print("[graphify] MCP server registered (launcher, project-relative graph path)")
PY

# 2c. Keep the build artifacts out of git
for f in "graphify-out/" ".graphifyignore"; do
  grep -qxF "$f" .gitignore 2>/dev/null || printf '%s\n' "$f" >> .gitignore
done

cat <<EOF
[graphify] done in $PROJECT.
  Next: build the graph (not done here — it has cost/method tradeoffs):
    graphify extract "$PROJECT"          # code AST is free; docs/specs need an API key
    # or, with no key, run /graphify .    in Claude/Gemini (the host session is the LLM)
  Then reload the assistant; it will check the graph before grepping.
EOF
