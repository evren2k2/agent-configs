# Agent Configs

A centralized repository for shared configurations, rules, and skills for **Claude Code** and **Gemini CLI**.

## Structure

- `.claude/`: Configuration for Claude Code (`~/.claude/`)
- `.gemini/`: Configuration for Gemini CLI (`~/.gemini/`)
- `hooks/`: Shared shell scripts for session management and vault validation.
- `setup.*`: Platform-specific setup scripts (Bash or PowerShell) to establish symlinks.
- `init-vault.*`: Scripts to initialize a fresh Obsidian vault.

## Requirements

- **Git:** Required for cloning and version control. **Git Bash** is specifically required on Windows to execute the shell-based hooks.
- **Node.js & npm:** Required for Claude Code installation and hook execution.
- **Obsidian Notes:** The hooks are hardcoded to look for the vault at `~/obsidian_notes` (`C:\Users\<user>\obsidian_notes` on Windows). This folder **must** be placed exactly there for the hooks to function.
- **Permissions:** 
    - **Linux/macOS:** Standard user permissions are sufficient.
    - **Windows:** The `setup.ps1` script will attempt to create Symbolic Links (requires Developer Mode or Admin), but will automatically fall back to **Junctions** and **Hardlinks** for standard users.

## Setup Instructions

### 1. Link Configurations
Clone this repository into your home directory (or any preferred location) and run the setup script for your environment.

#### Linux / macOS (Bash/Zsh)
```bash
./setup.sh
```

#### Windows (PowerShell)
```powershell
.\setup.ps1
```

### 2. Initialize or Connect your Vault
The configurations expect an Obsidian vault at `~/obsidian_notes`. 

#### If you already have a vault repo:
```bash
git clone <your-vault-url> ~/obsidian_notes
```

#### If you want to start a fresh vault:
Run the initialization script which creates the required directory structure (`areas/`, `agent/`, etc.) and initializes a local Git repository.

**Windows (PowerShell):**
```powershell
.\init-vault.ps1
```

**Linux / macOS (Bash):**
```bash
./init-vault.sh
```

Follow the post-initialization instructions to link it to a private GitHub repository.

## Features

### Centralized Hooks
Hooks are now managed within this repository in the `hooks/` directory, making it easier to update logic across all agent configurations. These hooks handle:
- **Session Lifecycle:** Context loading and cleanup.
- **Compaction Safety:** State persistence before context compression.
- **Validation:** Vault integrity checks after file edits.

## Synchronization (Automation)

To keep your vault synced across machines, set up an automated task to run the synchronization script. These scripts automatically handle merge conflicts by favoring local changes (`-X ours`).

### 1. Add Automated Task

#### Linux / macOS (Cron)
Run `crontab -e` and add the following line to sync every 5 minutes:

```bash
*/5 * * * * $HOME/agent-configs/hooks/server-sync.sh > /dev/null 2>&1
```

#### Windows (Task Scheduler)
Create a new task in **Task Scheduler** to run every 5 minutes:
- **Action:** Start a program
- **Program/script:** `powershell.exe`
- **Add arguments:** `-NoProfile -WindowStyle Hidden -File "$HOME\agent-configs\hooks\server-sync.ps1"`

### 2. Manual Sync
If you need to sync immediately, you can run:

**Bash:**
```bash
$HOME/agent-configs/hooks/server-sync.sh
```

**PowerShell:**
```powershell
.\hooks\server-sync.ps1
```

## Note Conventions

When working with the vault, follow these conventions to ensure agent compatibility:

- **Filenames:** Use `lowercase-hyphenated.md`.
- **Structure:**
    - `projects/<name>/working-context.md`: Critical for session recovery and project tracking.
    - `areas/`: Long-term knowledge storage.
- **Git Integration:** If a folder in your home directory matches a project name in `projects/`, the `pre-compact` hook will automatically snapshot that repository's state into your vault.

