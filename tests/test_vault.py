"""Unit tests for the vault CLI. Stdlib only (unittest).

Run from repo root:
    py -3 -m unittest tests.test_vault -v
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path


HERE = Path(__file__).resolve().parent
VAULT_SCRIPT = HERE.parent / "bin" / "vault"


def _load_vault_module():
    """Import bin/vault as a module (no .py extension)."""
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("vault_cli", str(VAULT_SCRIPT))
    spec = importlib.util.spec_from_loader("vault_cli", loader)
    if spec is None:
        raise RuntimeError(f"Cannot load {VAULT_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


vault = _load_vault_module()


# ---------------------------------------------------------------- fixtures ----

FIXTURE_NOTES: dict[str, str] = {
    "areas/agent-architecture.md": textwrap.dedent("""\
        ---
        date: 2026-05-10
        tags: [agents, langgraph, architecture]
        type: concept
        status: active
        ---
        # Agent Architecture

        This note covers patterns for building agents with LangGraph. See [[langgraph-state]].
        """),
    "areas/langgraph-state.md": textwrap.dedent("""\
        ---
        date: 2026-05-10
        tags: [langgraph, state]
        type: reference
        status: active
        ---
        # LangGraph State

        Stateful nodes communicate via shared state. Related: [[agent-architecture]].
        """),
    "projects/foo/working-context.md": textwrap.dedent("""\
        ---
        date: 2026-05-12
        tags: [foo, mission]
        type: mission
        status: active
        project: foo
        ---
        # Foo working context

        Mission for the foo project. References [[foo-design]] and [[Foo Design|aliased]].
        """),
    "projects/foo/foo-design.md": textwrap.dedent("""\
        ---
        date: 2026-05-12
        tags: [foo, design]
        type: concept
        status: active
        project: foo
        ---
        # Foo Design

        Design doc. Links to [[working-context]] (intra-project).
        """),
    "projects/bar/working-context.md": textwrap.dedent("""\
        ---
        date: 2026-05-12
        tags: [bar, mission]
        type: mission
        status: active
        project: bar
        ---
        # Bar working context

        Mission for bar. Refers to its own [[bar-notes]].
        """),
    "projects/bar/bar-notes.md": textwrap.dedent("""\
        ---
        date: 2026-05-12
        tags: [bar]
        type: concept
        status: active
        project: bar
        ---
        # Bar Notes

        Mentions [[working-context]] — should resolve to bar's, not foo's.
        """),
    "inbox/orphan.md": textwrap.dedent("""\
        ---
        date: 2026-05-13
        tags: [misc]
        type: concept
        status: active
        ---
        # Orphan

        Nothing links here. But this note links to [[agent-architecture]].
        """),
    "inbox/bom-test.md": "﻿" + textwrap.dedent("""\
        ---
        date: 2026-05-13
        tags: [misc]
        type: concept
        status: active
        ---
        # BOM Test

        UTF-8 BOM at start — must still parse. Links to [[agent-architecture]].
        """),
}


def _write_fixture(root: Path) -> None:
    for rel, content in FIXTURE_NOTES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- tests ----

class FrontmatterTests(unittest.TestCase):
    def test_parses_inline_array_tags(self):
        text = "---\ntags: [a, b, c]\ntype: concept\n---\nbody"
        fm, body = vault.parse_frontmatter(text)
        self.assertEqual(fm["tags"], ["a", "b", "c"])
        self.assertEqual(fm["type"], "concept")
        self.assertEqual(body, "body")

    def test_missing_frontmatter_returns_empty(self):
        fm, body = vault.parse_frontmatter("just a note\nwithout fm")
        self.assertEqual(fm, {})
        self.assertTrue(body.startswith("just"))

    def test_handles_quoted_values(self):
        text = '---\ntype: "concept"\nproject: \'foo\'\n---\nx'
        fm, _ = vault.parse_frontmatter(text)
        self.assertEqual(fm["type"], "concept")
        self.assertEqual(fm["project"], "foo")


class WikilinkExtractionTests(unittest.TestCase):
    def test_simple(self):
        out = vault.extract_wikilinks("see [[note-a]] for more")
        self.assertEqual(out, [("note-a", None)])

    def test_alias(self):
        out = vault.extract_wikilinks("see [[note-a|Note A]]")
        self.assertEqual(out, [("note-a", None)])

    def test_fragment_and_block(self):
        out = vault.extract_wikilinks("[[note#section]] [[other^block]]")
        self.assertEqual(out, [("note", None), ("other", None)])

    def test_folder_prefix_kept_as_hint(self):
        out = vault.extract_wikilinks("[[foo/working-context]]")
        self.assertEqual(out, [("working-context", "foo")])

    def test_normalization(self):
        out = vault.extract_wikilinks("[[My Note]] [[Some_Other]]")
        self.assertEqual(out, [("my-note", None), ("some-other", None)])


class NormalizeKeyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(vault.normalize_key("My Note"), "my-note")
        self.assertEqual(vault.normalize_key("some_thing.md"), "some-thing")
        self.assertEqual(vault.normalize_key("ALREADY-fine"), "already-fine")


class IndexBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vault-test-"))
        _write_fixture(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_index_counts(self):
        idx = vault.build_index(self.tmp)
        # 8 fixture files, but two share the stem "working-context"
        self.assertEqual(len(idx["notes"]), 8)

    def test_collision_qualified_keys(self):
        idx = vault.build_index(self.tmp)
        self.assertIn("foo/working-context", idx["notes"])
        self.assertIn("bar/working-context", idx["notes"])
        self.assertNotIn("working-context", idx["notes"])

    def test_wikilink_resolves_to_same_folder_on_ambiguity(self):
        idx = vault.build_index(self.tmp)
        bar_notes = idx["notes"]["bar-notes"]
        # bar-notes contains [[working-context]] — must resolve to bar/working-context
        self.assertIn("bar/working-context", bar_notes["forward_links"])
        self.assertNotIn("foo/working-context", bar_notes["forward_links"])

    def test_wikilink_with_explicit_folder_hint(self):
        idx = vault.build_index(self.tmp)
        # Add a note with explicit [[foo/working-context]] hint
        (self.tmp / "areas" / "cross-link.md").write_text(textwrap.dedent("""\
            ---
            date: 2026-05-13
            tags: [misc]
            type: concept
            status: active
            ---
            # Cross
            Uses [[foo/working-context]] explicitly.
            """), encoding="utf-8")
        idx = vault.build_index(self.tmp)
        cross = idx["notes"]["cross-link"]
        self.assertIn("foo/working-context", cross["forward_links"])

    def test_backlinks_computed(self):
        idx = vault.build_index(self.tmp)
        # foo-design is linked to from foo/working-context
        self.assertIn("foo/working-context", idx["backlinks"].get("foo-design", []))
        # agent-architecture is linked to from langgraph-state, orphan, bom-test
        self.assertEqual(
            set(idx["backlinks"]["agent-architecture"]),
            {"langgraph-state", "orphan", "bom-test"},
        )

    def test_orphans(self):
        idx = vault.build_index(self.tmp)
        # "orphan" links out but nothing links to it
        self.assertNotIn("orphan", idx["backlinks"])
        # bom-test similarly
        self.assertNotIn("bom-test", idx["backlinks"])

    def test_project_index(self):
        idx = vault.build_index(self.tmp)
        self.assertEqual(set(idx["project_index"]["foo"]), {"foo/working-context", "foo-design"})
        self.assertEqual(set(idx["project_index"]["bar"]), {"bar/working-context", "bar-notes"})

    def test_folder_project_index(self):
        idx = vault.build_index(self.tmp)
        self.assertEqual(set(idx["folder_project_index"]["foo"]), {"foo/working-context", "foo-design"})

    def test_tag_index(self):
        idx = vault.build_index(self.tmp)
        self.assertIn("agent-architecture", idx["tag_index"]["agents"])
        self.assertIn("langgraph-state", idx["tag_index"]["langgraph"])

    def test_bom_handled(self):
        idx = vault.build_index(self.tmp)
        n = idx["notes"]["bom-test"]
        self.assertEqual(n["frontmatter"]["type"], "concept")
        self.assertEqual(n["frontmatter"]["status"], "active")


class FindRankingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vault-test-"))
        _write_fixture(self.tmp)
        self.idx = vault.build_index(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _find(self, q, limit=5):
        class A:
            pass
        a = A()
        a.query = [q]
        a.limit = limit
        a.fuzzy = False
        a.json = True
        buf = io.StringIO()
        with redirect_stdout(buf):
            vault.cmd_find(a, self.idx)
        return json.loads(buf.getvalue())

    def test_filename_match_ranks_first(self):
        results = self._find("foo design")
        self.assertTrue(results)
        self.assertEqual(results[0]["key"], "foo-design")

    def test_tag_match_picks_up(self):
        results = self._find("langgraph")
        keys = [r["key"] for r in results]
        self.assertIn("langgraph-state", keys)
        self.assertIn("agent-architecture", keys)

    def test_no_results_empty(self):
        results = self._find("zzz-nonexistent-token")
        self.assertEqual(results, [])


class CommandIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vault-test-"))
        _write_fixture(self.tmp)
        # Isolate the cache too
        self.cache = Path(tempfile.mkdtemp(prefix="vault-cache-"))
        self._orig_xdg = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(self.cache)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.cache, ignore_errors=True)
        if self._orig_xdg is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self._orig_xdg

    def _run(self, *args):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = vault.main(["--vault", str(self.tmp), *args])
        return rc, out.getvalue(), err.getvalue()

    def test_stats_json(self):
        rc, out, _ = self._run("stats", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["total"], 8)

    def test_project_json(self):
        rc, out, _ = self._run("project", "foo", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        keys = {d["key"] for d in data}
        self.assertEqual(keys, {"foo/working-context", "foo-design"})

    def test_links_qualified(self):
        rc, out, _ = self._run("links", "foo/working-context", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("foo-design", data["out"])

    def test_neighbors_depth_1(self):
        rc, out, _ = self._run("neighbors", "agent-architecture", "--depth", "1", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        neighbors = set(data["by_depth"]["1"])
        # Should include all direct neighbors (linkers + linkees)
        self.assertIn("langgraph-state", neighbors)
        self.assertIn("orphan", neighbors)

    def test_show_not_found(self):
        rc, _, err = self._run("show", "nonexistent-note")
        self.assertEqual(rc, 1)
        self.assertIn("Not found", err)

    def test_orphans_json(self):
        rc, out, _ = self._run("orphans", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        keys = {d["key"] for d in data}
        # `orphan` and `bom-test` link out but have no incoming links
        self.assertIn("orphan", keys)
        self.assertIn("bom-test", keys)

    def test_deletion_invalidates_cache(self):
        # Prime the cache
        rc, out, _ = self._run("stats", "--json")
        self.assertEqual(rc, 0)
        before = json.loads(out)["total"]
        # Delete a note and re-run
        (self.tmp / "inbox" / "orphan.md").unlink()
        rc, out, _ = self._run("stats", "--json")
        self.assertEqual(rc, 0)
        after = json.loads(out)["total"]
        self.assertEqual(after, before - 1)
        # Verify it's also reflected on disk (next invocation reads the persisted index)
        rc, out, _ = self._run("show", "orphan")
        self.assertEqual(rc, 1)  # not found


if __name__ == "__main__":
    unittest.main()
