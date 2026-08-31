"""Unit tests for bin/checkpoint.py — the single ---CHECKPOINT--- implementation.

Run from repo root:
    py -3 -m unittest tests.test_checkpoint -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE.parent / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import checkpoint as cp  # noqa: E402


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
    Hand-maintained prose that must survive every trim. Links to [[something]].
    """)


def entry(tag: str, goal: str = "a goal") -> str:
    return textwrap.dedent(f"""\
        ## Checkpoint — 2026-02-01 10:00 ({tag})

        ### Current Goal
        {goal}

        ### Progress
        - [x] did the thing

        ### Open / Blocked
        - [ ] one thing left
        """).strip()


class VaultTempCase(unittest.TestCase):
    """Each test gets a throwaway vault via VAULT_PATH (same env var vault.py reads)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self._prev = os.environ.get("VAULT_PATH")
        os.environ["VAULT_PATH"] = str(self.vault)
        (self.vault / "projects" / "demo").mkdir(parents=True)
        self.ctx = self.vault / "projects" / "demo" / "working-context.md"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("VAULT_PATH", None)
        else:
            os.environ["VAULT_PATH"] = self._prev
        self.tmp.cleanup()

    def write(self, body: str, keep: int = 5, timeline: bool = False):
        class A:
            project, no_timeline = "demo", not timeline
        A.keep = keep
        from io import StringIO
        prev, sys.stdin = sys.stdin, StringIO(body)
        out, sys.stdout = sys.stdout, StringIO()
        try:
            return cp.cmd_write(A)
        finally:
            sys.stdin, sys.stdout = prev, out


class SplitJoinTests(unittest.TestCase):
    def test_no_separator_is_all_preamble(self):
        pre, entries = cp.split_document(PREAMBLE)
        self.assertEqual(pre, PREAMBLE)
        self.assertEqual(entries, [])

    def test_splits_and_drops_empties(self):
        text = PREAMBLE + f"\n{cp.SEP}\n{entry('a')}\n{cp.SEP}\n\n{cp.SEP}\n{entry('b')}\n"
        pre, entries = cp.split_document(text)
        self.assertIn("Hand-maintained prose", pre)
        self.assertEqual(len(entries), 2)
        self.assertIn("(a)", entries[0])
        self.assertIn("(b)", entries[1])

    def test_round_trip_is_stable(self):
        text = cp.join_document(PREAMBLE, [entry("a"), entry("b")])
        pre, entries = cp.split_document(text)
        self.assertEqual(cp.join_document(pre, entries), text)

    def test_join_without_preamble_has_no_leading_blank(self):
        out = cp.join_document("", [entry("a")])
        self.assertTrue(out.startswith(cp.SEP))

    def test_inline_marker_mention_is_not_a_separator(self):
        """Real notes document the format in prose; that must not split the file.
        projects/kahin-v1-internal/working-context.md does exactly this."""
        preamble = (
            "# demo — Working Context\n\n"
            "> Checkpoints are `" + cp.SEP + "`-delimited and appended newest LAST.\n\n"
            "Another paragraph mentioning " + cp.SEP + " mid-sentence.\n"
        )
        text = preamble + f"\n{cp.SEP}\n{entry('only')}\n"
        pre, entries = cp.split_document(text)
        self.assertEqual(len(entries), 1)
        self.assertIn("(only)", entries[0])
        self.assertIn("newest LAST", pre)
        self.assertIn("mid-sentence", pre)

    def test_trailing_whitespace_on_separator_still_splits(self):
        text = f"pre\n{cp.SEP}  \n{entry('a')}\n"
        _, entries = cp.split_document(text)
        self.assertEqual(len(entries), 1)

    def test_entry_header_strips_marker(self):
        self.assertEqual(cp.entry_header(entry("tagged")), "2026-02-01 10:00 (tagged)")
        self.assertEqual(cp.entry_header("no header here"), "(no header)")


class PathTests(VaultTempCase):
    def test_project_and_agent_paths(self):
        self.assertEqual(cp.context_path(self.vault, "demo"), self.ctx)
        self.assertEqual(cp.context_path(self.vault, None),
                         self.vault / "agent" / "working-context.md")

    def test_project_of(self):
        self.assertEqual(cp.project_of(self.ctx), "demo")
        self.assertIsNone(cp.project_of(self.vault / "agent" / "working-context.md"))

    def test_timeline_beside_project_else_root(self):
        self.assertEqual(cp.timeline_path(self.ctx), self.ctx.parent / "timeline.md")
        agent_ctx = self.vault / "agent" / "working-context.md"
        self.assertEqual(cp.timeline_path(agent_ctx), self.vault / "timeline.md")


class WriteTests(VaultTempCase):
    def test_creates_file_with_frontmatter_when_absent(self):
        self.write(entry("first"))
        text = self.ctx.read_text()
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("project: demo", text)
        self.assertIn("(first)", text)

    def test_preamble_survives_trimming(self):
        self.ctx.write_text(PREAMBLE + f"\n{cp.SEP}\n{entry('oldest')}\n")
        for i in range(6):
            self.write(entry(f"n{i}"))
        text = self.ctx.read_text()
        self.assertIn("Hand-maintained prose that must survive every trim", text)
        self.assertIn("[[something]]", text)
        self.assertIn("project: demo", text)

    def test_preamble_that_mentions_the_marker_survives_write_and_trim(self):
        """The regression that made SEP_RE line-anchored: a prose mention of the
        marker in the preamble used to be read as a separator, so the text after it
        became an 'entry' and got trimmed away on the sixth write."""
        preamble = (
            "---\ndate: 2026-01-01\ntype: mission\nstatus: active\nproject: demo\n---\n\n"
            "# demo — Working Context\n\n"
            "> **Ordering convention.** Checkpoints are `" + cp.SEP + "`-delimited "
            "and appended newest LAST. Do not invert.\n"
        )
        self.ctx.write_text(preamble)
        for i in range(6):
            self.write(entry(f"n{i}"), keep=5)
        text = self.ctx.read_text()
        self.assertIn("Ordering convention", text)
        self.assertIn("Do not invert", text)
        _, entries = cp.split_document(text)
        self.assertEqual(len(entries), 5)

    def test_keeps_only_last_n(self):
        for i in range(8):
            self.write(entry(f"n{i}"), keep=5)
        _, entries = cp.split_document(self.ctx.read_text())
        self.assertEqual(len(entries), 5)
        self.assertIn("(n3)", entries[0])
        self.assertIn("(n7)", entries[-1])

    def test_oldest_is_the_one_dropped(self):
        self.write(entry("keeper"), keep=2)
        self.write(entry("middle"), keep=2)
        self.write(entry("newest"), keep=2)
        text = self.ctx.read_text()
        self.assertNotIn("(keeper)", text)
        self.assertIn("(middle)", text)
        self.assertIn("(newest)", text)

    def test_empty_body_is_refused(self):
        self.assertEqual(self.write("   \n  "), 2)
        self.assertFalse(self.ctx.exists())

    def test_headerless_body_gets_a_header(self):
        self.write("### Current Goal\njust a body, no header line")
        _, entries = cp.split_document(self.ctx.read_text())
        self.assertTrue(entries[0].startswith("## Checkpoint — "))


class TimelineTests(VaultTempCase):
    def test_write_appends_to_timeline(self):
        self.write(entry("tracked"), timeline=True)
        tl = self.ctx.parent / "timeline.md"
        self.assertTrue(tl.exists())
        text = tl.read_text()
        self.assertIn("tags: [agent_util, timeline]", text)
        self.assertIn("project: demo", text)
        self.assertIn("(tracked)", text)

    def test_timeline_keeps_entries_that_working_context_trimmed(self):
        for i in range(7):
            self.write(entry(f"n{i}"), keep=2, timeline=True)
        ctx_text = self.ctx.read_text()
        tl_text = (self.ctx.parent / "timeline.md").read_text()
        self.assertNotIn("(n0)", ctx_text)      # trimmed out of the circular buffer
        self.assertIn("(n0)", tl_text)          # but preserved permanently
        self.assertIn("(n6)", tl_text)

    def test_cmd_timeline_is_a_noop_without_checkpoints(self):
        self.ctx.write_text(PREAMBLE)

        class A:
            file = str(self.ctx)
        self.assertEqual(cp.cmd_timeline(A), 0)
        self.assertFalse((self.ctx.parent / "timeline.md").exists())

    def test_cmd_timeline_is_a_noop_for_a_missing_file(self):
        class A:
            file = str(self.vault / "nope" / "working-context.md")
        self.assertEqual(cp.cmd_timeline(A), 0)


class TimelineDigestTests(unittest.TestCase):
    def test_line1_is_header_plus_goal(self):
        line1, _ = cp.timeline_lines(entry("tag", goal="ship the thing"))
        self.assertIn("Checkpoint — 2026-02-01 10:00 (tag)", line1)
        self.assertIn("ship the thing", line1)

    def test_line2_carries_progress_and_open_items(self):
        _, line2 = cp.timeline_lines(entry("tag"))
        self.assertIn("did the thing", line2)
        self.assertIn("left: one thing left", line2)

    def test_no_sections_yields_placeholder(self):
        _, line2 = cp.timeline_lines("## Checkpoint — 2026-01-01 00:00\n\nprose only")
        self.assertEqual(line2, "(no notable details)")

    def test_bugs_and_decisions_are_surfaced(self):
        e = textwrap.dedent("""\
            ## Checkpoint — 2026-01-01 00:00

            ### Bugs
            - **off-by-one in the trim** details follow

            ### Key Decisions
            - **keep 5, not 10** rationale follows
            """)
        _, line2 = cp.timeline_lines(e)
        self.assertIn("BUG: off-by-one in the trim", line2)
        self.assertIn("DECISION: keep 5, not 10", line2)


if __name__ == "__main__":
    unittest.main()
