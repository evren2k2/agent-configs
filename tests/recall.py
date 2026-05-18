#!/usr/bin/env python3
"""recall.py — compare BM25 (`vault find`) vs. semantic search on a fixed query set.

A dev tool, not a unit test: it runs against the *real* vault and the built
vector store, so it needs `vault embed` to have been run and the embedding model
present. It reports recall@5 for each method over tests/recall_cases.json.

    py -3 tests/recall.py

Expectation: semantic search wins the vocabulary-mismatch cases; BM25 wins or
ties the exact-token lookups — which is why the two tools stay separate.
"""

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import vault          # noqa: E402
import vault_embed    # noqa: E402

CASES = json.loads((Path(__file__).resolve().parent / "recall_cases.json")
                    .read_text(encoding="utf-8"))
TOPK = 5


def bm25_keys(idx, query, k):
    """Top-k note keys from the BM25 ranker, via cmd_find's JSON output."""
    class A:
        pass
    a = A()
    a.query, a.limit, a.fuzzy, a.json = [query], k, False, True
    buf = io.StringIO()
    with redirect_stdout(buf):
        vault.cmd_find(a, idx)
    return [r["key"] for r in json.loads(buf.getvalue() or "[]")]


def main():
    vroot = vault.vault_root()
    idx = vault.load_index(vroot)
    vectors, meta = vault_embed.load_store(vroot)
    have_vectors = vectors is not None
    encode = (vault_embed.make_encoder(meta.get("model") or vault_embed.DEFAULT_MODEL)
              if have_vectors else None)

    bm_hits = sem_hits = 0
    print(f"{'query':46}  BM25  SEM")
    print("-" * 64)
    for c in CASES:
        query, expected = c["query"], set(c["expected"])
        bm_ok = bool(expected & set(bm25_keys(idx, query, TOPK)))
        if have_vectors:
            # search() returns section-level chunks; dedup to distinct notes so
            # recall is measured per note — matching cmd_find's note-level output.
            sem = []
            for h in vault_embed.search(query, vault_path=vroot, k=TOPK * 10,
                                        encode=encode, store=(vectors, meta)):
                if h["key"] not in sem:
                    sem.append(h["key"])
                if len(sem) >= TOPK:
                    break
            sem_ok = bool(expected & set(sem))
        else:
            sem_ok = False
        bm_hits += bm_ok
        sem_hits += sem_ok
        print(f"{query[:46]:46}  {'HIT ' if bm_ok else 'miss'}  "
              f"{'HIT ' if sem_ok else 'miss'}")
    n = len(CASES)
    print("-" * 64)
    tail = "" if have_vectors else "   (no vector store — run `vault embed`)"
    print(f"recall@{TOPK}:  BM25 {bm_hits}/{n}   semantic {sem_hits}/{n}{tail}")


if __name__ == "__main__":
    main()
