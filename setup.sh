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
        if grep -Fq "agent-configs/bin" "$SHELL_RC" 2>/dev/null; then
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

echo -e "\nDone! Configuration links established."
echo -e "\nNext Step: Setup your Obsidian Vault"
echo "The configurations expect a vault at: $HOME/obsidian_notes"
echo ""
echo "Option A: Clone an existing vault repo:"
echo "  git clone <your-repo-url> $HOME/obsidian_notes"
echo ""
echo "Option B: Initialize a fresh vault:"
echo "  ./init-vault.sh"

