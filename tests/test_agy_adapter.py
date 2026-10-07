"""hooks/agy-adapter.py — the Claude hook scripts under agy's hook contract.

Until 2026-10-07 agy loaded zero hooks: the file sat in the wrong folder, in Claude's
shape, and the scripts speak Claude's stdin/stdout. These drive the adapter with the
payloads agy's own docs describe, against a throwaway HOME and vault.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "hooks/agy-adapter.py"


class AdapterCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.vault = self.home / "obsidian_notes"
        (self.vault / "projects/demo").mkdir(parents=True)
        (self.vault / "agent").mkdir()
        (self.vault / "agent/learned-dispositions.md").write_text(
            "---\ndate: 2026-10-07\n---\n\n- **measure first**\n", encoding="utf-8")
        self.workspace = self.home / "src" / "demo"
        self.workspace.mkdir(parents=True)

    def call(self, event, *scripts, payload=None, raw=None):
        env = {"HOME": str(self.home), "PATH": os.environ["PATH"], "CLAUDECODE": "1",
               "XDG_CACHE_HOME": str(self.home / "cache")}
        data = raw if raw is not None else json.dumps(payload or {})
        p = subprocess.run([sys.executable, str(ADAPTER), event, *scripts], input=data,
                           text=True, capture_output=True, env=env, cwd=str(REPO), timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def base(self, **kw):
        return dict(conversationId="conv-1", workspacePaths=[str(self.workspace)],
                    transcriptPath="/x/transcript.jsonl", **kw)

    def injected(self, out):
        steps = out.get("injectSteps") or []
        return "\n".join(s.get("ephemeralMessage", "") for s in steps)


class PreInvocationTests(AdapterCase):
    def test_session_start_is_injected_once_per_conversation(self):
        first = self.injected(self.call("PreInvocation", "session-start.sh", payload=self.base()))
        self.assertIn("Vault: ~/obsidian_notes/", first)
        self.assertIn("LEARNED DISPOSITIONS", first)
        self.assertEqual(self.call("PreInvocation", "session-start.sh", payload=self.base()), {})

    def test_project_is_detected_from_the_workspace_not_the_hook_folder(self):
        out = self.injected(self.call("PreInvocation", "session-start.sh", payload=self.base()))
        self.assertIn("CWD project: demo", out)

    def test_claude_only_lines_stay_out_of_agy(self):
        out = self.injected(self.call("PreInvocation", "session-start.sh", payload=self.base()))
        self.assertNotIn("cache-keepalive", out)


class PostToolUseTests(AdapterCase):
    def write_event(self, path, encode_twice=False):
        target = json.dumps(str(path)) if encode_twice else str(path)
        return self.base(toolCall={"name": "write_to_file", "args": {"TargetFile": target}})

    def test_tool_output_is_queued_and_delivered_on_the_next_invocation(self):
        bad = self.vault / "projects/demo/Bad Note.md"
        bad.write_text("no frontmatter here\n", encoding="utf-8")
        self.assertEqual(self.call("PostToolUse", "validate-vault-write.sh",
                                   payload=self.write_event(bad)), {})
        out = self.injected(self.call("PreInvocation", "session-start.sh", payload=self.base()))
        self.assertIn("VAULT WRITE VALIDATION FAILED", out)
        self.assertIn("BAD FILENAME", out)

    def test_double_encoded_arguments_are_decoded(self):
        bad = self.vault / "projects/demo/nolinks.md"
        bad.write_text("---\ndate: 2026-10-07\n---\nbody\n", encoding="utf-8")
        self.call("PostToolUse", "validate-vault-write.sh",
                  payload=self.write_event(bad, encode_twice=True))
        self.call("PreInvocation", "session-start.sh", payload=self.base())   # start block
        # queue drained into the start block above; a second write is delivered alone
        self.call("PostToolUse", "validate-vault-write.sh",
                  payload=self.write_event(bad, encode_twice=True))
        out = self.injected(self.call("PreInvocation", "session-start.sh", payload=self.base()))
        self.assertIn("NO WIKILINKS", out)
        self.assertNotIn("Vault: ~/obsidian_notes/", out)


class StopTests(AdapterCase):
    def test_stop_after_vault_work_asks_the_agent_to_continue_with_the_reminder(self):
        note = self.vault / "projects/demo/good-note.md"
        note.write_text("---\ndate: 2026-10-07\ntags: [x]\ntype: concept\nstatus: active\n---\n"
                        "see [[other]]\n", encoding="utf-8")
        self.call("PostToolUse", "validate-vault-write.sh",
                  payload=self.base(toolCall={"name": "write_to_file", "args": {"TargetFile": str(note)}}))
        out = self.call("Stop", "session-stop.sh", payload=self.base())
        self.assertEqual(out.get("decision"), "continue")
        self.assertIn("DISPOSITION CHECK", out.get("reason", ""))
        self.assertEqual(self.call("Stop", "session-stop.sh", payload=self.base()), {},
                         "the reminder must not fire again without new vault work")

    def test_stop_without_vault_work_is_silent(self):
        self.assertEqual(self.call("Stop", "session-stop.sh", payload=self.base()), {})


class RobustnessTests(AdapterCase):
    def test_garbage_input_never_blocks(self):
        self.assertEqual(self.call("PostToolUse", "validate-vault-write.sh", raw="not json"), {})
        self.assertEqual(self.call("Bogus", "session-start.sh", payload=self.base()), {})


if __name__ == "__main__":
    unittest.main()
