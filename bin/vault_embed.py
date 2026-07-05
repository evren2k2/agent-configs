"""vault_embed — semantic-search layer for the Obsidian vault.

Builds and queries a vector index over note paragraphs, complementing the BM25
`vault find`. Design notes:

- Vectors live in the vault's existing per-vault cache dir (see vault.cache_dir),
  i.e. under ~/.cache — NOT in the git repo. The 5-min sync stays conflict-free.
- Embedding is incremental and gated on a sha256 of each note's body, not mtime:
  a `git pull` that merely rewrites file mtimes must not trigger a full re-embed.
- Notes are split into section-level chunks: blank-line-separated blocks packed
  up to a word cap, but a markdown heading always starts a fresh chunk so each
  section stays independently searchable; an oversized block is hard-split.
  Each chunk carries its file path and 1-indexed line range, so search returns
  the specific passages that match a concept — multiple per note allowed. It
  reads as a semantic grep, not a note picker.
- The heavy dependency (sentence-transformers / torch) is imported lazily by
  make_encoder() — only when notes actually need (re-)embedding or a query must
  be encoded. numpy is a hard dependency of this module.

Public API: store_paths, load_store, make_encoder, chunk_note, build_vectors,
search.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

import vault

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"  # 384-dim; small, strong retrieval model
STORE_VERSION = 2
MAX_CHUNK_WORDS = 350  # word cap per chunk; stays comfortably under the ~512-token model window

# bge retrieval models are asymmetric: the *query* is prefixed with an
# instruction, documents are not. Omitted for symmetric models (e.g. MiniLM).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ---------------------------------------------------------------- store ----

def store_paths(vault_path) -> tuple[Path, Path]:
    """(vectors.npy, vectors-meta.json) inside the vault's per-vault cache dir."""
    cdir = vault.cache_dir(Path(vault_path))
    return cdir / "vectors.npy", cdir / "vectors-meta.json"


def _fresh_meta(model_name: str) -> dict:
    return {"version": STORE_VERSION, "model": model_name, "dim": 0,
            "chunks": [], "hashes": {}}


def load_store(vault_path, model_name: str = DEFAULT_MODEL):
    """Return (vectors, meta). vectors is an (N, dim) float32 ndarray, or None if
    no usable store exists (absent, corrupt, or built with a different model /
    store version). meta["chunks"] is the per-row chunk metadata list."""
    vec_path, meta_path = store_paths(vault_path)
    if not vec_path.exists() or not meta_path.exists():
        return None, _fresh_meta(model_name)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        vectors = np.load(vec_path)
    except Exception:
        return None, _fresh_meta(model_name)
    if meta.get("version") != STORE_VERSION or meta.get("model") != model_name:
        return None, _fresh_meta(model_name)
    if vectors.shape[0] != len(meta.get("chunks", [])):
        return None, _fresh_meta(model_name)  # store/meta out of sync
    return vectors, meta


def _save_store(vault_path, vectors: np.ndarray, meta: dict) -> None:
    vec_path, meta_path = store_paths(vault_path)
    # Each file is written atomically (temp in the same cache dir + os.replace) so a
    # reader never sees a torn file. The two aren't swapped as a unit, but load_store's
    # shape-count guard rejects a mismatched (vectors, meta) pair from the interleave.
    vtmp = vec_path.parent / f"{vec_path.stem}.tmp{os.getpid()}.npy"
    mtmp = meta_path.parent / f"{meta_path.name}.tmp{os.getpid()}"
    try:
        np.save(vtmp, vectors)             # vtmp already ends in .npy -> np.save won't append
        os.replace(vtmp, vec_path)
        mtmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        os.replace(mtmp, meta_path)
    except Exception:
        for t in (vtmp, mtmp):
            try:
                t.unlink()
            except OSError:
                pass
        raise


def stored_model(vault_path):
    """The model an existing store was built with (read from its meta), or None if
    no store exists. Lets a caller load a custom-model store without a model
    mismatch that would otherwise trigger a silent rebuild with DEFAULT_MODEL."""
    _, meta_path = store_paths(vault_path)
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("model")
    except Exception:
        return None


# ------------------------------------------------------------- helpers ----

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_raw(vault_path, rel_path: str) -> str:
    """Raw note text, BOM stripped. Newline normalization happens downstream."""
    return (Path(vault_path) / rel_path).read_text(encoding="utf-8-sig")


def _normalized_lines(raw_text: str) -> tuple[list[str], int]:
    """Return (lines, body_start) — newline-normalized lines and the 0-based
    index of the first body line, past a leading `---` frontmatter block."""
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines, i + 1
    return lines, 0


def _body_text(raw_text: str) -> str:
    """The note body with frontmatter removed — the input to the change hash.
    Hashing the body (not the raw file) means a frontmatter-only edit, e.g. a
    status flip, does not trigger a needless re-embed."""
    lines, start = _normalized_lines(raw_text)
    return "\n".join(lines[start:]).strip()


def chunk_note(raw_text: str, max_words: int = MAX_CHUNK_WORDS) -> list[tuple[str, int, int]]:
    """Split a raw note into paragraph-level chunks.

    Returns [(text, line_start, line_end), ...] with 1-indexed line numbers into
    the raw file (frontmatter lines counted, but excluded from chunk text).
    Blank-line-separated blocks are packed together greedily up to max_words,
    except that a markdown heading always begins a new chunk so each section is
    an independently searchable unit. A single block longer than max_words is
    hard-split into word windows (each sub-chunk keeps the block's line range).
    """
    lines, start = _normalized_lines(raw_text)

    # Blank-line-separated blocks of body text, with their 1-indexed line spans.
    blocks: list[tuple[str, int, int]] = []
    buf: list[str] = []
    buf_start: int | None = None
    for i in range(start, len(lines)):
        if lines[i].strip():
            if buf_start is None:
                buf_start = i + 1
            buf.append(lines[i])
        elif buf:
            blocks.append(("\n".join(buf), buf_start, i))  # blank at i -> last line is i
            buf, buf_start = [], None
    if buf:
        blocks.append(("\n".join(buf), buf_start, len(lines)))

    # Pack blocks up to max_words; hard-split any block that alone exceeds it.
    chunks: list[tuple[str, int, int]] = []
    pend: list[str] = []
    pend_start: int | None = None
    pend_end: int | None = None
    pend_words = 0

    def flush() -> None:
        nonlocal pend, pend_start, pend_end, pend_words
        if pend:
            chunks.append(("\n\n".join(pend), pend_start, pend_end))
        pend, pend_start, pend_end, pend_words = [], None, None, 0

    for text, ls, le in blocks:
        is_heading = text.lstrip().startswith("#")
        words = text.split()
        if len(words) > max_words:
            flush()
            for j in range(0, len(words), max_words):
                chunks.append((" ".join(words[j:j + max_words]), ls, le))
            continue
        # A heading starts a fresh chunk; otherwise pack up to the word cap.
        if pend and (is_heading or pend_words + len(words) > max_words):
            flush()
        if pend_start is None:
            pend_start = ls
        pend.append(text)
        pend_end = le
        pend_words += len(words)
    flush()
    return chunks


def _normalize(mat) -> np.ndarray:
    """L2-normalize rows so a dot product equals cosine similarity."""
    mat = np.asarray(mat, dtype="float32")
    if mat.ndim == 1:
        mat = mat.reshape(1, -1)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def make_encoder(model_name: str = DEFAULT_MODEL):
    """Return encode(texts, is_query=False) -> ndarray, backed by
    sentence-transformers. Imported lazily; raises ImportError if absent.
    Query texts get the bge instruction prefix when the model is a bge model."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    query_prefix = BGE_QUERY_PREFIX if "bge" in model_name.lower() else ""

    def encode(texts, is_query=False):
        items = list(texts)
        if is_query and query_prefix:
            items = [query_prefix + t for t in items]
        vecs = model.encode(items, convert_to_numpy=True, show_progress_bar=False)
        return np.asarray(vecs, dtype="float32")

    return encode


# --------------------------------------------------------------- build ----

def build_vectors(vault_path, index: dict, model_name: str = DEFAULT_MODEL,
                  encode=None, rebuild: bool = False) -> dict:
    """Incrementally (re-)embed the vault. Only notes whose body hash changed are
    re-chunked and re-encoded; vectors for unchanged notes are copied from the
    existing store.

    `encode` may be injected (tests pass a deterministic stub); otherwise a real
    sentence-transformers encoder is loaded lazily, and only if work is needed.
    """
    vault_path = Path(vault_path)
    if rebuild:
        old_vectors, old_meta = None, _fresh_meta(model_name)
    else:
        old_vectors, old_meta = load_store(vault_path, model_name)

    # Current raw text + body hash for every note in the index.
    current: dict[str, tuple[str, str, str]] = {}  # key -> (raw, rel_path, hash)
    for key, n in index["notes"].items():
        try:
            raw = _read_raw(vault_path, n["path"])
        except (OSError, UnicodeDecodeError):
            continue  # unreadable note — drop it from the store
        current[key] = (raw, n["path"], content_hash(_body_text(raw)))

    old_hashes = old_meta.get("hashes", {})
    old_chunks = old_meta.get("chunks", [])
    # Fall back to chunk paths for stores written before "paths" was tracked.
    old_paths = old_meta.get("paths") or {cd["key"]: cd["path"] for cd in old_chunks}
    # Unchanged only if BOTH the body hash AND the path match — a move (same
    # content, new path) must re-chunk so stored chunks carry the current path.
    unchanged = {k for k in current
                 if old_hashes.get(k) == current[k][2]
                 and old_paths.get(k) == current[k][1]}
    changed = [k for k in current if k not in unchanged]
    removed = [k for k in old_hashes if k not in current]

    if not changed and not removed and old_vectors is not None:
        return {"embedded": 0, "removed": 0, "unchanged": len(unchanged),
                "notes": len(current), "chunks": int(old_vectors.shape[0]),
                "model": model_name}

    # Chunk every changed/new note; collect chunk texts for one batched encode.
    changed_chunks: dict[str, list[dict]] = {}
    enc_texts: list[str] = []
    enc_targets: list[dict] = []  # parallel to enc_texts; the chunk dict to fill
    for k in changed:
        raw, rel_path, _ = current[k]
        cds: list[dict] = []
        for text, ls, le in chunk_note(raw):
            cd = {"key": k, "path": rel_path, "line_start": ls,
                  "line_end": le, "text": text}
            cds.append(cd)
            enc_texts.append(text)
            enc_targets.append(cd)
        changed_chunks[k] = cds

    enc = None
    if enc_texts:
        if encode is None:
            encode = make_encoder(model_name)
        enc = _normalize(encode(enc_texts))

    changed_rows: dict[str, list[tuple]] = {}  # key -> [(vector_row, chunk_dict)]
    if enc is not None:
        for i, cd in enumerate(enc_targets):
            changed_rows.setdefault(cd["key"], []).append((enc[i], cd))

    # Old rows indexed by note key, for copying unchanged notes verbatim.
    old_rows_by_key: dict[str, list[int]] = {}
    for i, cd in enumerate(old_chunks):
        old_rows_by_key.setdefault(cd["key"], []).append(i)

    # Assemble the new store: unchanged rows copied, changed rows freshly encoded.
    all_rows, all_chunks = [], []
    for key in sorted(current):
        if key in unchanged and old_vectors is not None:
            for i in old_rows_by_key.get(key, []):
                all_rows.append(old_vectors[i])
                all_chunks.append(old_chunks[i])
        else:
            for row, cd in changed_rows.get(key, []):
                all_rows.append(row)
                all_chunks.append(cd)

    if all_rows:
        new_vectors = np.vstack(all_rows).astype("float32")
        dim = int(new_vectors.shape[1])
    else:
        dim = int(old_meta.get("dim") or 0)
        new_vectors = np.zeros((0, dim), dtype="float32")

    meta = {
        "version": STORE_VERSION,
        "model": model_name,
        "dim": dim,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "chunks": all_chunks,
        "hashes": {k: current[k][2] for k in current},
        "paths": {k: current[k][1] for k in current},
    }
    _save_store(vault_path, new_vectors, meta)
    return {"embedded": len(changed), "removed": len(removed),
            "unchanged": len(unchanged), "notes": len(current),
            "chunks": int(new_vectors.shape[0]), "model": model_name}


# -------------------------------------------------------------- search ----

def search(query: str, vault_path=None, model_name: str = DEFAULT_MODEL,
           k: int = 10, encode=None, store=None) -> list[dict]:
    """Top-k note *paragraphs* by cosine similarity to `query`.

    Unlike a note-level search, several paragraphs from the same note can
    appear — that is the point: the caller wants every passage matching a
    concept, across all projects.

    Returns a list of dicts {key, path, line_start, line_end, text, score},
    score-descending. The cosine score is kept so the caller can judge match
    quality — semantic search always returns a top-k, even when nothing in the
    vault really matches. [] when no usable vector store exists.

    `store` (a preloaded (vectors, meta) tuple) and `encode` may be injected so
    a long-lived caller — the MCP server — loads model + vectors only once.
    """
    if store is None:
        store = load_store(vault_path, model_name)
    vectors, meta = store
    if vectors is None or vectors.shape[0] == 0:
        return []
    if encode is None:
        encode = make_encoder(meta.get("model") or model_name)
    q = _normalize(encode([query], is_query=True))[0]
    scores = vectors @ q
    chunks = meta["chunks"]
    order = np.argsort(-scores)[:k]
    return [dict(chunks[i], score=float(scores[i])) for i in order]
