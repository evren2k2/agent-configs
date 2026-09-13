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
        self.rules = self.vault / "learned-dispositions.md"
        self.agy = self.vault / "agy" / "SKILL.md"
        self._prev_rules, self._prev_agy = I.RULES_FILE, I.AGY_SKILL
        I.RULES_FILE, I.AGY_SKILL = self.rules, self.agy
        self.addCleanup(lambda: setattr(I, "RULES_FILE", self._prev_rules))
        self.addCleanup(lambda: setattr(I, "AGY_SKILL", self._prev_agy))

    def _restore(self):
        if self._prev is None:
            os.environ.pop("VAULT_PATH", None)
        else:
            os.environ["VAULT_PATH"] = self._prev

    def propose(self, text, origin="user said so", cap=I.CAP):
        return I.cmd_propose(Args(disposition=text, origin=origin,
                                  project="demo", cap=cap))

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

    def test_duplicate_is_a_no_op(self):
        self.quiet(self.propose, "same rule")
        self.quiet(self.propose, "SAME RULE")          # case-insensitive
        self.assertEqual(len(I.load()), 1)

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
    def test_promotion_below_the_bar_is_refused(self):
        self.quiet(self.propose, "unearned rule")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(I.cmd_promote, Args(match="unearned", apply=False, force=False))
        self.assertIn("seen=1", str(cm.exception))

    def test_seen_earns_promotion(self):
        self.quiet(self.propose, "earned rule")
        _, out = self.quiet(I.cmd_seen, Args(match="earned"))
        self.assertIn("seen=2", out)
        self.assertIn("READY", out)

    def test_dry_run_writes_nothing(self):
        self.quiet(self.propose, "dry rule")
        self.quiet(I.cmd_seen, Args(match="dry"))
        _, out = self.quiet(I.cmd_promote, Args(match="dry", apply=False, force=False))
        self.assertIn("nothing written", out)
        self.assertFalse(self.rules.exists())
        self.assertFalse(self.agy.exists())
        self.assertEqual(len(I.load()), 1)

    def test_promotion_lands_in_BOTH_stacks(self):
        """agentcfg installs rules/ for Claude only, so agy takes the same content as a
        skill. A promotion that reached one stack would be a Claude-only disposition."""
        self.quiet(self.propose, "cross-stack rule", origin='User: "always do X"')
        self.quiet(I.cmd_seen, Args(match="cross-stack"))
        self.quiet(I.cmd_promote, Args(match="cross-stack", apply=True, force=False))
        for path in (self.rules, self.agy):
            self.assertTrue(path.exists(), f"{path} was not written")
            self.assertIn("cross-stack rule", path.read_text(encoding="utf-8"))

    def test_agy_copy_carries_skill_frontmatter(self):
        """agy loads skills, which must declare name/description to be discoverable."""
        self.quiet(self.propose, "frontmatter rule")
        self.quiet(I.cmd_seen, Args(match="frontmatter"))
        self.quiet(I.cmd_promote, Args(match="frontmatter", apply=True, force=False))
        head = self.agy.read_text(encoding="utf-8")
        self.assertTrue(head.startswith("---\n"))
        self.assertIn("name: learned-dispositions", head)
        self.assertIn("description:", head)

    def test_both_stacks_stay_in_step_across_promotions(self):
        for n in ("rule alpha", "rule beta"):
            self.quiet(self.propose, n)
            self.quiet(I.cmd_seen, Args(match=n))
            self.quiet(I.cmd_promote, Args(match=n, apply=True, force=False))
        c = self.rules.read_text(encoding="utf-8")
        a = self.agy.read_text(encoding="utf-8")
        for n in ("rule alpha", "rule beta"):
            self.assertIn(n, c)
            self.assertIn(n, a)

    def test_apply_moves_it_out_of_the_queue(self):
        self.quiet(self.propose, "real rule", origin='User: "do it this way"')
        self.quiet(I.cmd_seen, Args(match="real rule"))
        self.quiet(I.cmd_promote, Args(match="real rule", apply=True, force=False))
        self.assertEqual(I.load(), [])
        text = self.rules.read_text(encoding="utf-8")
        self.assertIn("real rule", text)
        self.assertIn('User: "do it this way"', text)   # provenance survives

    def test_promotion_appends_rather_than_clobbering(self):
        for n in ("first rule", "second rule"):
            self.quiet(self.propose, n)
            self.quiet(I.cmd_seen, Args(match=n))
            self.quiet(I.cmd_promote, Args(match=n, apply=True, force=False))
        text = self.rules.read_text(encoding="utf-8")
        self.assertIn("first rule", text)
        self.assertIn("second rule", text)

    def test_force_overrides_the_bar(self):
        self.quiet(self.propose, "forced rule")
        self.quiet(I.cmd_promote, Args(match="forced", apply=True, force=True))
        self.assertEqual(I.load(), [])


class MatchTests(QueueCase):
    def test_ambiguous_match_refuses_rather_than_guessing(self):
        self.quiet(self.propose, "measure the thing")
        self.quiet(self.propose, "measure the other thing")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(I.cmd_seen, Args(match="measure"))
        self.assertIn("matches 2 entries", str(cm.exception))

    def test_no_match_is_an_error(self):
        with self.assertRaises(SystemExit):
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


if __name__ == "__main__":
    unittest.main()
