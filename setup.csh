#!/bin/tcsh
# setup.csh - Symlink agent configurations for TCSH

set REPO_DIR = `dirname $0`
set REPO_DIR = `cd $REPO_DIR && pwd`
set BACKUP_SUFFIX = ".orig."`date +%Y%m%d_%H%M%S`

foreach agent (claude gemini)
    echo "===> Setting up $agent..."
    set target_dir = "$HOME/.$agent"
    if (! -d "$target_dir") mkdir -p "$target_dir"
    
    foreach item (settings.json CLAUDE.md GEMINI.md rules skills)
        set src = "$REPO_DIR/.$agent/$item"
        set dest = "$target_dir/$item"
        
        if (! -e "$src") continue
        
        if (-l "$dest") then
            echo "  [Skipping] $item (already a symlink)"
        else if (-e "$dest") then
            echo "  [Backup] Moving existing $item to $item$BACKUP_SUFFIX"
            mv "$dest" "$dest$BACKUP_SUFFIX"
            ln -s "$src" "$dest"
        else
            echo "  [Linking] $item"
            ln -s "$src" "$dest"
        endif
    end
end

echo "Done! Configuration symlinks established."
