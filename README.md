# Agent Configs

One instruction stack for two coding agents — **Claude Code** and **Antigravity CLI** (`agy`) — plus the tooling that gives them a shared long-term memory: an Obsidian vault the agents read at session start and write to as they work, checkpoints that carry your intent across sessions, a queue for the corrections you make to how the agent works, and optional adversarial review and code-graph navigation.

Everything here is installed by one command and kept in sync with the repo by symlinks, so editing a rule or a skill in this checkout changes every agent immediately.

## What you get

| Piece | What it does | Where |
|---|---|---|
| **Vault memory** | Six MCP tools (`vault_find`, `vault_semantic_search`, `vault_project`, `vault_show`, `vault_links`, `vault_checkpoint`) over `~/obsidian_notes`, served to both agents by one `vault-mcp` server. | `bin/vault-mcp.py`, `bin/vault.py` |
| **Checkpoints** | A per-project circular buffer of "briefings for the next agent" with a verbatim **User Intent ledger** carried forward on every write; a reader that flags a dropped ledger; a hook that repairs hand-edited files. | `bin/checkpoint.py`, `.claude/skills/checkpoint/` |
| **Dispositions** | A capped queue of "how to work" rules learned from your corrections, scoped **per project** by default, promoted into always-loaded files only after recurring and only with your approval. | `bin/instincts.py`, `~/obsidian_notes/agent/instincts.yaml` |
| **Rules & skills** | Behavioral guidelines, vault rules, and task skills (`checkpoint`, `obsidian-notes`, `obsidian-audit`, `project-archaeology`, `compose-docs`, `architect-interview`, `paper-outline`, `paper-draft`, `isscc-figure`, `santa-method`, `graphify`). Mirrored for both agents; a test fails if they drift. | `.claude/`, `.antigravity/plugins/` |
| **Hooks** | Session start (project + working mode + checkpoint pointer), vault-write validation, checkpoint repair, pre-compact snapshot, end-of-turn knowledge/disposition check. | `hooks/` |
| **Santa Method** (optional) | Two independent reviewers must both PASS before high-stakes output ships. Off until you configure a reviewer. | `santa-method.json.example` |
| **graphify** (optional) | Code knowledge graph with `query` / `path` / `explain`, as a skill and an MCP server for both agents. | `setup-graphify.py`, `.antigravity/plugins/graphify/` |

## Install

**Requirements.** Git (Git Bash on Windows — the hooks are shell scripts), Node.js for Claude Code, Python 3.8+ for the vault tools. Semantic search needs `requirements.txt` (`sentence-transformers`, `numpy`); `agentcfg install` installs them, and the rest works without them. The vault must live at `~/obsidian_notes` (`C:\Users\<user>\obsidian_notes`). On Windows, `agentcfg` makes symlinks when it can (Developer Mode or admin) and falls back to copies otherwise — re-run `agentcfg update` after editing the repo in that case.

**1. Install the agents you use.** `npm install -g @anthropic/claude-code` and/or `curl -fsSL https://antigravity.google/cli/install.sh | bash` (`irm https://antigravity.google/cli/install.ps1 | iex` on Windows; the binary lands at `%LOCALAPPDATA%\agy\bin\agy.exe`). Run `agy` once to complete the browser sign-in before using it in print mode.

**2. Clone and link.**

```bash
git clone <this-repo> ~/agent-configs
python3 ~/agent-configs/bin/agentcfg install --apply     # omit --apply for a dry run
```

`agentcfg` is non-destructive: it merges a marked block into `~/.claude/CLAUDE.md`, deep-merges its keys into `~/.claude/settings.json` (backing up yours), drops per-item symlinks into `~/.claude/{rules,skills}`, links each `.antigravity/plugins/<name>/` where `agy` discovers plugins and runs `agy plugin install` on it, registers the `vault-mcp` server with both agents, and links the repo at `~/.agent-configs` so hooks and scripts have a fixed path. Later:

```bash
agentcfg status               # what is installed, what drifted
agentcfg update --apply       # re-sync after editing instructions.md / settings.json
agentcfg uninstall --apply    # remove everything, restore backups
```

**3. Vault.** Either `git clone <your-vault-url> ~/obsidian_notes`, or start fresh with `python3 bin/agentcfg init-vault --apply` and follow the printed steps to attach a private remote.

**4. Optional: graphify.** `python3 setup-graphify.py` creates `~/.graphify-venv`, puts `graphify` and `graphify-mcp` on your PATH, and installs the agy plugin. Then `python3 setup-graphify.py /path/to/project` registers it for Claude in that project (skill, `CLAUDE.md` section, hooks, `.mcp.json`). Build a graph with `graphify extract .` or the in-session `/graphify` skill; the agy side needs no per-project step because its MCP server resolves `graphify-out/graph.json` relative to where you launch `agy`. The venv is installed once and never upgraded on its own, so the version is effectively pinned; `python3 setup-graphify.py --upgrade` moves the package and both skill copies (Claude and agy) together and prints what to re-run afterwards. Review the skill diff before committing, since it lands in every session.

**5. Optional: Santa Method.** `cp santa-method.json.example santa-method.json` and trim it to the reviewer CLIs you have. See [Reviews](#reviews-santa-method) below.

**6. Optional: sync.** A cron job or scheduled task that commits and pushes the vault every five minutes — see [Keeping the vault in sync](#keeping-the-vault-in-sync).

## Using it day to day

The patterns below are generalized from real sessions. None of them need special commands; they are things you say to the agent, and the stack makes them work.

### Start a session by pointing at the memory

> *"Please read the most recent vault checkpoint and get situated with the necessary files, then let's discuss next steps."*

At session start the hook has already told the agent which vault project matches the working directory, how to read the last checkpoint (`vault_checkpoint`, with a Bash fallback), and — if the project has one — its **working mode**: your standing rulings on how that project is run, printed verbatim because they bind before the first action. The agent then enumerates the project's notes with `vault_project`, reads the direction notes and the checkpoint itself, and only pulls implementation detail the task needs. The read policy is three tiers (read it yourself; read a line range of a big note; delegate breadth only, with verbatim quotes back), and it forbids paraphrasing a number, path or error string the agent could have read.

### Discuss first, then build

> *"Let's discuss and settle the open questions first and modify the plan accordingly; then we will address the plan."*

The agent proposes a plan with its tradeoffs; you decide. Anything that sets or records **direction** — goals, scope calls, decisions, working mode — is written to the vault only after you approve it. Implementation findings the agent discovers while working are written autonomously but only when they are need-to-know. Notes the agent thinks are direction but you have not ratified stay proposals.

### Checkpoint before the context gets heavy

> *"Can you update the checkpoint? This is a close to ideal state for a new session."* — or just `/checkpoint`.

A checkpoint is a briefing for the next agent, not a status report. Its first section is the **User Intent ledger**: a numbered, verbatim record of everything you asked for and every correction you made, carried forward into every new checkpoint so the newest entry is always self-sufficient. The agent writes it with one call:

```bash
cat <<'EOF' | python3 ~/.agent-configs/bin/checkpoint.py write --project <project>
## Checkpoint — 2026-09-21 16:00 (topic)
### User Intent
<new items only — the previous ledger is spliced in automatically>
...
EOF
```

That one call carries the ledger, inserts the record separator, trims to the last five, and appends a digest to the project's append-only `timeline.md`. Never let the agent append to `working-context.md` by hand: an entry written that way lost the ledger in a real session, and the next session acted without your instructions. Two defences now cover that path: `vault_checkpoint` prints a **LEDGER GAP** banner with the dropped items when the newest entry did not carry them, and a hook on the shell tool runs `checkpoint.py repair` whenever a command touches a `working-context.md`.

### When you correct the agent, the correction is kept

> *"When I said the hook looks good, I meant your proposal for the hook modification looked good."*
> *"The outline is NOT the hard truth for what needs to be done; I am."*

Corrections like these are **dispositions**: how to work, not what is true about a system. At the end of a turn that wrote to the vault, the Stop hook asks the agent where it was corrected and has it queue a one-line rule with your words as provenance:

```bash
python3 ~/.agent-configs/bin/instincts.py propose --disposition '<rule>' --origin '<your words>' --project <p> [--scope global]
python3 ~/.agent-configs/bin/instincts.py list            # what is queued, with scope
```

`propose` holds a new rule until the agent has seen the queue: if a queued rule states the same principle with a different example, the agent records a re-trigger with `seen --match` instead, and only a genuinely new principle is queued (`--new`). Rules are worded at the level of the principle, with the incident in the origin, so the next instance matches.

Dispositions are **project-scoped by default**, because projects differ in method: a rule about who writes verification on one project should not govern a paper-writing project. A queued rule does nothing until it recurs in a later session **and** you approve its promotion:

```bash
python3 ~/.agent-configs/bin/instincts.py promote --match '<text>'            # dry run: shows the block and the target
python3 ~/.agent-configs/bin/instincts.py promote --match '<text>' --apply    # after your approval
```

Promotion routes on scope. A project rule lands in `projects/<p>/decisions/working-mode.md` in the vault, which the session-start hook prints for that project. A global rule (`--scope global`, or overridden at promotion) lands in `agent/learned-dispositions.md` in the vault, which the same hook prints in every session of every project, for Claude and agy alike. The signal that a project rule is really global is the same rule being proposed from a second project; `propose` records that and says so. The queue is capped at 15 and a rule that never recurs expires, so the always-on budget cannot grow unbounded.

### Knowledge goes in the vault, in the right class

What the agent learns about a system — a non-obvious constraint, a weakness, something that will clash with future work — is a vault note, retrieved on demand. The vault rules classify notes so a fresh agent reads intent before detail:

| Read first | `projects/<p>/decisions/` (direction, constraints, working mode), `projects/<p>/vocabulary.md` if the project needs one |
| Read on demand | `projects/<p>/implementation/` (how it works), `findings/` (what the data showed, with provenance), `operational.md` (how to run it) |
| Durable, cross-project | `areas/` (promoted when a second project needs it), `library/` (reference) |

Every note has YAML frontmatter (`date`, `tags`, `type`, `status`, `project`), a lowercase-hyphenated filename, and at least one `[[wikilink]]`; a hook validates each write and tells the agent what to fix.

### Reviews: Santa Method

For output that ships without a human reading every line — pre-tapeout RTL, verification infrastructure, production scripts — the `santa-method` skill runs two independent reviewers with different angles and requires both to end with `VERDICT: PASS`. It is off until `santa-method.json` exists. The template ships `agy` and `claude` as reviewers; keep `agy --print-timeout 20m`, since agy's print mode otherwise cuts a long review off before its verdict line. Subscription CLIs work without API keys. A project's working mode can turn santa off for that project; the working-mode block printed at session start overrides the generic hook line.

### Codebase questions: graphify

With a graph built, both agents are told to run `graphify query "<question>"` before grepping, `graphify path "A" "B"` for relationships, and `graphify explain "X"` for one concept, and to run `graphify update .` after changing code. The same tools are exposed over MCP (`query_graph`, `shortest_path`, `get_node`, ...) to Claude per project and to agy globally.

## Repository layout

```
.claude/
  instructions.md        global instructions, merged into ~/.claude/CLAUDE.md (named this way so the
                         repo's own CLAUDE.md is not injected twice when the CWD is this repo)
  rules/                 behavioral-guidelines.md, obsidian-notes.md
  skills/                one directory per skill
  settings.json          hooks + permissions, deep-merged into ~/.claude/settings.json
.antigravity/plugins/
  obsidian/              vault skills, vault-mcp server, all session/post-tool hooks
  general/               task skills with no MCP or hooks
  graphify/              graphify skill + references + graphify MCP server
bin/                     agentcfg (installer), vault.py / vault-mcp.py, checkpoint.py, instincts.py, vault_embed.py
hooks/                   shell scripts referenced by both agents' hook configs, plus the vault sync scripts
tests/                   unit tests for every script and a regression suite for the instruction stack
setup-graphify.py        standalone graphify installer (venv, PATH, Claude per-project, agy plugin)
santa-method.json.example
```

## Claude Code vs. Antigravity CLI

The content is one stack; the delivery differs.

- **Claude Code** reads `~/.claude/CLAUDE.md`, `~/.claude/rules/*.md` and `~/.claude/skills/*/SKILL.md`, and fires hooks from `~/.claude/settings.json`. Rules are always in context.
- **agy** loads plugins from `~/.gemini/antigravity-cli/plugins/<name>/` (`plugin.json`, optional `mcp_config.json`, `hooks/hooks.json`, `skills/<skill>/SKILL.md`). It has no always-loaded rules file, so the rules ship as skills (`behavioral-guidelines`, `obsidian-vault-rules`) and are loaded on demand. Hook events confirmed in agy 1.x: `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`. `PreInvocation` runs `session-start.sh` before every model call, so that script stays idempotent. There is no pre-compaction event; run `bash ~/.agent-configs/hooks/pre-compact.sh` yourself before `/compact` if you want the snapshot.
- **Verify agy** sees everything: `agy -p "List the names of all MCP tools available to you, comma-separated."` should return the six `vault_*` tools and, with graphify installed, `query_graph`, `shortest_path`, `get_node` and friends. If not, `agy plugin validate ~/.gemini/antigravity-cli/plugins/<name>` and `agy plugin list` show what loaded.
- Gemini CLI support was retired when Google ended the service; `~/.gemini/` paths in this repo refer to agy's own config, not gemini-cli.

## Keeping the vault in sync

`hooks/server-sync.sh` (and `server-sync.ps1`) commit and push the vault, resolving conflicts in favour of local changes, with `flock` against overlapping runs and log rotation.

```bash
# Linux / macOS: crontab -e
*/5 * * * * $HOME/.agent-configs/hooks/server-sync.sh > /dev/null 2>&1
```

```powershell
# Windows, from an administrator terminal (the VBScript wrapper keeps the window hidden)
schtasks /create /sc minute /mo 5 /tn "sync obsidian" /tr "wscript.exe %USERPROFILE%\.agent-configs\hooks\silent-sync.vbs" /it /f
```

In Task Scheduler choose "Run only when user is logged on" (Git credentials need the session), stop the task if it runs longer than two minutes, and force-stop if it does not end. Run the script directly for an immediate sync.

## Tests

```bash
python3 -m unittest discover tests -v
```

`test_checkpoint`, `test_instincts`, `test_vault`, `test_vault_mcp`, `test_embed` and `test_agentcfg` cover the scripts. `test_instruction_stack` guards what lives in prose and config: no double-injected instructions, the three-tier read policy, qualified MCP tool ids, byte-identical Claude/agy skill mirrors (including graphify's references), the checkpoint ledger defences, and scoped dispositions. Run it after editing anything under `.claude/` or `.antigravity/`.
