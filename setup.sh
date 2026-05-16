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
    local items=("settings.json" "CLAUDE.md" "GEMINI.md" "rules" "skills")
    
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

echo -e "\nDone! Configuration links established."
echo -e "\nNext Step: Setup your Obsidian Vault"
echo "The configurations expect a vault at: $HOME/obsidian_notes"
echo ""
echo "Option A: Clone an existing vault repo:"
echo "  git clone <your-repo-url> $HOME/obsidian_notes"
echo ""
echo "Option B: Initialize a fresh vault:"
echo "  ./init-vault.sh"

