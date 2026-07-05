"""Unit tests for the agentcfg install/uninstall JSON lifecycle. Stdlib only.

The install lifecycle (bin/agentcfg) has no other coverage; these lock in the
P0 backup-poisoning and un-merge-snapshot fixes so a settings.json that already
contains a user's own keys survives install->uninstall byte-for-byte.

Run from repo root:
    python3 -m unittest tests.test_agentcfg -v
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path


HERE = Path(__file__).resolve().parent
AGENTCFG_SCRIPT = HERE.parent / "bin" / "agentcfg"


def _load_agentcfg():
    """Import bin/agentcfg (extensionless script) as a module."""
    loader = SourceFileLoader("agentcfg", str(AGENTCFG_SCRIPT))
    spec = importlib.util.spec_from_loader("agentcfg", loader)
    if spec is None:
        raise RuntimeError(f"Cannot load {AGENTCFG_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


ac = _load_agentcfg()

REPO_DATA = {
    "permissions": {"allow": ["Read(~/x)"]},
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "ours"}]}]},
}

USER = {
    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "user-stop"}]}]},
    "theme": "light",
    "permissions": {"allow": ["Bash(ls)"]},
    "custom": [1, 2, 3],
}


class AgentcfgJsonLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo_src = self.tmp / "repo_settings.json"
        self.repo_src.write_text(json.dumps(REPO_DATA, indent=2), encoding="utf-8")
        self.dest = self.tmp / "settings.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bak(self) -> Path:
        return self.dest.with_suffix(self.dest.suffix + ".orig")

    def test_orig_backup_restores_user_file_byte_for_byte(self):
        user_text = json.dumps(USER, indent=2) + "\n"
        self.dest.write_text(user_text, encoding="utf-8")

        ac.apply_json(self.repo_src, self.dest)
        merged = json.loads(self.dest.read_text())
        self.assertTrue(self._bak().exists())
        self.assertEqual(self._bak().read_text(), user_text)      # exact original bytes
        self.assertIn("Stop", merged["hooks"])                    # user hook kept
        self.assertIn("SessionStart", merged["hooks"])            # ours merged in
        self.assertEqual(merged["theme"], "light")                # unmanaged scalar untouched
        self.assertEqual(set(merged["permissions"]["allow"]), {"Bash(ls)", "Read(~/x)"})

        shutil.move(str(self._bak()), str(self.dest))             # uninstall via .orig
        self.assertEqual(self.dest.read_text(), user_text)

    def test_snapshot_restores_when_no_orig_present(self):
        self.dest.write_text(json.dumps(USER, indent=2) + "\n", encoding="utf-8")
        ac.apply_json(self.repo_src, self.dest)
        self._bak().unlink()                                      # force _unmerge_json fallback
        ac._unmerge_json(self.dest)
        self.assertEqual(json.loads(self.dest.read_text()), USER)

    def test_no_backup_poisoning_on_repeated_install(self):
        ac.apply_json(self.repo_src, self.dest)                   # fresh: no prior file
        self.assertFalse(self._bak().exists())
        ac.apply_json(self.repo_src, self.dest)                   # re-run must not back up our output
        self.assertFalse(self._bak().exists())
        ac._unmerge_json(self.dest)                               # created file removed cleanly
        self.assertFalse(self.dest.exists())


class AgentcfgIsOurs(unittest.TestCase):
    """The uninstall orphan-cleanup iterates the dest dir and unlink()s every
    is_ours entry — the one destructive P2 change. Pin down its classification."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dest_dir = self.tmp / "skills"
        self.dest_dir.mkdir()
        self.repo = ac.REPO.resolve()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dest_iteration_removes_only_ours(self):
        ours = self.dest_dir / "ours"
        ours.symlink_to(self.repo / "README.md")                  # -> into REPO: ours
        real = self.dest_dir / "user-real.md"
        real.write_text("mine", encoding="utf-8")                 # user's real file: keep
        target = self.tmp / "outside.md"
        target.write_text("x", encoding="utf-8")
        elsewhere = self.dest_dir / "user-link"
        elsewhere.symlink_to(target)                              # user's link elsewhere: keep
        broken = self.dest_dir / "broken-ours"
        broken.symlink_to(self.repo / "does-not-exist-xyz")       # broken but target in REPO: ours

        self.assertTrue(ac.is_ours(ours))
        self.assertFalse(ac.is_ours(real))
        self.assertFalse(ac.is_ours(elsewhere))
        self.assertTrue(ac.is_ours(broken))

        removed = {ch.name for ch in sorted(self.dest_dir.iterdir()) if ac.is_ours(ch)}
        self.assertEqual(removed, {"ours", "broken-ours"})

    def test_sibling_prefix_is_not_ours(self):
        # A symlink into a sibling like <repo>-backup must not match by string prefix.
        sib = self.repo.parent / (self.repo.name + "-backup-xyz")
        link = self.dest_dir / "sibling"
        link.symlink_to(sib / "file.md")
        self.assertFalse(ac.is_ours(link))


class AgentcfgStripMd(unittest.TestCase):
    def test_missing_end_marker_preserves_user_content(self):
        # An incomplete block (BEGIN but no END) must not eat trailing user content.
        text = "user pre\n\n" + ac.MD_BEGIN + "\nmanaged body\n\n# My own notes\nkeep me\n"
        self.assertEqual(ac.strip_md_block(text), text)

    def test_complete_block_is_stripped(self):
        text = "user pre\n\n" + ac.MD_BEGIN + "\nmanaged\n" + ac.MD_END + "\n\nuser post\n"
        out = ac.strip_md_block(text)
        self.assertNotIn("managed", out)
        self.assertIn("user pre", out)
        self.assertIn("user post", out)


if __name__ == "__main__":
    unittest.main()
