"""Unit tests for vault_embed — the semantic-search layer.

These run offline and deterministically with a stub bag-of-words encoder; no
model is downloaded. The real sentence-transformers end-to-end check is gated
behind the VAULT_EMBED_E2E env var so the default suite stays fast and offline.

Run from repo root:
    py -3 -m unittest tests.test_embed -v
    # opt-in real-model check (downloads the model on first run):
    VAULT_EMBED_E2E=1 py -3 -m unittest tests.test_embed -v
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import vault          # noqa: E402
import vault_embed    # noqa: E402

try:
    import sentence_transformers  # noqa: F401
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False


# ----------------------------------------------------------- stub encoder ----

def stub_encode(texts, dim=64, is_query=False):
    """Deterministic bag-of-words encoder: texts that share words land in the
    same buckets, so cosine ranking is meaningful — but no model is loaded.
    Stand-in for sentence-transformers in the incremental/search logic tests.
    `is_query` is accepted to match the real encoder contract; ignored here
    (bag-of-words is symmetric)."""
    import numpy as np
    out = np.zeros((len(texts), dim), dtype="float32")
    for i, t in enumerate(texts):
        for tok in t.lower().split():
            b = int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim
            out[i, b] += 1.0
    return out


def _note(title: str, body: str) -> str:
    return f"---\ntags: [t]\ntype: concept\nstatus: active\n---\n# {title}\n\n{body}\n"


FIXTURES = {
    "areas/accelerator.md": _note(
        "Accelerator", "Matrix multiply datapath for neural network inference."),
    "areas/cooking.md": _note(
        "Cooking", "Roasting vegetables and braising meat for a slow dinner."),
    "areas/long-note.md": _note("Long Note", "word " * 900),
}


# --------------------------------------------------------------- chunking ----

class ChunkTests(unittest.TestCase):
    # Body blocks sit at known raw-file line numbers — frontmatter is lines 1-5.
    LINE_FIXTURE = (
        "---\n"                              # 1
        "tags: [t]\n"                        # 2
        "type: concept\n"                    # 3
        "status: active\n"                   # 4
        "---\n"                              # 5
        "# Heading One\n"                    # 6
        "\n"                                 # 7
        "Alpha alpha alpha alpha alpha.\n"   # 8
        "\n"                                 # 9
        "## Heading Two\n"                   # 10
        "\n"                                 # 11
        "Beta beta beta beta beta.\n"        # 12
    )

    def test_paragraph_chunks_carry_exact_line_numbers(self):
        # max_words=5 keeps each body block its own chunk -> exact spans.
        chunks = vault_embed.chunk_note(self.LINE_FIXTURE, max_words=5)
        spans = [(ls, le) for _, ls, le in chunks]
        self.assertEqual(spans, [(6, 6), (8, 8), (10, 10), (12, 12)])
        self.assertEqual(chunks[0][0], "# Heading One")
        self.assertIn("Alpha", chunks[1][0])

    def test_headings_start_new_chunks(self):
        # Even with a cap generous enough to pack everything, each heading must
        # begin a fresh chunk — so the two sections stay independently
        # searchable — while a heading still packs with the prose under it.
        chunks = vault_embed.chunk_note(self.LINE_FIXTURE, max_words=50)
        spans = [(ls, le) for _, ls, le in chunks]
        self.assertEqual(spans, [(6, 8), (10, 12)])
        self.assertTrue(chunks[0][0].startswith("# Heading One"))
        self.assertIn("Alpha", chunks[0][0])
        self.assertTrue(chunks[1][0].startswith("## Heading Two"))

    def test_oversized_block_is_hard_split(self):
        raw = "---\ntags: [t]\n---\n" + ("word " * 20).strip() + "\n"
        chunks = vault_embed.chunk_note(raw, max_words=7)
        self.assertEqual(len(chunks), 3)  # 20 words / 7
        # every sub-chunk keeps the original block's line range
        self.assertTrue(all((ls, le) == (4, 4) for _, ls, le in chunks))

    def test_empty_body_no_chunks(self):
        self.assertEqual(vault_embed.chunk_note("---\ntags: [t]\n---\n"), [])
        self.assertEqual(vault_embed.chunk_note(""), [])
        self.assertEqual(vault_embed.chunk_note("   "), [])


# ---------------------------------------------------------------- harness ----

class EmbedTestCase(unittest.TestCase):
    """Temp vault + isolated cache (XDG_CACHE_HOME) so the store never touches
    the real vault cache."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vault-embed-"))
        self.cache = Path(tempfile.mkdtemp(prefix="vault-embed-cache-"))
        self._orig_xdg = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(self.cache)
        for rel, content in FIXTURES.items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.cache, ignore_errors=True)
        if self._orig_xdg is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self._orig_xdg

    def build(self, **kw):
        kw.setdefault("encode", stub_encode)
        return vault_embed.build_vectors(self.tmp, vault.build_index(self.tmp), **kw)


# ----------------------------------------------------------- incremental ----

class IncrementalTests(EmbedTestCase):
    def test_first_build_embeds_all(self):
        stats = self.build()
        self.assertEqual(stats["embedded"], len(FIXTURES))
        self.assertEqual(stats["removed"], 0)

    def test_second_build_is_noop(self):
        self.build()
        stats = self.build()  # nothing changed on disk
        self.assertEqual(stats["embedded"], 0)
        self.assertEqual(stats["unchanged"], len(FIXTURES))

    def test_changed_note_reembeds_only_one(self):
        self.build()
        (self.tmp / "areas/cooking.md").write_text(
            FIXTURES["areas/cooking.md"] + "\nAn extra paragraph was appended.\n",
            encoding="utf-8")
        stats = self.build()
        self.assertEqual(stats["embedded"], 1)
        self.assertEqual(stats["unchanged"], len(FIXTURES) - 1)

    def test_deleted_note_is_dropped(self):
        self.build()
        (self.tmp / "areas/cooking.md").unlink()
        stats = self.build()
        self.assertEqual(stats["removed"], 1)
        _, meta = vault_embed.load_store(self.tmp)
        self.assertNotIn("cooking", {c["key"] for c in meta["chunks"]})
        self.assertNotIn("cooking", meta["hashes"])

    def test_rebuild_flag_reembeds_all(self):
        self.build()
        stats = self.build(rebuild=True)
        self.assertEqual(stats["embedded"], len(FIXTURES))
        self.assertEqual(stats["unchanged"], 0)

    def test_moved_note_updates_stored_path(self):
        # Same content, new path (unique-stem key unchanged): must re-chunk so the
        # stored chunks carry the new path instead of serving the old one forever.
        self.build()
        (self.tmp / "areas/hw").mkdir(parents=True, exist_ok=True)
        (self.tmp / "areas/accelerator.md").rename(self.tmp / "areas/hw/accelerator.md")
        stats = self.build()
        self.assertEqual(stats["embedded"], 1)          # re-embedded despite same body
        _, meta = vault_embed.load_store(self.tmp)
        acc_paths = {c["path"] for c in meta["chunks"] if c["key"] == "accelerator"}
        self.assertEqual(acc_paths, {"areas/hw/accelerator.md"})
        self.assertEqual(meta["paths"]["accelerator"], "areas/hw/accelerator.md")


# ---------------------------------------------------------------- search ----

class SearchTests(EmbedTestCase):
    def test_relevant_note_ranks_first(self):
        self.build()
        hits = vault_embed.search("neural network inference datapath",
                                  vault_path=self.tmp, encode=stub_encode)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["key"], "accelerator")

    def test_hits_carry_location_and_text(self):
        self.build()
        hits = vault_embed.search("neural network", vault_path=self.tmp,
                                  encode=stub_encode)
        h = hits[0]
        for field in ("key", "path", "line_start", "line_end", "text", "score"):
            self.assertIn(field, h)
        self.assertEqual(h["path"], "areas/accelerator.md")
        self.assertGreaterEqual(h["line_start"], 1)

    def test_multiple_paragraphs_from_one_note_can_match(self):
        self.build()
        # long-note is 900 words → hard-split into several chunks; a query that
        # matches them all must return more than one row for that note. (The
        # old behaviour deduped to one note per hit — the opposite of the goal.)
        hits = vault_embed.search("word", vault_path=self.tmp,
                                  encode=stub_encode, k=10)
        keys = [h["key"] for h in hits]
        self.assertGreaterEqual(keys.count("long-note"), 2)
        self.assertEqual(hits[0]["key"], "long-note")

    def test_empty_store_returns_nothing(self):
        # no build() → no vector store on disk
        hits = vault_embed.search("anything", vault_path=self.tmp, encode=stub_encode)
        self.assertEqual(hits, [])


# ----------------------------------------------------- real model (opt-in) ----

@unittest.skipUnless(_ST_AVAILABLE and os.environ.get("VAULT_EMBED_E2E"),
                     "set VAULT_EMBED_E2E=1 with sentence-transformers installed")
class RealModelTest(EmbedTestCase):
    def test_end_to_end_with_real_encoder(self):
        stats = self.build(encode=None)  # real sentence-transformers encoder
        self.assertEqual(stats["embedded"], len(FIXTURES))
        hits = vault_embed.search("hardware for machine learning",
                                  vault_path=self.tmp)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["key"], "accelerator")  # semantic, not lexical, match
        for h in hits:
            self.assertGreaterEqual(h["score"], -1.001)
            self.assertLessEqual(h["score"], 1.001)


if __name__ == "__main__":
    unittest.main()
