# init-vault.ps1 - Initialize a new Obsidian vault with the correct structure and Git repo

$vault_path = Join-Path $HOME "obsidian_notes"

if (Test-Path $vault_path) {
    Write-Host "Error: $vault_path already exists. Move or delete it if you want to initialize a fresh one." -ForegroundColor Red
    exit 1
}

Write-Host "Initializing new Obsidian vault at $vault_path..." -ForegroundColor Cyan

# Create directories
New-Item -ItemType Directory -Path $vault_path | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path ".obsidian") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path "inbox") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path "projects") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path "areas") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path "library") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path "personal") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $vault_path "agent") | Out-Null

# Create base README
$readme_content = @"
# Obsidian Notes

This is your agent-managed Obsidian vault.

## Structure
- `areas/`: Thematic folders for notes.
- `agent/`: Context and metadata managed by your CLI agents.
- `.obsidian/`: Obsidian configuration.
"@
Set-Content -Path (Join-Path $vault_path "README.md") -Value $readme_content

# Create .gitignore
$gitignore_content = @"
.obsidian/workspace
.obsidian/workspace.json
.obsidian/cache/
*.tmp
"@
Set-Content -Path (Join-Path $vault_path ".gitignore") -Value $gitignore_content

# Git initialization
Push-Location $vault_path
git init
git add .
git commit -m "Initial vault structure"

Write-Host "`nVault initialized successfully!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Create a private repo on GitHub (e.g., 'obsidian_notes')."
Write-Host "2. Run: git remote add origin <your-repo-url>"
Write-Host "3. Run: git push -u origin main"
Pop-Location
