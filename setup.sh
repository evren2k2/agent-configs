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

echo -e "\nDone! Configuration links established."
echo -e "\nNext Step: Setup your Obsidian Vault"
echo "The configurations expect a vault at: $HOME/obsidian_notes"
echo ""
echo "Option A: Clone an existing vault repo:"
echo "  git clone <your-repo-url> $HOME/obsidian_notes"
echo ""
echo "Option B: Initialize a fresh vault:"
echo "  ./init-vault.sh"

