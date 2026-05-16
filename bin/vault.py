#!/usr/bin/env python3
"""vault — graph-aware CLI for an Obsidian vault.

Subcommands:
  stats                          Vault overview
  find <query>                   Lexical (BM25-ish) ranker over notes
  query [--tag --status --type --project]
                                 Frontmatter filter
  project <name>                 Notes with `project: <name>` frontmatter
  tag <tag>                      Notes carrying a tag
  recent [--days N]              Recently modified notes
  orphans                        Notes with no incoming links
  show <note>                    Frontmatter + link counts + first paragraph
  links <note> [--to|--from]     Backlinks / forward links
  neighbors <note> [--depth N]   BFS k-hop neighborhood
  path <a> <b>                   Shortest wikilink path
  index [--rebuild]              Inspect / rebuild the cached index

Index is cached per-vault at $XDG_CACHE_HOME/agent-vault/<hash>/index.json.
Stdlib only; no external dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

INDEX_VERSION = 2
DEFAULT_VAULT = Path.home() / "obsidian_notes"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
STOPWORDS = {
    "the","a","an","of","in","on","at","to","for","and","or","is","are","was",
    "were","be","this","that","it","as","by","with","from","vs","not","no",
}


# ---------------------------------------------------------------- paths ----

def vault_root(override: str | None = None) -> Path:
    return Path(override or os.environ.get("VAULT_PATH") or DEFAULT_VAULT).expanduser().resolve()

def cache_dir(vault: Path) -> Path:
    h = hashlib.sha256(str(vault).encode("utf-8")).hexdigest()[:12]
    base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
    d = base / "agent-vault" / h
    d.mkdir(parents=True, exist_ok=True)
    return d

def index_path(vault: Path) -> Path:
    return cache_dir(vault) / "index.json"


# ---------------------------------------------------------------- parse ----

def normalize_key(s: str) -> str:
    """Canonical key for a note: lowercase, hyphenated, no extension."""
    s = s.strip()
    if s.lower().endswith(".md"):
        s = s[:-3]
    return s.lower().replace(" ", "-").replace("_", "-")

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Shallow YAML-ish parser. Handles only the subset used by this vault:
    scalar values and inline arrays `[a, b, c]`.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    block, body = m.group(1), text[m.end():]
    fm: dict = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line.strip() or ":" not in line or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            continue  # nested keys not supported; skip
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if not v:
            continue
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            items = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            fm[k] = items
        else:
            fm[k] = v.strip('"').strip("'")
    return fm, body

def extract_wikilinks(body: str) -> list[tuple[str, str | None]]:
    """Return list of (stem, folder_hint) tuples. folder_hint is the explicit
    folder from [[folder/note]] if given, else None.
    """
    out: list[tuple[str, str | None]] = []
    for m in WIKILINK_RE.finditer(body):
        raw = m.group(1).strip()
        raw = raw.split("|", 1)[0]
        raw = raw.split("#", 1)[0]
        raw = raw.split("^", 1)[0]
        raw = raw.strip()
        if not raw:
            continue
        folder_hint: str | None = None
        if "/" in raw:
            parts = raw.split("/")
            folder_hint = normalize_key(parts[-2]) if len(parts) >= 2 else None
            raw = parts[-1]
        stem = normalize_key(raw)
        if stem:
            out.append((stem, folder_hint))
    return out

def extract_title(body: str) -> str | None:
    m = H1_RE.search(body)
    return m.group(1).strip() if m else None

def first_paragraph(body: str, max_chars: int = 320) -> str:
    for chunk in re.split(r"\n\s*\n", body.strip()):
        chunk = chunk.strip()
        if not chunk or chunk.startswith("#"):
            continue
        cleaned = re.sub(r"\s+", " ", chunk)
        return cleaned[:max_chars]
    return ""


# ---------------------------------------------------------------- index ----

def scan_vault(vault: Path):
    for path in vault.rglob("*.md"):
        rel = path.relative_to(vault)
        if any(part.startswith(".") for part in rel.parts[:-1]):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        yield path, mtime

def parse_note(path: Path, vault: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    # Normalize CRLF → LF so frontmatter regex matches cleanly.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    fm, body = parse_frontmatter(text)
    title = extract_title(body) or path.stem
    rel = str(path.relative_to(vault)).replace("\\", "/")
    if not isinstance(fm.get("tags"), list):
        fm["tags"] = []
    raw_links = extract_wikilinks(body)
    return {
        "path": rel,
        "mtime": path.stat().st_mtime,
        "title": title,
        "frontmatter": fm,
        "_raw_links": raw_links,
        "first_paragraph": first_paragraph(body),
    }

def _parent_folder(rel_path: str) -> str:
    """Last folder component of a vault-relative path, normalized. Empty string for root files."""
    parts = rel_path.split("/")
    return normalize_key(parts[-2]) if len(parts) >= 2 else ""

def _assign_keys(files: list[tuple[Path, float, Path]]) -> tuple[dict[Path, str], dict[str, list[str]]]:
    """Decide a canonical key per file. Qualify with parent folder only on stem collision.
    Returns (path -> key) and (bare_stem -> [canonical_keys]) for wikilink resolution.
    """
    by_stem: dict[str, list[tuple[Path, Path]]] = defaultdict(list)
    for path, _, rel in files:
        by_stem[normalize_key(path.stem)].append((path, rel))

    path_to_key: dict[Path, str] = {}
    stem_to_keys: dict[str, list[str]] = defaultdict(list)
    for stem, items in by_stem.items():
        if len(items) == 1:
            path, _rel = items[0]
            path_to_key[path] = stem
            stem_to_keys[stem].append(stem)
        else:
            for path, rel in items:
                parts = str(rel).replace("\\", "/").split("/")
                parent = normalize_key(parts[-2]) if len(parts) >= 2 else ""
                key = f"{parent}/{stem}" if parent else stem
                path_to_key[path] = key
                stem_to_keys[stem].append(key)
    return path_to_key, stem_to_keys

def _resolve_link(stem: str, folder_hint: str | None, source_folder: str,
                  stem_to_keys: dict[str, list[str]]) -> str:
    """Map a raw wikilink (stem, folder_hint) to a canonical key."""
    candidates = stem_to_keys.get(stem, [])
    if not candidates:
        # Unresolved (broken link or note doesn't exist). Keep raw stem.
        return stem
    if len(candidates) == 1:
        return candidates[0]
    # Disambiguate
    if folder_hint:
        for c in candidates:
            if "/" in c and c.split("/", 1)[0] == folder_hint:
                return c
    if source_folder:
        for c in candidates:
            if "/" in c and c.split("/", 1)[0] == source_folder:
                return c
    return candidates[0]

def build_index(vault: Path, existing: dict | None = None, verbose: bool = False) -> dict:
    files: list[tuple[Path, float, Path]] = []
    for path, mtime in scan_vault(vault):
        files.append((path, mtime, path.relative_to(vault)))
    path_to_key, stem_to_keys = _assign_keys(files)

    prev_notes = (existing or {}).get("notes", {}) if existing else {}
    new_notes: dict[str, dict] = {}
    changed = 0
    for path, mtime, rel in files:
        key = path_to_key[path]
        rel_s = str(rel).replace("\\", "/")
        prev = prev_notes.get(key)
        if prev and prev.get("path") == rel_s and abs(prev.get("mtime", 0) - mtime) < 0.5:
            new_notes[key] = prev
            continue
        parsed = parse_note(path, vault)
        if parsed:
            new_notes[key] = parsed
            changed += 1
            if verbose:
                print(f"  reparsed: {rel_s}", file=sys.stderr)

    # Resolve wikilinks against the full key vocabulary
    for key, n in new_notes.items():
        source_folder = _parent_folder(n["path"])
        raw = n.get("_raw_links") or []
        resolved: list[str] = []
        for entry in raw:
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                stem, hint = entry
            else:
                # Older cached entries may be bare strings; treat as no hint.
                stem, hint = entry, None
            resolved.append(_resolve_link(stem, hint, source_folder, stem_to_keys))
        # de-dup while preserving order
        seen: set[str] = set()
        n["forward_links"] = [x for x in resolved if not (x in seen or seen.add(x))]

    backlinks: dict[str, list[str]] = defaultdict(list)
    for key, n in new_notes.items():
        for target in n["forward_links"]:
            if target and target != key:
                backlinks[target].append(key)
    backlinks_clean = {k: sorted(set(v)) for k, v in backlinks.items()}

    tag_index: dict[str, list[str]] = defaultdict(list)
    project_index: dict[str, list[str]] = defaultdict(list)
    folder_project_index: dict[str, list[str]] = defaultdict(list)
    for key, n in new_notes.items():
        for tag in n["frontmatter"].get("tags", []) or []:
            if isinstance(tag, str):
                tag_index[tag.lower()].append(key)
        proj = n["frontmatter"].get("project")
        if proj:
            project_index[proj].append(key)
        # Folder-based fallback: notes under projects/<name>/ get grouped by folder name
        parts = n["path"].split("/")
        if len(parts) >= 3 and parts[0] == "projects":
            folder_project_index[parts[1]].append(key)

    return {
        "version": INDEX_VERSION,
        "vault_path": str(vault),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "notes": new_notes,
        "backlinks": backlinks_clean,
        "tag_index": {k: sorted(set(v)) for k, v in tag_index.items()},
        "project_index": {k: sorted(set(v)) for k, v in project_index.items()},
        "folder_project_index": {k: sorted(set(v)) for k, v in folder_project_index.items()},
        "_changed": changed,
    }

def load_index(vault: Path, force_rebuild: bool = False, verbose: bool = False) -> dict:
    path = index_path(vault)
    existing: dict | None = None
    if not force_rebuild and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") == INDEX_VERSION and data.get("vault_path") == str(vault):
                existing = data
        except Exception:
            existing = None
    idx = build_index(vault, existing=existing, verbose=verbose)
    prev_keys = set((existing or {}).get("notes", {}).keys())
    new_keys = set(idx["notes"].keys())
    deleted = prev_keys - new_keys
    if existing is None or idx["_changed"] > 0 or deleted or force_rebuild:
        # Strip transient fields before persisting.
        to_persist = {k: v for k, v in idx.items() if k != "_changed"}
        path.write_text(json.dumps(to_persist, indent=2, default=str), encoding="utf-8")
        if verbose:
            print(f"Index written ({idx['_changed']} reparsed, {len(deleted)} removed): {path}", file=sys.stderr)
    return idx


# ---------------------------------------------------------------- query ----

def resolve_key(idx: dict, name: str) -> str | None:
    # Accept "folder/note" qualified keys or bare stems.
    if "/" in name:
        k = "/".join(normalize_key(p) for p in name.split("/"))
    else:
        k = normalize_key(name)
    if k in idx["notes"]:
        return k
    # Try bare stem against all qualified keys
    matches = [nk for nk in idx["notes"] if nk.rsplit("/", 1)[-1] == k]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous: '{name}' matches {matches}. Qualify with folder/note.", file=sys.stderr)
        return None
    # Try title match
    for nk, n in idx["notes"].items():
        if normalize_key(n.get("title") or "") == k:
            return nk
    return None

def tokenize(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t and t not in STOPWORDS]


# --------------------------------------------------------------- output ----

def fmt_note_line(key: str, n: dict, in_c: int, out_c: int) -> str:
    fm = n.get("frontmatter") or {}
    bits: list[str] = [fm.get("type", "?"), fm.get("status", "?")]
    if fm.get("project"):
        bits.append(f"@{fm['project']}")
    tags = ",".join((fm.get("tags") or [])[:3])
    if tags:
        bits.append(f"#{tags}")
    return f"  {key}  ({n['path']})  [{in_c}in/{out_c}out]\n    " + " • ".join(bits)

def emit_keys(args, idx, keys, header):
    if getattr(args, "json", False):
        out = []
        for k in keys:
            n = idx["notes"][k]
            out.append({
                "key": k,
                "path": n["path"],
                "title": n.get("title"),
                "frontmatter": n["frontmatter"],
                "in_count": len(idx["backlinks"].get(k, [])),
                "out_count": len(n["forward_links"]),
            })
        print(json.dumps(out, indent=2))
        return
    print(header + "\n")
    for k in keys:
        n = idx["notes"][k]
        in_c = len(idx["backlinks"].get(k, []))
        out_c = len(n["forward_links"])
        print(fmt_note_line(k, n, in_c, out_c))


# ----------------------------------------------------------- subcommands ----

def cmd_stats(args, idx):
    notes = idx["notes"]
    by_folder: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    by_status: dict[str, int] = defaultdict(int)
    for n in notes.values():
        parts = n["path"].split("/")
        by_folder["(root)" if len(parts) == 1 else parts[0]] += 1
        by_type[n["frontmatter"].get("type", "?")] += 1
        by_status[n["frontmatter"].get("status", "?")] += 1
    top_tags = sorted(
        ((t, len(ks)) for t, ks in idx["tag_index"].items()), key=lambda x: -x[1]
    )[:10]
    orphans = [k for k in notes if k not in idx["backlinks"]]
    out = {
        "total": len(notes),
        "by_folder": dict(by_folder),
        "by_type": dict(by_type),
        "by_status": dict(by_status),
        "top_tags": dict(top_tags),
        "orphan_count": len(orphans),
        "index_path": str(index_path(Path(idx["vault_path"]))),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"Vault: {idx['vault_path']}")
    print(f"Total notes: {out['total']}")
    print(f"By folder:  {dict(by_folder)}")
    print(f"By type:    {dict(by_type)}")
    print(f"By status:  {dict(by_status)}")
    print(f"Top tags:   {top_tags[:5]}")
    print(f"Orphans:    {len(orphans)}")
    print(f"Index:      {out['index_path']}")

def cmd_project(args, idx):
    fm_keys = set(idx["project_index"].get(args.name, []))
    folder_keys = set(idx.get("folder_project_index", {}).get(args.name, []))
    keys = sorted(fm_keys | folder_keys)
    if not keys:
        print(f"No notes for project: {args.name}", file=sys.stderr)
        return 1

    if args.json:
        out = []
        for k in keys:
            n = idx["notes"][k]
            out.append({
                "key": k, "path": n["path"], "title": n.get("title"),
                "frontmatter": n["frontmatter"],
                "in_links": idx["backlinks"].get(k, []),
                "out_links": n["forward_links"],
                "frontmatter_project_match": k in fm_keys,
                "folder_match": k in folder_keys,
            })
        print(json.dumps(out, indent=2))
        return

    only_folder = folder_keys - fm_keys
    print(f"# project: {args.name} ({len(keys)} notes)")
    if only_folder:
        print(f"  ({len(only_folder)} found by folder only — missing `project:` frontmatter)")
    print()
    grouped: dict[str, list[str]] = defaultdict(list)
    for k in keys:
        grouped[idx["notes"][k]["frontmatter"].get("status", "?")].append(k)
    for status in sorted(grouped):
        print(f"## status: {status}")
        for k in sorted(grouped[status]):
            n = idx["notes"][k]
            marker = "" if k in fm_keys else "  [no fm]"
            print(fmt_note_line(k, n, len(idx["backlinks"].get(k, [])), len(n["forward_links"])) + marker)
        print()

def cmd_tag(args, idx):
    keys = sorted(idx["tag_index"].get(args.tag.lower(), []))
    emit_keys(args, idx, keys, f"# tag: {args.tag} ({len(keys)} notes)")

def cmd_query(args, idx):
    keys = []
    for key, n in idx["notes"].items():
        fm = n["frontmatter"]
        if args.tag and args.tag.lower() not in {t.lower() for t in (fm.get("tags") or [])}:
            continue
        if args.status and fm.get("status") != args.status:
            continue
        if args.type and fm.get("type") != args.type:
            continue
        if args.project and fm.get("project") != args.project:
            continue
        keys.append(key)
    keys.sort()
    if args.limit:
        keys = keys[: args.limit]
    parts = [
        f"tag={args.tag}" if args.tag else None,
        f"status={args.status}" if args.status else None,
        f"type={args.type}" if args.type else None,
        f"project={args.project}" if args.project else None,
    ]
    desc = " ".join(p for p in parts if p) or "(all)"
    emit_keys(args, idx, keys, f"# query {desc} → {len(keys)} notes")

def cmd_recent(args, idx):
    cutoff = time.time() - args.days * 86400
    keys = [k for k, n in idx["notes"].items() if n.get("mtime", 0) >= cutoff]
    keys.sort(key=lambda k: -idx["notes"][k]["mtime"])
    if args.limit:
        keys = keys[: args.limit]
    emit_keys(args, idx, keys, f"# recent (last {args.days}d) → {len(keys)} notes")

def cmd_orphans(args, idx):
    keys = sorted(k for k in idx["notes"] if k not in idx["backlinks"])
    emit_keys(args, idx, keys, f"# orphans ({len(keys)} notes with no incoming links)")

def cmd_show(args, idx):
    key = resolve_key(idx, args.note)
    if not key:
        print(f"Not found: {args.note}", file=sys.stderr)
        return 1
    n = idx["notes"][key]
    in_links = idx["backlinks"].get(key, [])
    if args.json:
        print(json.dumps({
            "key": key, "path": n["path"], "title": n.get("title"),
            "frontmatter": n["frontmatter"],
            "in_links": in_links,
            "out_links": n["forward_links"],
            "first_paragraph": n.get("first_paragraph", ""),
        }, indent=2))
        return
    print(f"# {n.get('title') or key}")
    print(f"path:        {n['path']}")
    print(f"frontmatter: {n['frontmatter']}")
    print(f"in_links  ({len(in_links)}): {in_links}")
    print(f"out_links ({len(n['forward_links'])}): {n['forward_links']}")
    if n.get("first_paragraph"):
        print(f"\n{n['first_paragraph']}")

def cmd_links(args, idx):
    key = resolve_key(idx, args.note)
    if not key:
        print(f"Not found: {args.note}", file=sys.stderr)
        return 1
    out_links = idx["notes"][key]["forward_links"]
    in_links = idx["backlinks"].get(key, [])
    # --to suppresses out-links; --from suppresses in-links. Default: show both.
    show_in = not args.from_only
    show_out = not args.to_only
    result: dict[str, list[str]] = {}
    if show_in:
        result["in"] = in_links
    if show_out:
        result["out"] = out_links
    if args.json:
        print(json.dumps(result, indent=2))
        return
    if "in" in result:
        print(f"# {key} ← in ({len(result['in'])})")
        for k in result["in"]:
            print(f"  {k}")
        print()
    if "out" in result:
        print(f"# {key} → out ({len(result['out'])})")
        for k in result["out"]:
            print(f"  {k}")

def cmd_neighbors(args, idx):
    key = resolve_key(idx, args.note)
    if not key:
        print(f"Not found: {args.note}", file=sys.stderr)
        return 1
    visited = {key: 0}
    queue: deque = deque([(key, 0)])
    while queue:
        cur, d = queue.popleft()
        if d >= args.depth:
            continue
        nbs = set(idx["notes"].get(cur, {}).get("forward_links", [])) | set(idx["backlinks"].get(cur, []))
        for nb in nbs:
            if nb in idx["notes"] and nb not in visited:
                visited[nb] = d + 1
                queue.append((nb, d + 1))
    by_depth: dict[int, list[str]] = defaultdict(list)
    for k, d in visited.items():
        if k != key:
            by_depth[d].append(k)
    if args.json:
        print(json.dumps({"center": key, "by_depth": {str(d): sorted(ks) for d, ks in by_depth.items()}}, indent=2))
        return
    print(f"# neighbors of {key} (depth {args.depth})")
    for d in sorted(by_depth):
        ks = sorted(by_depth[d])
        print(f"\n## depth {d} ({len(ks)})")
        for k in ks:
            print(f"  {k}")

def cmd_path(args, idx):
    a = resolve_key(idx, args.a)
    b = resolve_key(idx, args.b)
    if not a:
        print(f"Not found: {args.a}", file=sys.stderr); return 1
    if not b:
        print(f"Not found: {args.b}", file=sys.stderr); return 1
    parent: dict[str, str | None] = {a: None}
    queue: deque = deque([a])
    while queue:
        cur = queue.popleft()
        if cur == b:
            break
        nbs = set(idx["notes"].get(cur, {}).get("forward_links", [])) | set(idx["backlinks"].get(cur, []))
        for nb in nbs:
            if nb in idx["notes"] and nb not in parent:
                parent[nb] = cur
                queue.append(nb)
    if b not in parent:
        print(f"No path between {a} and {b}", file=sys.stderr)
        return 1
    chain: list[str] = []
    cur: str | None = b
    while cur is not None:
        chain.append(cur)
        cur = parent[cur]
    chain.reverse()
    if args.json:
        print(json.dumps({"from": a, "to": b, "path": chain}, indent=2))
        return
    print(" → ".join(chain))

def cmd_find(args, idx):
    query = " ".join(args.query) if isinstance(args.query, list) else args.query
    tokens = tokenize(query)
    if not tokens:
        print("Empty query", file=sys.stderr)
        return 1
    docs: dict[str, dict[str, list[str]]] = {}
    for key, n in idx["notes"].items():
        fm = n.get("frontmatter") or {}
        docs[key] = {
            "filename": tokenize(key),
            "title": tokenize(n.get("title") or ""),
            "tags": [t.lower() for t in (fm.get("tags") or [])],
            "meta": tokenize(" ".join([fm.get("type") or "", fm.get("status") or "", fm.get("project") or ""])),
            "body": tokenize(n.get("first_paragraph") or ""),
        }
    N = max(1, len(docs))
    df: dict[str, int] = defaultdict(int)
    for d in docs.values():
        seen: set[str] = set()
        for field_tokens in d.values():
            seen.update(field_tokens)
        for t in seen:
            df[t] += 1
    def idf(t: str) -> float:
        return math.log(1 + (N - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))

    WEIGHTS = {"filename": 4.0, "title": 3.0, "tags": 3.0, "meta": 2.0, "body": 1.0}
    avg_len = {f: max(1.0, sum(len(d[f]) for d in docs.values()) / N) for f in WEIGHTS}
    k1, b_param = 1.2, 0.5

    scored: list[tuple[float, str]] = []
    for key, doc in docs.items():
        score = 0.0
        for t in tokens:
            it = idf(t)
            for field, w in WEIGHTS.items():
                tf = doc[field].count(t)
                if tf == 0:
                    continue
                dl = len(doc[field])
                norm = tf * (k1 + 1) / (tf + k1 * (1 - b_param + b_param * dl / avg_len[field]))
                score += w * it * norm
        if score > 0:
            scored.append((score, key))

    if not scored and args.fuzzy:
        import difflib
        candidates = difflib.get_close_matches(query.lower(), list(docs.keys()), n=args.limit, cutoff=0.5)
        scored = [(1.0, c) for c in candidates]

    scored.sort(key=lambda x: -x[0])
    scored = scored[: args.limit]

    if args.json:
        out = []
        for s, key in scored:
            n = idx["notes"][key]
            out.append({
                "score": round(s, 3), "key": key, "path": n["path"], "title": n.get("title"),
                "frontmatter": n["frontmatter"],
                "in_count": len(idx["backlinks"].get(key, [])),
                "out_count": len(n["forward_links"]),
                "snippet": (n.get("first_paragraph") or "")[:240],
            })
        print(json.dumps(out, indent=2))
        return

    print(f"# find: {query} → {len(scored)} results\n")
    for i, (s, key) in enumerate(scored, 1):
        n = idx["notes"][key]
        in_c = len(idx["backlinks"].get(key, []))
        out_c = len(n["forward_links"])
        fm = n["frontmatter"]
        tag_str = ",".join((fm.get("tags") or [])[:4])
        print(f"{i}. {key}  (score {s:.2f})  [{in_c}in/{out_c}out]")
        print(f"   {n['path']}  • {fm.get('type','?')}/{fm.get('status','?')}  • #{tag_str}")
        snip = (n.get("first_paragraph") or "")[:160].strip()
        if snip:
            print(f"   {snip}")
        print()

def cmd_index(args, idx):
    p = index_path(Path(idx["vault_path"]))
    if args.json:
        print(json.dumps({
            "rebuilt": bool(args.rebuild),
            "notes": len(idx["notes"]),
            "backlink_edges": sum(len(v) for v in idx["backlinks"].values()),
            "path": str(p), "built_at": idx["built_at"],
        }, indent=2))
        return
    print(f"Index path:     {p}")
    print(f"Notes:          {len(idx['notes'])}")
    print(f"Backlink edges: {sum(len(v) for v in idx['backlinks'].values())}")
    print(f"Built at:       {idx['built_at']}")


# ----------------------------------------------------------------- main ----

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vault", description="Graph-aware Obsidian vault CLI")
    p.add_argument("--vault", help="Override vault path (default $VAULT_PATH or ~/obsidian_notes)")
    p.add_argument("--verbose", "-v", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("stats"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("project"); s.add_argument("name"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("tag"); s.add_argument("tag"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("query")
    s.add_argument("--tag"); s.add_argument("--status"); s.add_argument("--type"); s.add_argument("--project")
    s.add_argument("--limit", type=int, default=50); s.add_argument("--json", action="store_true")

    s = sub.add_parser("recent")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--limit", type=int, default=20); s.add_argument("--json", action="store_true")

    s = sub.add_parser("orphans"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("show"); s.add_argument("note"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("links")
    s.add_argument("note")
    s.add_argument("--to", dest="to_only", action="store_true", help="Only show in-links (who links to note)")
    s.add_argument("--from", dest="from_only", action="store_true", help="Only show out-links (who note links to)")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("neighbors")
    s.add_argument("note"); s.add_argument("--depth", type=int, default=1); s.add_argument("--json", action="store_true")

    s = sub.add_parser("path")
    s.add_argument("a"); s.add_argument("b"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("find")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--fuzzy", action="store_true"); s.add_argument("--json", action="store_true")

    s = sub.add_parser("index")
    s.add_argument("--rebuild", action="store_true"); s.add_argument("--json", action="store_true")
    return p


HANDLERS = {
    "stats": cmd_stats, "project": cmd_project, "tag": cmd_tag, "query": cmd_query,
    "recent": cmd_recent, "orphans": cmd_orphans, "show": cmd_show, "links": cmd_links,
    "neighbors": cmd_neighbors, "path": cmd_path, "find": cmd_find, "index": cmd_index,
}


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 stdout on Windows cp1252 consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = build_parser().parse_args(argv)
    vault = vault_root(args.vault)
    if not vault.exists():
        print(f"Vault not found: {vault}", file=sys.stderr)
        return 1
    idx = load_index(vault, force_rebuild=getattr(args, "rebuild", False), verbose=args.verbose)
    return HANDLERS[args.cmd](args, idx) or 0


if __name__ == "__main__":
    sys.exit(main())
