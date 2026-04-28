# Agent Configs

A centralized repository for shared configurations, rules, and skills for **Claude Code** and **Gemini CLI**.

## Structure

- `.claude/`: Configuration for Claude Code (`~/.claude/`)
- `.gemini/`: Configuration for Gemini CLI (`~/.gemini/`)
- `setup.*`: Platform-specific setup scripts to establish symlinks.

## Setup Instructions

Clone this repository into your home directory (or any preferred location) and run the setup script for your environment.

### Linux / macOS (Bash/Zsh)
```bash
./setup.sh
```

### Linux (TCSH)
```tcsh
./setup.csh
```

### Hook Dependencies (Obsidian Notes)
The configuration relies on external hooks provided by the `obsidian_notes` repository. This repository must be cloned in parallel to your home directory:

```bash
git clone git@github.com:evren2k2/obsidian_notes.git ~/obsidian_notes
```

These hooks handle:
- **Session Lifecycle:** `session-start.sh` and `session-stop.sh` for context loading/cleanup.
- **Compaction Safety:** `pre-compact.sh` to ensure vault state is persisted before context compression.
- **Validation:** `validate-vault-write.sh`, `detect-stale-notes.sh`, and `update-timeline.sh` to maintain vault integrity after file edits.

### Windows (PowerShell)
*Run in an elevated PowerShell terminal or ensure Developer Mode is enabled.*
```powershell
.\setup.ps1
```

## Features

### Separated Settings
To prevent hook compatibility warnings, each agent has its own `settings.json`:
- **Claude:** Uses `PreCompact` and `PostToolUse` hooks.
- **Gemini:** Uses `PreCompress` and `AfterTool` hooks.

### Shared Logic
While settings are separated, you can still share `rules` and `skills` by copying or linking them between the `.claude/` and `.gemini/` directories in this repo.

## Security
The repository includes a `.gitignore` that prevents the following from being tracked:
- Credentials (`.credentials.json`, `oauth_creds.json`, etc.)
- Session history and cache.
- Local project-specific transient data.

**Always verify you are not committing secrets before pushing.**
