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
        
        if [ -L "$dest" ]; then
            echo "  [Skipping] $item (already a symlink)"
        elif [ -e "$dest" ]; then
            echo "  [Backup] Moving existing $item to $item$BACKUP_SUFFIX"
            mv "$dest" "$dest$BACKUP_SUFFIX"
            ln -s "$src" "$dest"
        else
            echo "  [Linking] $item"
            ln -s "$src" "$dest"
        fi
    done
}

setup_links "claude"
setup_links "gemini"

echo "Done! Configuration symlinks established."
