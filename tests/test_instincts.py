"""Unit tests for bin/instincts.py — the disposition staging queue.

The two invariants under test are the two the OLD methodology failed to hold on its
own: a bounded always-on budget, and promotion that has to be earned. Both were prose
rules before; across 43 commits to the old instincts.yaml the confidence field never
moved once. That is why they are enforced in code and tested here.

Run from repo root:
    py -3 -m unittest tests.test_instincts -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE.parent / "bin"
if str(BIN) not in sys.path:
    sys.path.insert(0, str(BIN))

import instincts as I  # noqa: E402


class Args:
    """Duck-typed argparse namespace; mirrors the style used in test_checkpoint."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


class QueueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name)
        (self.vault / "agent").mkdir(parents=True)
        self._prev = os.environ.get("VAULT_PATH")
        os.environ["VAULT_PATH"] = str(self.vault)
        self.addCleanup(self._restore)
        self.rules = self.vault / "agent" / "learned-dispositions.md"

    def _restore(self):
        if self._prev is None:
            os.environ.pop("VAULT_PATH", None)
        else:
            os.environ["VAULT_PATH"] = self._prev

    def propose(self, text, origin="user said so", cap=I.CAP, project="demo", scope=None):
        return I.cmd_propose(Args(disposition=text, origin=origin,
                                  project=project, cap=cap, scope=scope))

    def backdate(self, match, day="2020-01-01"):
        """Pretend the last re-trigger happened in an earlier session."""
        items = I.load()
        items[I.find(items, match)]["last_seen"] = day
        I.save(items)

    def quiet(self, fn, *a, **kw):
        from io import StringIO
        out, sys.stdout = sys.stdout, StringIO()
        try:
            return fn(*a, **kw), sys.stdout.getvalue()
        finally:
            sys.stdout = out


class ProposeTests(QueueCase):
    def test_propose_writes_the_full_schema(self):
        self.quiet(self.propose, "always measure before estimating")
        items = I.load()
        self.assertEqual(len(items), 1)
        for field in I.FIELDS:
            self.assertIn(field, items[0])
        self.assertEqual(items[0]["seen"], 1)

    def test_duplicate_does_not_create_a_second_entry(self):
        self.quiet(self.propose, "same rule")
        self.quiet(self.propose, "SAME RULE")          # case-insensitive
        self.assertEqual(len(I.load()), 1)

    def test_duplicate_in_a_later_session_counts_as_the_re_trigger(self):
        """The dead end this guards: `seen` was only ever incremented by an explicit
        `seen` command that nothing in the instruction stack invoked, so every entry
        sat at 1 until it expired and nothing could ever promote. A later session
        independently proposing the same rule IS the recurrence evidence."""
        self.quiet(self.propose, "recurring rule")
        self.backdate("recurring rule")
        self.quiet(self.propose, "recurring rule")
        self.assertEqual(I.load()[0]["seen"], 2)

    def test_same_day_re_propose_does_not_count(self):
        """Otherwise one session could promote its own brand-new rule by repeating it."""
        self.quiet(self.propose, "same day rule")
        self.quiet(self.propose, "same day rule")
        self.assertEqual(I.load()[0]["seen"], 1)

    def test_a_re_trigger_records_its_own_evidence(self):
        self.quiet(self.propose, "evidenced rule", origin="first correction")
        self.backdate("evidenced rule")
        self.quiet(self.propose, "evidenced rule", origin="second correction")
        rec = I.load()[0].get("recurrences", [])
        self.assertEqual(len(rec), 1)
        self.assertIn("second correction", rec[0])

    def test_promotion_is_reachable_through_propose_alone(self):
        """End to end: nothing but the hook's own `propose` call is needed."""
        self.quiet(self.propose, "reachable rule", scope="global")
        self.backdate("reachable rule")
        self.quiet(self.propose, "reachable rule", scope="global")
        self.quiet(I.cmd_promote, Args(match="reachable", apply=True, force=False))
        self.assertEqual(I.load(), [])
        self.assertIn("reachable rule", self.rules.read_text(encoding="utf-8"))

    def test_cap_is_enforced_not_requested(self):
        """The old file grew unbounded at 3.22/week because nothing stopped it."""
        for n in range(3):
            self.quiet(self.propose, f"rule {n}", cap=3)
        with self.assertRaises(SystemExit) as cm:
            self.quiet(self.propose, "one too many", cap=3)
        self.assertIn("queue is full", str(cm.exception))
        self.assertEqual(len(I.load()), 3)

    def test_full_queue_names_what_to_evict(self):
        for n in range(2):
            self.quiet(self.propose, f"rule {n}", cap=2)
        with self.assertRaises(SystemExit) as cm:
            self.quiet(self.propose, "blocked", cap=2)
        self.assertIn("rule 0", str(cm.exception))

    def test_header_survives_a_write(self):
        self.quiet(self.propose, "a rule")
        text = I.queue_path().read_text(encoding="utf-8")
        self.assertIn("Disposition staging queue", text)
        self.assertIn("bin/instincts.py", text)


class PromotionTests(QueueCase):
    """The GLOBAL path: the vault's agent/learned-dispositions.md. Project routing is in ScopeTests."""
    def test_promotion_below_the_bar_is_refused(self):
        self.quiet(self.propose, "unearned rule", scope="global")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(I.cmd_promote, Args(match="unearned", apply=False, force=False))
        self.assertIn("seen=1", str(cm.exception))

    def test_seen_earns_promotion(self):
        self.quiet(self.propose, "earned rule", scope="global")
        self.backdate("earned rule")
        _, out = self.quiet(I.cmd_seen, Args(match="earned"))
        self.assertIn("seen=2", out)
        self.assertIn("READY", out)

    def test_dry_run_writes_nothing(self):
        self.quiet(self.propose, "dry rule", scope="global")
        self.backdate("dry")
        self.quiet(I.cmd_seen, Args(match="dry"))
        _, out = self.quiet(I.cmd_promote, Args(match="dry", apply=False, force=False))
        self.assertIn("nothing written", out)
        self.assertFalse(self.rules.exists())
        self.assertEqual(len(I.load()), 1)

    def test_global_promotion_lands_in_the_vault_not_the_repo(self):
        """Dispositions are the user's, so they live in the vault; the hook prints them."""
        self.quiet(self.propose, "vault rule", origin='User: "always do X"', scope="global")
        self.backdate("vault rule")
        self.quiet(I.cmd_seen, Args(match="vault rule"))
        _, out = self.quiet(I.cmd_promote, Args(match="vault rule", apply=True, force=False))
        self.assertEqual(I.global_path(), self.rules)
        self.assertIn(str(self.rules), out)
        self.assertIn("- **vault rule**", self.rules.read_text(encoding="utf-8"))

    def test_global_note_carries_vault_frontmatter_and_a_wikilink(self):
        self.quiet(self.propose, "frontmatter rule", scope="global")
        self.quiet(I.cmd_promote, Args(match="frontmatter", apply=True, force=True))
        text = self.rules.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        for field in ("date: 2", "tags:", "type: decision", "status: active"):
            self.assertIn(field, text)
        self.assertIn("[[", text)
        self.assertNotIn("{today}", text)

    def test_apply_moves_it_out_of_the_queue(self):
        self.quiet(self.propose, "real rule", origin='User: "do it this way"', scope="global")
        self.backdate("real rule")
        self.quiet(I.cmd_seen, Args(match="real rule"))
        self.quiet(I.cmd_promote, Args(match="real rule", apply=True, force=False))
        self.assertEqual(I.load(), [])
        text = self.rules.read_text(encoding="utf-8")
        self.assertIn("real rule", text)
        self.assertIn('User: "do it this way"', text)   # provenance survives

    def test_promotion_appends_rather_than_clobbering(self):
        for n in ("first rule", "second rule"):
            self.quiet(self.propose, n, scope="global")
            self.backdate(n)
            self.quiet(I.cmd_seen, Args(match=n))
            self.quiet(I.cmd_promote, Args(match=n, apply=True, force=False))
        text = self.rules.read_text(encoding="utf-8")
        self.assertIn("first rule", text)
        self.assertIn("second rule", text)

    def test_force_overrides_the_bar(self):
        self.quiet(self.propose, "forced rule", scope="global")
        self.quiet(I.cmd_promote, Args(match="forced", apply=True, force=True))
        self.assertEqual(I.load(), [])


class MatchTests(QueueCase):
    def test_ambiguous_match_refuses_rather_than_guessing(self):
        self.quiet(self.propose, "measure the thing")
        self.quiet(self.propose, "measure the other thing")
        with self.assertRaises(SystemExit) as cm:
            self.backdate("measure")
            self.quiet(I.cmd_seen, Args(match="measure"))
        self.assertIn("matches 2 entries", str(cm.exception))

    def test_no_match_is_an_error(self):
        with self.assertRaises(SystemExit):
            self.backdate("nothing like this")
            self.quiet(I.cmd_seen, Args(match="nothing like this"))


class ExpiryTests(QueueCase):
    def test_stale_never_retriggered_proposals_expire(self):
        self.quiet(self.propose, "stale rule")
        items = I.load()
        items[0]["date"] = "2020-01-01"
        I.save(items)
        self.quiet(I.cmd_expire, Args(days=90))
        self.assertEqual(I.load(), [])

    def test_a_retriggered_proposal_survives_expiry(self):
        self.quiet(self.propose, "live rule")
        items = I.load()
        items[0]["date"] = "2020-01-01"
        items[0]["seen"] = I.PROMOTE_AT
        I.save(items)
        self.quiet(I.cmd_expire, Args(days=90))
        self.assertEqual(len(I.load()), 1)


class ScopeTests(QueueCase):
    """Projects differ in scope and method; a rule is project working-mode until a
    second project shows it holds there too. Promotion routes on that call."""

    def test_default_scope_is_project(self):
        self.quiet(self.propose, "speak plainly")
        self.assertEqual(I.load()[0]["scope"], "project")
        self.assertEqual(I.load()[0]["project"], "demo")

    def test_project_scope_requires_a_project(self):
        with self.assertRaises(SystemExit):
            self.quiet(self.propose, "speak plainly", project=None)

    def test_global_scope_is_explicit(self):
        self.quiet(self.propose, "measure before claiming", scope="global")
        self.assertEqual(I.load()[0]["scope"], "global")

    def test_re_trigger_from_a_second_project_is_recorded_and_flagged(self):
        self.quiet(self.propose, "speak plainly")
        self.backdate("speak plainly")
        _, out = self.quiet(self.propose, "speak plainly", project="other")
        x = I.load()[0]
        self.assertEqual(x["also_seen_in"], ["other"])
        self.assertEqual(x["project"], "demo")            # origin project is kept
        self.assertIn("promote --scope global", out)

    def test_list_shows_the_scope(self):
        self.quiet(self.propose, "speak plainly")
        self.quiet(self.propose, "measure before claiming", scope="global")
        _, out = self.quiet(I.cmd_list, Args(all=False))
        self.assertIn("(project:demo)", out)
        self.assertIn("(global)", out)

    def _ready(self, text, **kw):
        self.quiet(self.propose, text, **kw)
        self.backdate(text)
        self.quiet(self.propose, text, **kw)

    def test_project_promotion_lands_in_the_vault_working_mode_note_not_the_rules(self):
        self._ready("speak plainly")
        self.quiet(I.cmd_promote, Args(match="speak plainly", apply=True, force=False, scope=None))
        wm = self.vault / "projects" / "demo" / "decisions" / "working-mode.md"
        self.assertTrue(wm.is_file())
        text = wm.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"), "a vault note needs frontmatter")
        self.assertIn("type: decision", text)
        self.assertIn("project: demo", text)
        self.assertIn("[[demo/working-context]]", text)
        self.assertIn("- **speak plainly**", text)
        self.assertFalse(self.rules.exists(), "a project rule must not become global")
        self.assertEqual(I.load(), [])

    def test_global_promotion_lands_in_the_global_note(self):
        self._ready("measure before claiming", scope="global")
        self.quiet(I.cmd_promote, Args(match="measure", apply=True, force=False, scope=None))
        self.assertIn("measure before claiming", self.rules.read_text(encoding="utf-8"))
        self.assertFalse((self.vault / "projects").exists())

    def test_scope_can_be_overridden_at_promotion(self):
        self._ready("speak plainly")                         # queued as project
        self.quiet(I.cmd_promote, Args(match="speak plainly", apply=True, force=False, scope="global"))
        self.assertIn("speak plainly", self.rules.read_text(encoding="utf-8"))
        self.assertFalse((self.vault / "projects" / "demo" / "decisions" / "working-mode.md").exists())

    def test_project_promotion_appends_to_an_existing_working_mode_note(self):
        self._ready("speak plainly")
        self.quiet(I.cmd_promote, Args(match="speak plainly", apply=True, force=False, scope=None))
        self._ready("show your evidence")
        self.quiet(I.cmd_promote, Args(match="evidence", apply=True, force=False, scope=None))
        text = (self.vault / "projects" / "demo" / "decisions" / "working-mode.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("---\ndate:"), 1, "frontmatter must not be duplicated")
        self.assertLess(text.index("speak plainly"), text.index("show your evidence"))

    def test_dry_run_names_the_working_mode_target(self):
        self._ready("speak plainly")
        _, out = self.quiet(I.cmd_promote, Args(match="speak plainly", apply=False, force=False, scope=None))
        self.assertIn("working-mode", out)
        self.assertFalse((self.vault / "projects").exists())


class PendingTests(QueueCase):
    """The session-start hook prints `pending`; it must be silent on the normal path
    and name the decision the user has to make otherwise."""

    def test_silent_when_nothing_is_ready_and_the_queue_has_room(self):
        self.quiet(self.propose, "speak plainly")
        _, out = self.quiet(I.cmd_pending, Args())
        self.assertEqual(out, "")

    def test_ready_entries_are_named_with_their_scope(self):
        self.quiet(self.propose, "speak plainly")
        self.backdate("speak plainly")
        self.quiet(self.propose, "speak plainly", project="other")
        _, out = self.quiet(I.cmd_pending, Args())
        self.assertIn("READY", out)
        self.assertIn("project:demo", out)
        self.assertIn("also seen in other", out)
        self.assertIn("ask the user", out)

    def test_near_cap_is_flagged_before_propose_starts_refusing(self):
        for n in range(I.CAP - 1):
            self.quiet(self.propose, f"rule {n}")
        _, out = self.quiet(I.cmd_pending, Args())
        self.assertIn(f"{I.CAP - 1}/{I.CAP}", out)
        self.quiet(self.propose, "last rule")
        _, out = self.quiet(I.cmd_pending, Args())
        self.assertIn("will be refused", out)


if __name__ == "__main__":
    unittest.main()
