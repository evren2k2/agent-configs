#!/bin/bash
# init-vault.sh - Initialize a new Obsidian vault with the correct structure and Git repo

vault_path="$HOME/obsidian_notes"

if [ -d "$vault_path" ]; then
    echo "Error: $vault_path already exists. Move or delete it if you want to initialize a fresh one."
    exit 1
fi

echo "Initializing new Obsidian vault at $vault_path..."

# Create directories
mkdir -p "$vault_path/.obsidian"
mkdir -p "$vault_path/inbox"
mkdir -p "$vault_path/projects"
mkdir -p "$vault_path/areas"
mkdir -p "$vault_path/library"
mkdir -p "$vault_path/personal"
mkdir -p "$vault_path/agent"

# Create base README
cat > "$vault_path/README.md" <<EOF
# Obsidian Notes

This is your agent-managed Obsidian vault.

## Structure
- \`areas/\`: Thematic folders for notes.
- \`agent/\`: Context and metadata managed by your CLI agents.
- \`.obsidian/\`: Obsidian configuration.
EOF

# Create .gitignore
cat > "$vault_path/.gitignore" <<EOF
.obsidian/workspace
.obsidian/workspace.json
.obsidian/cache/
*.tmp
EOF

# Git initialization
cd "$vault_path" || exit
git init
git add .
git commit -m "Initial vault structure"

echo -e "\nVault initialized successfully!"
echo -e "\nNext steps:"
echo "1. Create a private repo on GitHub (e.g., 'obsidian_notes')."
echo "2. Run: git remote add origin <your-repo-url>"
echo "3. Run: git push -u origin main"
