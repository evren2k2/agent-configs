#!/bin/bash
# setup.sh - Symlink agent configurations for Bash/Zsh

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKUP_SUFFIX=".orig.$(date +%Y%m%d_%H%M%S)"

setup_links() {
    local agent=$1
    local target_dir="$HOME/.$agent"
    
    echo "===> Setting up $agent..."
    mkdir -p "$target_dir"
    
    # Files to link
    local items=("settings.json" "CLAUDE.md" "GEMINI.md" "rules" "skills" "policies")
    
    for item in "${items[@]}"; do
        local src="$REPO_DIR/.$agent/$item"
        local dest="$target_dir/$item"
        
        [ ! -e "$src" ] && continue
        
        if [ -L "$dest" ] || [ -e "$dest" ] && [ "$src" -ef "$dest" ]; then
            echo "  [Skipping] $item (already linked)"
        elif [ -e "$dest" ]; then
            echo "  [Backup] Moving existing $item to $item$BACKUP_SUFFIX"
            mv "$dest" "$dest$BACKUP_SUFFIX"
            ln -s "$src" "$dest"
            echo "  [Linking] $item"
        else
            echo "  [Linking] $item"
            ln -s "$src" "$dest"
        fi
    done
}

setup_links "claude"
setup_links "gemini"

# --- ~/.agent-configs indirection symlink ------------------------------------
# Hook commands in settings.json reference ~/.agent-configs/hooks/... so the
# repo can be cloned to any path and still work without regenerating settings.
echo "===> Ensuring ~/.agent-configs symlink..."
if [ -L "$HOME/.agent-configs" ]; then
    echo "  [Skipping] ~/.agent-configs (already a link)"
elif [ -e "$HOME/.agent-configs" ]; then
    echo "  [Warning] ~/.agent-configs exists but is not a symlink; skipping."
else
    ln -s "$REPO_DIR" "$HOME/.agent-configs"
    echo "  [Linking] ~/.agent-configs -> $REPO_DIR"
fi

# --- Antigravity CLI plugins -------------------------------------------------
# `agy` reads plugins from $HOME/.gemini/antigravity-cli/plugins/<name>/.
# We symlink each .antigravity/plugins/<name> dir into that location so the
# antigravity CLI picks up the same skills + hooks + MCP wiring we maintain
# in this repo, side-by-side with any agy-imported gemini extensions.
setup_antigravity_plugins() {
    echo "===> Setting up antigravity plugins..."
    local src_root="$REPO_DIR/.antigravity/plugins"
    local dest_root="$HOME/.gemini/antigravity-cli/plugins"

    if [ ! -d "$src_root" ]; then
        echo "  [Skipping] no .antigravity/plugins directory in repo"
        return
    fi
    mkdir -p "$dest_root"

    for src in "$src_root"/*/; do
        [ -d "$src" ] || continue
        local name
        name="$(basename "$src")"
        local dest="$dest_root/$name"

        if [ -L "$dest" ]; then
            echo "  [Skipping] $name (already a link)"
        elif [ -e "$dest" ]; then
            echo "  [Backup] Moving existing $name to $name$BACKUP_SUFFIX"
            mv "$dest" "$dest$BACKUP_SUFFIX"
            ln -s "${src%/}" "$dest"
            echo "  [Linking] $name"
        else
            echo "  [Linking] $name"
            ln -s "${src%/}" "$dest"
        fi
    done

    # Register plugins in import_manifest.json so `agy plugin list` sees them
    # and they survive across agy startups. Preserve any pre-existing entries
    # (e.g. real gemini-cli extensions imported via `agy plugin import gemini`).
    local manifest_path="$HOME/.gemini/antigravity-cli/import_manifest.json"
    # Find a Python interpreter that actually executes (Windows has a broken
    # python3 stub from the Microsoft Store; probe for one that runs).
    local py=""
    for cand in python3 python py; do
        if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "" >/dev/null 2>&1; then
            py="$cand"
            break
        fi
    done
    if [ -z "$py" ]; then
        echo "  [Warning] no working python found - cannot register plugins in import_manifest.json"
        return
    fi
    "$py" - "$manifest_path" <<'PYEOF'
import json, os, sys, datetime
path = sys.argv[1]
repo_plugins = [
    ("obsidian", ["skills", "mcpServers", "hooks"]),
    ("general",  ["skills"]),
]
try:
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
except FileNotFoundError:
    manifest = {"imports": []}
if "imports" not in manifest or not isinstance(manifest["imports"], list):
    manifest["imports"] = []
existing = {entry.get("name") for entry in manifest["imports"]}
now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
changed = False
for name, components in repo_plugins:
    if name not in existing:
        manifest["imports"].append({
            "name": name,
            "source": "local",
            "importedAt": now,
            "components": components,
        })
        print(f"  [Registering] {name} in import_manifest.json")
        changed = True
if changed:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
PYEOF
}
setup_antigravity_plugins

# --- bin/ on PATH for the `vault` CLI ---------------------------------------
BIN_DIR="$REPO_DIR/bin"
if [ -d "$BIN_DIR" ]; then
    echo "===> Ensuring $BIN_DIR is on PATH..."
    chmod +x "$BIN_DIR/vault" 2>/dev/null
    # Pick the user's shell rc
    SHELL_RC=""
    case "${SHELL:-}" in
        */zsh) SHELL_RC="$HOME/.zshrc" ;;
        */bash) SHELL_RC="$HOME/.bashrc" ;;
        *) [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc" ;;
    esac
    if [ -n "$SHELL_RC" ]; then
        if grep -Fq "$BIN_DIR" "$SHELL_RC" 2>/dev/null; then
            echo "  [Skipping] PATH entry already in $SHELL_RC"
        else
            echo "" >> "$SHELL_RC"
            echo "# Added by agent-configs setup.sh" >> "$SHELL_RC"
            echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$SHELL_RC"
            echo "  [Added] $BIN_DIR to PATH in $SHELL_RC (re-source to activate)"
        fi
    else
        echo "  [Warning] Could not detect shell rc; add this to your shell config:"
        echo "    export PATH=\"$BIN_DIR:\$PATH\""
    fi
    # Sanity check python3
    if ! command -v python3 >/dev/null 2>&1 && ! command -v py >/dev/null 2>&1; then
        echo "  [Warning] python3 not found. The vault CLI requires Python 3.8+."
    fi
fi

# --- Semantic-search dependencies -------------------------------------------
# `vault embed` / vault_semantic_search need the packages in requirements.txt
# (sentence-transformers, numpy). The core vault CLI works without them.
echo "===> Semantic-search dependencies..."
REQ_FILE="$REPO_DIR/requirements.txt"
# Install target follows the cascade venv_bootstrap.py resolves at runtime:
# the repo venv, then the global venv, then the shell's Python.
PIP_PY=""
for venv in "$REPO_DIR/.venv" "$HOME/.venv"; do
    if [ -x "$venv/bin/python" ]; then PIP_PY="$venv/bin/python"; break; fi
done
[ -z "$PIP_PY" ] && PIP_PY="$(command -v python3 || command -v python || true)"

DEPS_PROBE='import importlib.util as u,sys; sys.exit(0 if u.find_spec("sentence_transformers") and u.find_spec("numpy") else 1)'
if [ -z "$PIP_PY" ]; then
    echo "  [Warning] no Python found — semantic search will be unavailable."
elif "$PIP_PY" -c "$DEPS_PROBE" 2>/dev/null; then
    echo "  [OK] dependencies already present ($PIP_PY)"
else
    echo "  Installing into $PIP_PY ..."
    if "$PIP_PY" -m pip install --quiet -r "$REQ_FILE"; then
        echo "  [OK] semantic-search dependencies installed"
    else
        echo "  [Warning] install failed — semantic search will be unavailable."
        echo "            Fix your Python setup, then run:"
        echo "              <python> -m pip install -r \"$REQ_FILE\""
        echo "            If the system Python is locked, create a venv at"
        echo "              $REPO_DIR/.venv  (or ~/.venv)  and install there."
    fi
fi

# --- Write vault-mcp into ~/.gemini/config/mcp_config.json (agy brain/edit mode) ---
# agy brain/edit mode reads MCP config from ~/.gemini/config/, not antigravity-cli/.
# Writing vault-mcp here makes vault tools available without /mcp in the main session.
echo "===> Registering vault-mcp in ~/.gemini/config/mcp_config.json..."
GEMINI_CONFIG_MCP="$HOME/.gemini/config/mcp_config.json"
if [ -z "$PIP_PY" ]; then
    echo "  [Warning] no Python found - cannot update $GEMINI_CONFIG_MCP"
else
    "$PIP_PY" - "$GEMINI_CONFIG_MCP" <<'PYEOF'
import json, os, sys
path = sys.argv[1]
vault_mcp_args = 'S="$HOME/.agent-configs/bin/vault-mcp.py"; for P in python3 python py; do command -v "$P" >/dev/null 2>&1 && "$P" -c "" >/dev/null 2>&1 && exec "$P" "$S"; done; echo "vault-mcp: no working python in PATH" >&2; exit 1'
try:
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}
if not isinstance(config.get("mcpServers"), dict):
    config["mcpServers"] = {}
if "vault-mcp" not in config["mcpServers"]:
    config["mcpServers"]["vault-mcp"] = {
        "command": "bash",
        "args": ["-c", vault_mcp_args],
        "trust": True,
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"  [Written] vault-mcp to {path}")
else:
    print(f"  [Skipping] vault-mcp already in {path}")
PYEOF
fi

echo -e "\nDone! Configuration links established."

VAULT_PATH="$HOME/obsidian_notes"
if [ -e "$VAULT_PATH" ]; then
    echo -e "\n\033[32m[Vault detected] $VAULT_PATH\033[0m"
else
    echo -e "\nNext Step: Setup your Obsidian Vault"
    echo "No vault found at $VAULT_PATH. Choose one of:"
    echo ""
    echo "Option A: Clone an existing vault repo:"
    echo "  git clone <your-repo-url> $VAULT_PATH"
    echo ""
    echo "Option B: Link an existing vault from another location:"
    echo "  ln -s <path-to-your-vault> $VAULT_PATH"
    echo ""
    echo "Option C: Initialize a fresh vault:"
    echo "  ./init-vault.sh"
fi

