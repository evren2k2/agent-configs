# Agent Configs

A centralized repository for shared configurations, rules, and skills for **Claude Code** and **Antigravity CLI** (`agy`).

> Gemini CLI support was retired after Google deprecated it (service to AI Pro/Ultra ended June 18, 2026). `.antigravity/` is now the single Google-side config tree; `agy` still lives under `~/.gemini/`, so paths like `~/.gemini/antigravity-cli/` and `~/.gemini/config/mcp_config.json` below refer to agy, not gemini-cli.

## Structure

- `.claude/`: Configuration for Claude Code (`~/.claude/`)
- `.antigravity/plugins/`: Plugin packages for Antigravity CLI (`~/.gemini/antigravity-cli/plugins/`)
  - `obsidian/`: vault-related skills + vault-mcp server + hooks
  - `general/`: general behavioral skills (no MCP, no hooks)
- `hooks/`: Shared shell scripts for session management and vault validation. Referenced by the Claude Code and antigravity hook configs.
- `santa-method.json.example`: Template reviewer config for the optional `santa-method` skill; copy to the gitignored, machine-local `santa-method.json` to activate — see [Santa Method](#santa-method-optional-adversarial-review).
- `bin/`: the `vault` CLI, the `vault-mcp` server (launched via `vault-mcp-launcher.sh` / `.cmd`), and **`agentcfg`** — the cross-platform installer (`install` / `update` / `uninstall` / `status` / `init-vault`).
- `setup-graphify.py`: optional, independent installer for the graphify code-knowledge-graph integration (Claude-only, separate from the vault install).

## Requirements

- **Git:** Required for cloning and version control. **Git Bash** is specifically required on Windows to execute the shell-based hooks.
- **Node.js & npm:** Required for Claude Code installation and hook execution.
- **Python 3.8+:** Required for the vault graph engine and MCP server (`vault` CLI / `vault-mcp`). Semantic search (`vault embed` / `vault_semantic_search`) additionally needs the packages in `requirements.txt` (`sentence-transformers`, `numpy`) — `agentcfg install` installs them automatically. The core vault tooling works without them.
- **Obsidian Notes:** The hooks are hardcoded to look for the vault at `~/obsidian_notes` (`C:\Users\<user>\obsidian_notes` on Windows). This folder **must** be placed exactly there for the hooks to function.
- **Permissions:** 
    - **Linux/macOS:** Standard user permissions are sufficient.
    - **Windows:** `agentcfg` creates Symbolic Links (requires Developer Mode or Admin); without those it automatically falls back to **copies** (re-run `agentcfg update` after editing repo files to re-sync).

## Setup Instructions

### 1. Install the CLIs

Make sure the agents you want to use are installed first. `agentcfg` wires configs but does not install the tools themselves.

**Antigravity CLI (`agy`):**
```bash
# Linux / macOS
curl -fsSL https://antigravity.google/cli/install.sh | bash

# Windows (PowerShell)
irm https://antigravity.google/cli/install.ps1 | iex
```
The Windows installer drops the binary at `%LOCALAPPDATA%\agy\bin\agy.exe` and appends it to the user PATH. Restart your terminal after installing.

**Claude Code** installs per its docs (`npm install -g @anthropic/claude-code`).

### 2. Link Configurations
Clone this repository into your home directory (or any preferred location), then run the installer — a single cross-platform Python tool (`bin/agentcfg`) that replaces the old `setup.sh`/`setup.ps1`:

```bash
python3 bin/agentcfg install --apply     # omit --apply for a dry-run preview
```

It is **non-destructive**: it merges a marked block into an existing `CLAUDE.md` and deep-merges keys into `settings.json` (never overwriting your own config), and drops per-skill symlinks (copies on locked-down Windows) into your config dirs. Manage it anytime:

```bash
agentcfg status               # what's installed / drifted
agentcfg update --apply       # re-sync after editing repo CLAUDE.md / settings.json
agentcfg uninstall --apply    # cleanly remove everything (restores backups)
```

`agentcfg` symlinks (or copies) each `.antigravity/plugins/<name>/` directory into `~/.gemini/antigravity-cli/plugins/<name>/` — `agy` discovers them automatically. Existing agy-imported gemini extensions in the same parent directory are left untouched.

### 3. Initialize or Connect your Vault
The configurations expect an Obsidian vault at `~/obsidian_notes`. 

#### If you already have a vault repo:
```bash
git clone <your-vault-url> ~/obsidian_notes
```

#### If you want to start a fresh vault:
Create the required directory structure (`areas/`, `agent/`, etc.) and a local Git repo with:
```bash
python3 bin/agentcfg init-vault --apply     # omit --apply for a dry-run preview
```
Then follow the printed instructions to link it to a private GitHub repository.

## Features

### Centralized Hooks
Hooks are now managed within this repository in the `hooks/` directory, making it easier to update logic across all agent configurations. These hooks handle:
- **Session Lifecycle:** Context loading and cleanup.
- **Compaction Safety:** State persistence before context compression (manual compacts only; automatic ones are skipped).
- **Validation:** Vault integrity checks after file edits, surfaced back to the model as hook feedback (`additionalContext`), not just logged.

### Santa Method (optional adversarial review)

`santa-method` is a skill (mirrored across Claude and Antigravity) that gates high-stakes output — pre-tapeout RTL, verification infra, production scripts — behind two independent reviewers that must both PASS before shipping.

It is **off by default**: `santa-method.json` is gitignored and absent on a fresh clone, so `session-start.sh` emits nothing about santa and the skill stays dormant. To activate it on a machine, copy the tracked template — **`santa-method.json.example`** — to **`santa-method.json`**, then trim it to the reviewer CLIs you actually have installed + authed:

```bash
cp santa-method.json.example santa-method.json
```

The skill substitutes `{focus}` (the review angle) and `{files}` (target paths) into each `command`. Subscription CLIs work without API keys; the template ships two divergent reviewers (`agy`, `claude`), e.g.:

```json
{ "reviewers": [
  { "name": "agy",
    "command": "agy --print-timeout 20m -p \"Adversarial review — {focus}. Target files: {files}. Static analysis only. End with exactly one line: VERDICT: PASS or VERDICT: FAIL.\"" }
] }
```

The `agy --print-timeout 20m` is deliberate — agy's `-p` print mode defaults to a 5-minute timeout and will otherwise cut a long review off before the final `VERDICT:` line (the response comes back truncated, with no verdict). Don't drop that flag. See the *Truncated / incomplete runs* section in any agent's `santa-method` SKILL.md for the full failure mode.

(`claude -p --model <model-you-have> "..."` and codex's `adversarial-review` channel work the same way — see any agent's `santa-method` SKILL.md for the codex example and the full method: two divergent angles, both-PASS gate, ≤3 iterations.)

### Antigravity CLI plugins

**First-time auth:** agy v1.0.0 requires an interactive login before it will execute prompts (browser-based Google OAuth). Run `agy` once after install, sign in, then `Ctrl+C` to exit. Subsequent invocations (including `-p` print mode) work without prompting.

**Verifying the plugins load:** once signed in, smoke-test with
```bash
agy -p "List the names of all MCP tools available to you, comma-separated."
```
The output should include the five `vault_*` tools (`vault_find`, `vault_semantic_search`, `vault_project`, `vault_show`, `vault_links`). If they're missing, the `obsidian` plugin's `mcp_config.json` isn't being picked up — verify the link (or copy, on Windows) at `~/.gemini/antigravity-cli/plugins/obsidian` and re-run `agy plugin validate <that path>`.

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
- **`general`** — architect-interview + behavioral-guidelines + paper-outline + santa-method skills (no MCP, no hooks)

**Hook events (Antigravity CLI v1.0.0):**

Confirmed event names per the `/hooks` panel in agy v1.0.0: `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`. Bindings in `.antigravity/plugins/obsidian/hooks/hooks.json`:
- `PreInvocation` → `session-start.sh` *(fires before every LLM invocation, not once per session — the script must stay idempotent / self-throttling)*
- `PostToolUse` with matchers `Write` / `Edit` → vault validators
- `Stop` → `session-stop.sh`
- Pre-compaction has **no agy event.** Run `bash ~/.agent-configs/hooks/pre-compact.sh` manually before `/compact` if needed.

If a hook isn't firing, double-check the event name against `/hooks` in your agy session, then re-validate with `agy plugin validate ~/.gemini/antigravity-cli/plugins/obsidian`.

**Single source of truth:** with gemini-cli retired, `.antigravity/plugins/obsidian/skills/` is the only Google-side copy of the vault skills (Claude's copies live in `.claude/skills/`).

## Synchronization (Automation)

To keep your vault synced across machines, set up an automated task to run the synchronization script. These scripts automatically handle merge conflicts by favoring local changes (`-X ours`).

### 1. Add Automated Task

#### Linux / macOS (Cron)
Run `crontab -e` and add the following line to sync every 5 minutes:

```bash
*/5 * * * * $HOME/.agent-configs/hooks/server-sync.sh > /dev/null 2>&1
```

(`~/.agent-configs` is the namespace link `agentcfg install` creates, so this works regardless of where the repo is cloned. Overlapping runs are prevented with `flock`, and `sync.log` is rotated automatically.)

#### Windows Task Scheduler (Silent Sync)
To prevent a PowerShell window from flashing every 5 minutes, use the provided VBScript wrapper.

1. **Verify the wrapper exists:** Ensure `agent-configs/hooks/silent-sync.vbs` is present.
2. **Create or Update the Task:** Run the following command in an administrator terminal:

```powershell
schtasks /create /sc minute /mo 5 /tn "sync obsidian" /tr "wscript.exe %USERPROFILE%\.agent-configs\hooks\silent-sync.vbs" /it /f
```


- **Program/script:** `wscript.exe`
- **Add arguments:** `"%USERPROFILE%\.agent-configs\hooks\silent-sync.vbs"`
- **Settings (Critical):**
    - **General:** Select "Run only when user is logged on" (required for Git credential access).
    - **Settings:** Enable "Stop the task if it runs longer than" (set to **2 minutes** via `/k` in the command above).
    - **Settings:** Enable "If the running task does not end when requested, force it to stop."


### 2. Manual Sync
If you need to sync immediately, you can run:

**Bash:**
```bash
$HOME/.agent-configs/hooks/server-sync.sh
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
- **Git Integration:** On manual compaction, the `pre-compact` hook snapshots the git state of the current working directory and the vault itself into `agent/pre-compact-snapshot.md` (scan deliberately bounded to stay within the hook timeout).

