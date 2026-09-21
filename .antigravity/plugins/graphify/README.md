# graphify plugin (agy)

The same graphify skill Claude Code gets from `.claude/skills/graphify/`, packaged as an
Antigravity CLI plugin so `agy` is not left out: `skills/graphify/` is a byte-identical
copy (guarded by `tests/test_instruction_stack.py`), and `mcp_config.json` registers the
`graphify-mcp` server with the graph path relative to the working directory — agy MCP
servers are global, so the server follows whichever project you launch `agy` in, exactly
like Claude's per-project `.mcp.json` entry does.

Installed by `python3 setup-graphify.py` (or by `agentcfg install`, which links every
plugin under `.antigravity/plugins/`). Build the graph per project with `graphify extract .`
or the in-session `/graphify` skill; without `graphify-out/graph.json` the MCP server has
nothing to serve and the skill falls back to building one.
