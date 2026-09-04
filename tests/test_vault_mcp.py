"""Live end-to-end tests for the vault-mcp server — does the checkpoint READ path
actually work when driven the way an agent drives it?

tests/test_instruction_stack.py asserts the wiring exists in the source. This file
asserts it *runs*: a real subprocess, real JSON-RPC over stdio, a real temp vault.
The gap between the two is where the reported failure lived — every static check
passed while an agent still could not read a checkpoint.

Covered here:
  - the server answers `initialize` as `vault-mcp`, which is what makes the tool id
    the instruction stack advertises (`mcp__vault-mcp__vault_checkpoint`) correct
  - all six tools are listed, checkpoint included
  - vault_checkpoint returns entry bodies VERBATIM (byte-for-byte, no summarizing)
  - n / headers behave as the skill documents them
  - the absent cases return a sentence, not a crash or an empty string
  - the read short-circuits before the index build (no cache is written)
  - the documented Bash fallback produces the same entries as the tool

Run from repo root:
    py -3 -m unittest tests.test_vault_mcp -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "bin/vault-mcp.py"
CHECKPOINT_PY = REPO / "bin/checkpoint.py"

EXPECTED_TOOLS = {
    "vault_find", "vault_project", "vault_show",
    "vault_links", "vault_semantic_search", "vault_checkpoint",
}

# The server name half of the tool id the instruction stack tells agents to call.
SERVER_NAME = "vault-mcp"

PREAMBLE = textwrap.dedent("""\
    ---
    date: 2026-01-01
    tags: [demo]
    type: mission
    status: active
    project: demo
    ---

    # demo — Working Context

    ## Mission
    Hand-maintained prose. Mentions ---CHECKPOINT--- inline on purpose.
    """)

# Load-bearing detail — a path, a flag and an error string. If a read path ever
# starts summarizing, these are the first things to go.
OLDER = textwrap.dedent("""\
    ## Checkpoint — 2026-02-01 10:00 (older)

    ### Current Goal
    wire vault_checkpoint into bin/vault-mcp.py:289

    ### Open / Blocked
    - [ ] `--no-timeline` still snapshots""").strip()

NEWER = textwrap.dedent("""\
    ## Checkpoint — 2026-02-02 11:00 (newer)

    ### Current Goal
    reproduce "Tool not found: vault_checkpoint"

    ### Active Files
    - hooks/session-start.sh""").strip()


class VaultMCPCase(unittest.TestCase):
    """A throwaway vault plus a throwaway cache, so nothing here touches the real one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        self.cache = Path(self.tmp.name) / "cache"
        (self.vault / "projects/demo").mkdir(parents=True)
        self.cache.mkdir()
        self.ctx = self.vault / "projects/demo/working-context.md"
        self.write_context([OLDER, NEWER])

    def write_context(self, entries):
        body = PREAMBLE
        for e in entries:
            body += f"\n---CHECKPOINT---\n\n{e}\n"
        self.ctx.write_text(body, encoding="utf-8")

    def env(self):
        return dict(os.environ, VAULT_PATH=str(self.vault), XDG_CACHE_HOME=str(self.cache))

    def rpc(self, *calls, allow_error=False):
        """Drive the server over stdio exactly as an MCP host does. Returns the
        result object for each call, in order."""
        reqs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {}}}]
        for i, (method, params) in enumerate(calls, start=1):
            reqs.append({"jsonrpc": "2.0", "id": i, "method": method, "params": params})

        proc = subprocess.run(
            [sys.executable, str(SERVER)],
            input="\n".join(json.dumps(r) for r in reqs) + "\n",
            capture_output=True, text=True, timeout=180, env=self.env(),
        )
        self.assertEqual(proc.returncode, 0, f"server exited {proc.returncode}\n{proc.stderr}")

        by_id = {}
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if "error" in msg and not allow_error:
                self.fail(f"JSON-RPC error for id {msg.get('id')}: {msg['error']}")
            by_id[msg["id"]] = msg.get("result", msg.get("error"))
        self.assertEqual(len(by_id), len(reqs), f"missing responses; stderr:\n{proc.stderr}")
        self.by_id = by_id
        return [by_id[i] for i in range(1, len(reqs))]

    def call_tool(self, **arguments):
        """One vault_checkpoint call; returns its text content."""
        (res,) = self.rpc(("tools/call", {"name": "vault_checkpoint", "arguments": arguments}))
        return res["content"][0]["text"]


class ToolDiscoveryTests(VaultMCPCase):
    """The half that failed in the field: can the tool be found at all?"""

    def test_server_identifies_as_vault_mcp(self):
        """The advertised id is <server>__<tool>. Rename the server and every
        `mcp__vault-mcp__vault_checkpoint` in the instruction stack goes stale."""
        self.rpc(("tools/list", {}))
        self.assertEqual(self.by_id[0]["serverInfo"]["name"], SERVER_NAME)

    def test_all_six_tools_are_listed(self):
        (res,) = self.rpc(("tools/list", {}))
        self.assertEqual({t["name"] for t in res["tools"]}, EXPECTED_TOOLS)

    def test_checkpoint_tool_declares_its_arguments(self):
        """The skill documents project / n / headers; a host builds the call from
        this schema, so a missing property makes the documented call unmakeable."""
        (res,) = self.rpc(("tools/list", {}))
        schema = next(t for t in res["tools"] if t["name"] == "vault_checkpoint")["inputSchema"]
        self.assertEqual(set(schema["properties"]), {"project", "n", "headers"})
        self.assertFalse(schema.get("required"),
                         "project must stay optional — omitting it reads agent/working-context.md")

    def test_unknown_tool_name_is_an_error_not_a_silent_empty(self):
        """A short name reaching the server (rather than the host) must say so."""
        (res,) = self.rpc(("tools/call", {"name": "checkpoint", "arguments": {}}),
                          allow_error=True)
        self.assertIn("Tool not found: checkpoint", json.dumps(res))


class CheckpointReadTests(VaultMCPCase):
    """The other half: once found, does it return the right bytes?"""

    def test_latest_checkpoint_is_returned_verbatim(self):
        text = self.call_tool(project="demo")
        self.assertIn(NEWER, text, "the newest entry did not come back byte-for-byte")
        self.assertNotIn(OLDER, text, "n defaults to 1; the older entry should not appear")

    def test_load_bearing_details_survive_the_round_trip(self):
        text = self.call_tool(project="demo")
        for detail in ('bin/vault-mcp.py:289', '"Tool not found: vault_checkpoint"',
                       "hooks/session-start.sh", "--no-timeline"):
            with self.subTest(detail=detail):
                self.assertIn(detail, self.call_tool(project="demo", n=0))
        self.assertIn("hooks/session-start.sh", text)

    def test_n_zero_returns_every_entry_newest_last(self):
        text = self.call_tool(project="demo", n=0)
        self.assertIn(OLDER, text)
        self.assertIn(NEWER, text)
        self.assertLess(text.index(OLDER), text.index(NEWER), "entries came back out of order")

    def test_headers_returns_one_line_per_checkpoint(self):
        """entry_header() strips the '## Checkpoint —' marker, so an index line is
        the timestamp plus the parenthetical tag."""
        text = self.call_tool(project="demo", headers=True)
        lines = [l for l in text.splitlines() if l.startswith("2026-")]
        self.assertEqual(lines, ["2026-02-01 10:00 (older)", "2026-02-02 11:00 (newer)"])
        self.assertNotIn("### Current Goal", text, "headers mode leaked entry bodies")

    def test_headers_indexes_every_entry_regardless_of_n(self):
        """The tool's headers mode is a whole-file index — n does not narrow it.
        The CLI fallback applies -n FIRST, which is why the skill tells you to
        pass `-n 0 --headers` there. Pinned so the two stay documented apart."""
        self.assertEqual(self.call_tool(project="demo", headers=True),
                         self.call_tool(project="demo", headers=True, n=1))

    def test_the_hand_maintained_preamble_is_not_returned(self):
        """The whole point of the tool over a Read: entries only."""
        self.assertNotIn("Hand-maintained prose", self.call_tool(project="demo", n=0))

    def test_omitting_project_reads_the_agent_scoped_file(self):
        agent = self.vault / "agent"
        agent.mkdir()
        (agent / "working-context.md").write_text(
            PREAMBLE + "\n---CHECKPOINT---\n\n## Checkpoint — 2026-03-01 09:00 (unscoped)\n\nbody\n",
            encoding="utf-8")
        self.assertIn("(unscoped)", self.call_tool())

    def test_missing_project_explains_itself(self):
        text = self.call_tool(project="nope")
        self.assertIn("No working context", text)
        self.assertIn("nope", text)

    def test_context_without_entries_explains_itself(self):
        self.write_context([])
        text = self.call_tool(project="demo")
        self.assertIn("no checkpoints yet", text)

    def test_read_does_not_build_an_index(self):
        """It opens one known file. Paying for an index build (the cold-start cost
        of every other tool) would be waste — assert no cache was written."""
        self.call_tool(project="demo")
        self.assertEqual(list(self.cache.rglob("index.json")), [],
                         "the checkpoint read fell through to ensure_index()")


class BashFallbackTests(VaultMCPCase):
    """The skill tells agents to use `checkpoint.py read` when the tool is
    unavailable in a host. That fallback has to produce the same entries."""

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, str(CHECKPOINT_PY), "read", *args],
                              capture_output=True, text=True, timeout=60, env=self.env())
        return proc

    def test_cli_read_matches_the_tool_output(self):
        proc = self.run_cli("--project", "demo", "-n", "0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for entry in (OLDER, NEWER):
            self.assertIn(entry, proc.stdout)
        self.assertNotIn("Hand-maintained prose", proc.stdout)

    def test_cli_headers_needs_n_zero_to_match_the_tools_index(self):
        """`--headers` alone honours the default -n 1 and indexes one entry; the
        tool's headers=true indexes all. The skill documents `-n 0 --headers` for
        the equivalent call — this pins that instruction to the behaviour."""
        one = self.run_cli("--project", "demo", "--headers")
        self.assertEqual(one.returncode, 0, one.stderr)
        self.assertEqual(one.stdout.strip().splitlines(), ["2026-02-02 11:00 (newer)"])

        allof = self.run_cli("--project", "demo", "-n", "0", "--headers")
        self.assertEqual(allof.returncode, 0, allof.stderr)
        self.assertEqual(allof.stdout.strip().splitlines(),
                         ["2026-02-01 10:00 (older)", "2026-02-02 11:00 (newer)"])
        self.assertNotIn("### Current Goal", allof.stdout)

    def test_cli_reports_a_missing_project_on_stderr(self):
        proc = self.run_cli("--project", "nope")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no working context", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
