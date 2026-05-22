# setup.ps1 - Symlink agent configurations for Windows PowerShell
# Note: Requires Developer Mode or Administrative privileges for symlinks

# Check for Git Bash (required for .sh hooks on Windows)
if (-not (Get-Command bash -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'bash' not found in PATH." -ForegroundColor Red
    Write-Host "Git Bash is required to run the agent hooks on Windows." -ForegroundColor Red
    Write-Host "Please install Git for Windows: https://gitforwindows.org/" -ForegroundColor Cyan
    Write-Host "Ensure 'Git\bin' or 'Git\usr\bin' is added to your system PATH." -ForegroundColor Cyan
    exit 1
}

$REPO_DIR = $PSScriptRoot
$BACKUP_SUFFIX = ".orig." + (Get-Date -Format "yyyyMMdd_HHmmss")

function Setup-Links($agent) {
    Write-Host "===> Setting up $agent..." -ForegroundColor Cyan
    $target_dir = Join-Path $HOME ".$agent"
    
    if (-not (Test-Path $target_dir)) {
        New-Item -ItemType Directory -Path $target_dir | Out-Null
    }
    
    $items = @("settings.json", "CLAUDE.md", "GEMINI.md", "rules", "skills", "policies")
    
    foreach ($item in $items) {
        $src = Join-Path $REPO_DIR ".$agent\$item"
        $dest = Join-Path $target_dir $item
        
        if (-not (Test-Path $src)) { continue }
        
        $itemInfo = Get-Item -Path $dest -ErrorAction SilentlyContinue
        
        $isDir = (Get-Item -Path $src).PSIsContainer
        $linkType = if ($isDir) { "Junction" } else { "HardLink" }

        if ($null -ne $itemInfo -and $itemInfo.Attributes -match "ReparsePoint") {
            Write-Host "  [Skipping] $item (already a link)"
        }
        elseif (Test-Path $dest) {
            Write-Host "  [Backup] Moving existing $item to $item$BACKUP_SUFFIX" -ForegroundColor Yellow
            Rename-Item -Path $dest -NewName ($item + $BACKUP_SUFFIX)
            
            try {
                New-Item -ItemType SymbolicLink -Path $dest -Target $src -ErrorAction Stop | Out-Null
                Write-Host "  [Linking] $item (SymbolicLink)" -ForegroundColor Green
            } catch {
                New-Item -ItemType $linkType -Path $dest -Target $src | Out-Null
                Write-Host "  [Linking] $item ($linkType Fallback)" -ForegroundColor Yellow
            }
        }
        else {
            try {
                New-Item -ItemType SymbolicLink -Path $dest -Target $src -ErrorAction Stop | Out-Null
                Write-Host "  [Linking] $item (SymbolicLink)" -ForegroundColor Green
            } catch {
                New-Item -ItemType $linkType -Path $dest -Target $src | Out-Null
                Write-Host "  [Linking] $item ($linkType Fallback)" -ForegroundColor Yellow
            }
        }
    }
}

Setup-Links "claude"
Setup-Links "gemini"

# --- ~/.agent-configs indirection symlink -----------------------------------
# Hook commands in settings.json reference ~/.agent-configs/hooks/... so the
# repo can be cloned to any path and still work without regenerating settings.
Write-Host "===> Ensuring ~/.agent-configs symlink..." -ForegroundColor Cyan
$agentLink = Join-Path $HOME ".agent-configs"
$agentLinkInfo = Get-Item -Path $agentLink -ErrorAction SilentlyContinue
if ($null -ne $agentLinkInfo -and $agentLinkInfo.Attributes -match "ReparsePoint") {
    Write-Host "  [Skipping] ~/.agent-configs (already a link)"
} elseif (Test-Path $agentLink) {
    Write-Host "  [Warning] ~/.agent-configs exists but is not a symlink; skipping." -ForegroundColor Yellow
} else {
    try {
        New-Item -ItemType SymbolicLink -Path $agentLink -Target $REPO_DIR -ErrorAction Stop | Out-Null
        Write-Host "  [Linking] ~/.agent-configs -> $REPO_DIR (SymbolicLink)" -ForegroundColor Green
    } catch {
        New-Item -ItemType Junction -Path $agentLink -Target $REPO_DIR | Out-Null
        Write-Host "  [Linking] ~/.agent-configs -> $REPO_DIR (Junction Fallback)" -ForegroundColor Yellow
    }
}

# --- Antigravity CLI plugins -------------------------------------------------
# `agy` reads plugins from $HOME\.gemini\antigravity-cli\plugins\<name>\.
# We symlink each .antigravity\plugins\<name> dir into that location so the
# antigravity CLI picks up the same skills + hooks + MCP wiring we maintain
# in this repo, side-by-side with any agy-imported gemini extensions.
function Setup-AntigravityPlugins {
    Write-Host "===> Setting up antigravity plugins..." -ForegroundColor Cyan
    $src_root = Join-Path $REPO_DIR ".antigravity\plugins"
    $dest_root = Join-Path $HOME ".gemini\antigravity-cli\plugins"

    if (-not (Test-Path $src_root)) {
        Write-Host "  [Skipping] no .antigravity\plugins directory in repo"
        return
    }
    if (-not (Test-Path $dest_root)) {
        New-Item -ItemType Directory -Path $dest_root -Force | Out-Null
    }

    # Manifest of plugins this repo manages: name → recognized component list
    $repo_plugins = @{
        "obsidian" = @("skills", "mcpServers", "hooks")
        "general"  = @("skills")
    }

    foreach ($plugin in Get-ChildItem -Path $src_root -Directory) {
        $src = $plugin.FullName
        $dest = Join-Path $dest_root $plugin.Name
        $destInfo = Get-Item -Path $dest -ErrorAction SilentlyContinue

        if ($null -ne $destInfo -and $destInfo.Attributes -match "ReparsePoint") {
            Write-Host "  [Skipping] $($plugin.Name) (already a link)"
            continue
        }
        if (Test-Path $dest) {
            Write-Host "  [Backup] Moving existing $($plugin.Name) to $($plugin.Name)$BACKUP_SUFFIX" -ForegroundColor Yellow
            Rename-Item -Path $dest -NewName ($plugin.Name + $BACKUP_SUFFIX)
        }

        try {
            New-Item -ItemType SymbolicLink -Path $dest -Target $src -ErrorAction Stop | Out-Null
            Write-Host "  [Linking] $($plugin.Name) (SymbolicLink)" -ForegroundColor Green
        } catch {
            New-Item -ItemType Junction -Path $dest -Target $src | Out-Null
            Write-Host "  [Linking] $($plugin.Name) (Junction Fallback)" -ForegroundColor Yellow
        }
    }

    # Register plugins in import_manifest.json so `agy plugin list` sees them
    # and they survive across agy startups. Preserve any pre-existing entries
    # (e.g. real gemini-cli extensions imported via `agy plugin import gemini`).
    $manifest_path = Join-Path $HOME ".gemini\antigravity-cli\import_manifest.json"
    if (Test-Path $manifest_path) {
        $manifest = Get-Content $manifest_path -Raw | ConvertFrom-Json
    } else {
        $manifest = [PSCustomObject]@{ imports = @() }
    }
    if ($null -eq $manifest.imports) {
        $manifest | Add-Member -NotePropertyName imports -NotePropertyValue @() -Force
    }
    $existing = @($manifest.imports | ForEach-Object { $_.name })
    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $updated = $false
    foreach ($name in $repo_plugins.Keys) {
        if ($existing -notcontains $name) {
            $entry = [PSCustomObject]@{
                name        = $name
                source      = "local"
                importedAt  = $now
                components  = $repo_plugins[$name]
            }
            $manifest.imports = @($manifest.imports) + $entry
            Write-Host "  [Registering] $name in import_manifest.json"
            $updated = $true
        }
    }
    if ($updated) {
        $manifest | ConvertTo-Json -Depth 10 | Set-Content $manifest_path -Encoding utf8NoBOM
    }
}
Setup-AntigravityPlugins

# --- bin/ on PATH for the `vault` CLI ---------------------------------------
$binDir = Join-Path $REPO_DIR "bin"
if (Test-Path $binDir) {
    Write-Host "===> Ensuring $binDir is on User PATH..." -ForegroundColor Cyan
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -and ($userPath.Split(';') -contains $binDir)) {
        Write-Host "  [Skipping] $binDir already on User PATH"
    } else {
        $newPath = if ($userPath) { "$binDir;$userPath" } else { $binDir }
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "  [Added] $binDir to User PATH (open a new shell to pick it up)" -ForegroundColor Green
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue) -and `
        -not (Get-Command python3 -ErrorAction SilentlyContinue)) {
        Write-Host "  [Warning] Neither 'py' nor 'python3' found. The vault CLI requires Python 3.8+." -ForegroundColor Yellow
    }
}

# --- Semantic-search dependencies -------------------------------------------
# `vault embed` / vault_semantic_search need the packages in requirements.txt
# (sentence-transformers, numpy). The core vault CLI works without them.
Write-Host "===> Semantic-search dependencies..." -ForegroundColor Cyan
$reqFile = Join-Path $REPO_DIR "requirements.txt"
# Install target follows the cascade venv_bootstrap.py resolves at runtime:
# the repo venv, then the global venv, then the shell's Python.
$pipPy = $null
foreach ($venv in @((Join-Path $REPO_DIR ".venv"), (Join-Path $HOME ".venv"))) {
    $cand = Join-Path $venv "Scripts\python.exe"
    if (Test-Path $cand) { $pipPy = $cand; break }
}
if (-not $pipPy) {
    foreach ($c in @("py", "python3", "python")) {
        if (Get-Command $c -ErrorAction SilentlyContinue) { $pipPy = $c; break }
    }
}
$depsProbe = 'import importlib.util as u,sys; sys.exit(0 if u.find_spec("sentence_transformers") and u.find_spec("numpy") else 1)'
if (-not $pipPy) {
    Write-Host "  [Warning] no Python found - semantic search will be unavailable." -ForegroundColor Yellow
} else {
    & $pipPy -c $depsProbe 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] dependencies already present ($pipPy)" -ForegroundColor Green
    } else {
        Write-Host "  Installing into $pipPy ..."
        & $pipPy -m pip install --quiet -r $reqFile
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] semantic-search dependencies installed" -ForegroundColor Green
        } else {
            Write-Host "  [Warning] install failed - semantic search will be unavailable." -ForegroundColor Yellow
            Write-Host "            Fix your Python setup, then run:" -ForegroundColor Yellow
            Write-Host "              <python> -m pip install -r `"$reqFile`""
            Write-Host "            If the system Python is locked, create a venv at" -ForegroundColor Yellow
            Write-Host "              $REPO_DIR\.venv  (or ~\.venv)  and install there."
        }
    }
}

# --- Write vault-mcp into ~/.gemini/config/mcp_config.json (agy brain/edit mode) ---
# agy brain/edit mode reads MCP config from ~/.gemini/config/, not antigravity-cli/.
# Writing vault-mcp here makes vault tools available without /mcp in the main session.
Write-Host "===> Registering vault-mcp in ~/.gemini/config/mcp_config.json..." -ForegroundColor Cyan
$geminiConfigMcp = Join-Path $HOME ".gemini\config\mcp_config.json"
$vaultMcpScript = 'S="$HOME/.agent-configs/bin/vault-mcp.py"; for P in python3 python py; do command -v "$P" >/dev/null 2>&1 && "$P" -c "" >/dev/null 2>&1 && exec "$P" "$S"; done; echo "vault-mcp: no working python in PATH" >&2; exit 1'
$mcpConfig = $null
if (Test-Path $geminiConfigMcp) {
    $mcpConfig = Get-Content $geminiConfigMcp -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
}
if ($null -eq $mcpConfig) {
    $mcpConfig = [PSCustomObject]@{ mcpServers = [PSCustomObject]@{} }
}
if ($null -eq $mcpConfig.mcpServers) {
    $mcpConfig | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([PSCustomObject]@{}) -Force
}
$existingServers = @($mcpConfig.mcpServers.PSObject.Properties.Name)
if ($existingServers -notcontains "vault-mcp") {
    $entry = [PSCustomObject]@{
        command = "bash"
        args    = @("-c", $vaultMcpScript)
        trust   = $true
    }
    $mcpConfig.mcpServers | Add-Member -NotePropertyName "vault-mcp" -NotePropertyValue $entry -Force
    $dir = Split-Path $geminiConfigMcp
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $mcpConfig | ConvertTo-Json -Depth 10 | Set-Content $geminiConfigMcp -Encoding utf8NoBOM
    Write-Host "  [Written] vault-mcp to $geminiConfigMcp" -ForegroundColor Green
} else {
    Write-Host "  [Skipping] vault-mcp already in $geminiConfigMcp"
}

Write-Host "`nDone! Configuration links established." -ForegroundColor Green

$vaultPath = Join-Path $HOME "obsidian_notes"
if (Test-Path $vaultPath) {
    Write-Host "`n[Vault detected] $vaultPath" -ForegroundColor Green
} else {
    Write-Host "`nNext Step: Setup your Obsidian Vault" -ForegroundColor Cyan
    Write-Host "No vault found at $vaultPath. Choose one of:"
    Write-Host ""
    Write-Host "Option A: Clone an existing vault repo:"
    Write-Host "  git clone <your-repo-url> $vaultPath"
    Write-Host ""
    Write-Host "Option B: Link an existing vault from another location:"
    Write-Host "  New-Item -ItemType Junction -Path `"$vaultPath`" -Target `"<path-to-your-vault>`""
    Write-Host ""
    Write-Host "Option C: Initialize a fresh vault:"
    Write-Host "  .\init-vault.ps1"
}

