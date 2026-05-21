# Agent Configs

A centralized repository for shared configurations, rules, and skills for **Claude Code**, **Antigravity CLI** (`agy`), and **Gemini CLI**.

> Google is transitioning Gemini CLI into Antigravity CLI; Gemini CLI service to AI Pro/Ultra ends June 18, 2026. This repo now wires both side-by-side so the migration is incremental — `.gemini/` continues to serve gemini-cli while `.antigravity/` populates the agy plugin tree.

## Structure

- `.claude/`: Configuration for Claude Code (`~/.claude/`)
- `.antigravity/plugins/`: Plugin packages for Antigravity CLI (`~/.gemini/antigravity-cli/plugins/`)
  - `obsidian/`: vault-related skills + vault-mcp server + hooks
  - `general/`: general behavioral skills (no MCP, no hooks)
- `.gemini/`: Configuration for Gemini CLI (`~/.gemini/`)
  - `rules/`: Custom behavioral rules.
  - `skills/`: Specialized agent skills.
  - `policies/`: Custom security and tool-access policies.
- `hooks/`: Shared shell scripts for session management and vault validation. Referenced by both gemini-cli and antigravity hook configs.
- `setup.*`: Platform-specific setup scripts (Bash or PowerShell) to establish symlinks.
- `init-vault.*`: Scripts to initialize a fresh Obsidian vault.

## Requirements

- **Git:** Required for cloning and version control. **Git Bash** is specifically required on Windows to execute the shell-based hooks.
- **Node.js & npm:** Required for Claude Code installation and hook execution.
- **Python 3.8+:** Required for the vault graph engine and MCP server (`vault` CLI / `vault-mcp`). Semantic search (`vault embed` / `vault_semantic_search`) additionally needs the packages in `requirements.txt` (`sentence-transformers`, `numpy`) — the setup script installs them automatically. The core vault tooling works without them.
- **Obsidian Notes:** The hooks are hardcoded to look for the vault at `~/obsidian_notes` (`C:\Users\<user>\obsidian_notes` on Windows). This folder **must** be placed exactly there for the hooks to function.
- **Permissions:** 
    - **Linux/macOS:** Standard user permissions are sufficient.
    - **Windows:** The `setup.ps1` script will attempt to create Symbolic Links (requires Developer Mode or Admin), but will automatically fall back to **Junctions** and **Hardlinks** for standard users.

## Setup Instructions

### 1. Install the CLIs

Make sure the agents you want to use are installed first. The setup script wires configs but does not install the tools themselves.

**Antigravity CLI (`agy`):**
```bash
# Linux / macOS
curl -fsSL https://antigravity.google/cli/install.sh | bash

# Windows (PowerShell)
irm https://antigravity.google/cli/install.ps1 | iex
```
The Windows installer drops the binary at `%LOCALAPPDATA%\agy\bin\agy.exe` and appends it to the user PATH. Restart your terminal after installing.

**Claude Code** and **Gemini CLI** install per their respective docs (`npm install -g @anthropic/claude-code`, `npm install -g @google/gemini-cli`).

### 2. Link Configurations
Clone this repository into your home directory (or any preferred location) and run the setup script for your environment.

#### Linux / macOS (Bash/Zsh)
```bash
./setup.sh
```

#### Windows (PowerShell)
```powershell
.\setup.ps1
```

The setup script symlinks each `.antigravity/plugins/<name>/` directory into `~/.gemini/antigravity-cli/plugins/<name>/` — `agy` discovers them automatically. Existing agy-imported gemini extensions in the same parent directory are left untouched.

### 3. Initialize or Connect your Vault
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

### Managed Policies
The repository now manages Gemini CLI policies in `.gemini/policies/`. 
- **Plan Mode Override:** By default, Plan Mode restricts the agent to built-in read-only tools. A custom policy (`allow-vault-plan.toml`) is included to permit the use of `vault_*` read tools during the planning phase, allowing for graph-aware context retrieval without exiting Plan Mode. Claude controls this via `settings.json`

### Antigravity CLI plugins

**First-time auth:** agy v1.0.0 requires an interactive login before it will execute prompts (browser-based Google OAuth). Run `agy` once after install, sign in, then `Ctrl+C` to exit. Subsequent invocations (including `-p` print mode) work without prompting.

**Verifying the plugins load:** once signed in, smoke-test with
```bash
agy -p "List the names of all MCP tools available to you, comma-separated."
```
The output should include the five `vault_*` tools (`vault_find`, `vault_semantic_search`, `vault_project`, `vault_show`, `vault_links`). If they're missing, the `obsidian` plugin's `mcp_config.json` isn't being picked up — verify the symlink at `~/.gemini/antigravity-cli/plugins/obsidian` and re-run `agy plugin validate <that path>`.

Each subdirectory under `.antigravity/plugins/` is a self-contained agy plugin. Layout per plugin:

```
.antigravity/plugins/<name>/
├── plugin.json           # { "name": "<name>" } — required manifest
├── mcp_config.json       # optional; { "mcpServers": { ... } }
├── hooks/hooks.json      # optional; event → command bindings
└── skills/<skill>/SKILL.md
```

Two plugins ship in this repo:
- **`obsidian`** — `vault-mcp` server + obsidian-notes / obsidian-audit / project-archaeology / checkpoint / obsidian-vault-rules skills + all session/post-tool hooks
- **`general`** — architect-interview + behavioral-guidelines skills (no MCP, no hooks)

**Hook event mapping (Antigravity CLI v1.0.0):**

Confirmed event names per the `/hooks` panel in agy v1.0.0: `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`. Mapping in `.antigravity/plugins/obsidian/hooks/hooks.json`:
- Gemini `SessionStart` → agy `PreInvocation` *(fires before every LLM invocation, not once per session — `session-start.sh` should be idempotent or self-throttle)*
- Gemini `AfterTool` with matchers `write_file` / `replace` → agy `PostToolUse` with matchers `Write` / `Edit`
- Gemini `SessionEnd` → agy `Stop`
- Gemini `PreCompress` → **no direct analog.** Run `bash ~/agent-configs/hooks/pre-compact.sh` manually before `/compact` if needed.

If a hook isn't firing after migration, double-check the event name against `/hooks` in your agy session, then re-validate with `agy plugin validate ~/.gemini/antigravity-cli/plugins/obsidian`.

**Skill duplication during migration:** The vault skills currently exist in both `.gemini/skills/` and `.antigravity/plugins/obsidian/skills/` so Gemini CLI keeps working through its sunset date. When `.gemini/` is retired, the antigravity copy becomes the single source of truth.

## Synchronization (Automation)

To keep your vault synced across machines, set up an automated task to run the synchronization script. These scripts automatically handle merge conflicts by favoring local changes (`-X ours`).

### 1. Add Automated Task

#### Linux / macOS (Cron)
Run `crontab -e` and add the following line to sync every 5 minutes:

```bash
*/5 * * * * $HOME/agent-configs/hooks/server-sync.sh > /dev/null 2>&1
```

#### Windows Task Scheduler (Silent Sync)
To prevent a PowerShell window from flashing every 5 minutes, use the provided VBScript wrapper.

1. **Verify the wrapper exists:** Ensure `agent-configs/hooks/silent-sync.vbs` is present.
2. **Create or Update the Task:** Run the following command in an administrator terminal:

```powershell
schtasks /create /sc minute /mo 5 /tn "sync obsidian" /tr "wscript.exe %USERPROFILE%\agent-configs\hooks\silent-sync.vbs" /it /f
```


- **Program/script:** `wscript.exe`
- **Add arguments:** `"%USERPROFILE%\agent-configs\hooks\silent-sync.vbs"`
- **Settings (Critical):**
    - **General:** Select "Run only when user is logged on" (required for Git credential access).
    - **Settings:** Enable "Stop the task if it runs longer than" (set to **2 minutes** via `/k` in the command above).
    - **Settings:** Enable "If the running task does not end when requested, force it to stop."


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

