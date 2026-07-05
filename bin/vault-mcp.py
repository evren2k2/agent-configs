#!/usr/bin/env python3
"""vault-mcp — STDIO-based MCP server for the Obsidian vault.
Wraps the existing logic in bin/vault to expose native tools.
"""

import json
import sys
import os
import traceback
from pathlib import Path

# Add current bin directory to path so we can import vault
BIN_DIR = Path(__file__).parent.absolute()
if str(BIN_DIR) not in sys.path:
    sys.path.append(str(BIN_DIR))

from venv_bootstrap import ensure_venv
ensure_venv()  # relaunch under ~/.venv if one exists (semantic-search deps live there)

import vault

def get_vault_root():
    return vault.vault_root()

class VaultMCPServer:
    def __init__(self):
        self.vault_path = get_vault_root()
        self.index = None
        # Semantic search: loaded once per process on first use.
        self.semantic = None        # (encode, (vectors, meta)) or None
        self.semantic_tried = False

    def ensure_index(self):
        """Load/refresh the lexical index. If a semantic store is already loaded,
        keep it in step with the index incrementally (only changed notes re-embed;
        the encoder is already in memory) so mid-session edits stay searchable.
        The expensive first build stays lazy — it only runs on a real query."""
        prev_keys = set(self.index["notes"]) if self.index else set()
        self.index = vault.load_index(self.vault_path)
        # _changed counts reparses; a pure deletion reparses nothing, so also compare
        # the key set — else a deleted note's passages linger in the semantic store.
        changed = bool(self.index.get("_changed")) or set(self.index["notes"]) != prev_keys
        if self.semantic is not None and changed:
            try:
                import vault_embed
                encode, _ = self.semantic
                _, meta = self.semantic[1]
                model = meta.get("model") or vault_embed.DEFAULT_MODEL
                vault_embed.build_vectors(self.vault_path, self.index,
                                          model_name=model, encode=encode)
                vectors, meta = vault_embed.load_store(self.vault_path, model)
                if vectors is not None:
                    self.semantic = (encode, (vectors, meta))
            except Exception as e:
                print(f"vault-mcp: semantic refresh skipped — {e}", file=sys.stderr, flush=True)
        return self.index

    def handle_request(self, request):
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                return self.on_initialize(params)
            elif method == "tools/list":
                return self.on_list_tools()
            elif method == "tools/call":
                return self.on_call_tool(params)
            else:
                return {"error": {"code": -32601, "message": f"Method not found: {method}"}}
        except Exception as e:
            return {"error": {"code": -32603, "message": str(e), "data": traceback.format_exc()}}

    def on_initialize(self, params):
        # Echo client's requested version — makes server compatible with any MCP client version
        protocol_version = params.get("protocolVersion", "2024-11-05")
        return {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "vault-mcp",
                "version": "0.1.0"
            }
        }

    def on_list_tools(self):
        return {
            "tools": [
                {
                    "name": "vault_find",
                    "description": "Search for notes in the vault using lexical ranking (BM25).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query terms"},
                            "limit": {"type": "integer", "default": 10},
                            "fuzzy": {"type": "boolean", "default": False}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "vault_project",
                    "description": ("List notes in a project as a lean, sub-folder-grouped "
                                    "overview (counts instead of full link lists; frontmatter "
                                    "trimmed to type/status/tags). The archive/ sub-folder is "
                                    "collapsed to a count by default — pass expand_archive=true "
                                    "to list it. Built for orientation: enumerate, then "
                                    "vault_show / Read the few notes you need."),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Project name (e.g. 'brawlstars-ranked-app')"},
                            "depth": {"type": "integer", "default": 1,
                                      "description": ("How many sub-folder levels under projects/<name>/ "
                                                      "to use for grouping. 1 (default) groups by the "
                                                      "immediate sub-folder (logs, decisions, archive, ...); "
                                                      "higher descends further; 0 collapses all in-folder notes "
                                                      "into one '(root)' group (notes matched only by project: "
                                                      "frontmatter that live outside the folder stay under '(other)').")},
                            "expand_archive": {"type": "boolean", "default": False,
                                               "description": ("By default the archive/ sub-folder is shown as a "
                                                               "one-line count ({folder, count, collapsed:true}) "
                                                               "instead of listing every archived note. Set true "
                                                               "to list the archive/ notes in full.")}
                        },
                        "required": ["name"]
                    }
                },
                {
                    "name": "vault_show",
                    "description": "Show metadata, links, and the first paragraph of a specific note.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "note": {"type": "string", "description": "Note name or path"}
                        },
                        "required": ["note"]
                    }
                },
                {
                    "name": "vault_links",
                    "description": "Get incoming and outgoing links for a note.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "note": {"type": "string", "description": "Note name or path"}
                        },
                        "required": ["note"]
                    }
                },
                {
                    "name": "vault_semantic_search",
                    "description": ("Semantic (vector) search over note paragraphs — a "
                                    "concept-aware grep. Returns the specific passages that "
                                    "match a concept by meaning, across all projects, each "
                                    "with its file path and line range. Multiple passages "
                                    "from the same note may appear. Each hit carries a cosine "
                                    "`score` (~1.0 strong, <0.3 weak — semantic search always "
                                    "returns a top-k, so judge by the score). Complements "
                                    "vault_find (BM25 lexical); prefer vault_find for exact "
                                    "symbol/name/project-ID lookups."),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Natural-language query / concept"},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                }
            ]
        }

    def on_call_tool(self, params):
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Ensure index is ready before any tool execution
        idx = self.ensure_index()

        if name == "vault_find":
            return self.tool_find(idx, arguments)
        elif name == "vault_project":
            return self.tool_project(idx, arguments)
        elif name == "vault_show":
            return self.tool_show(idx, arguments)
        elif name == "vault_links":
            return self.tool_links(idx, arguments)
        elif name == "vault_semantic_search":
            return self.tool_semantic_search(idx, arguments)
        else:
            return {"error": {"code": -32601, "message": f"Tool not found: {name}"}}

    def _call_capturing(self, fn, mock, idx, fallback):
        """Run a vault.cmd_* handler capturing stdout AND stderr. The handlers
        print 'Not found: X' to stderr and return non-zero on failure; surface
        that message instead of returning an empty {"text": ""} to the model."""
        import io
        from contextlib import redirect_stdout, redirect_stderr
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = fn(mock, idx)
        text = out.getvalue()
        if rc:
            text = err.getvalue().strip() or fallback
        return {"content": [{"type": "text", "text": text}]}

    def tool_find(self, idx, args):
        query = args.get("query")
        limit = args.get("limit", 10)
        fuzzy = args.get("fuzzy", False)

        class MockArgs:
            def __init__(self, q, l, f):
                self.query = q
                self.limit = l
                self.fuzzy = f
                self.json = True

        return self._call_capturing(vault.cmd_find, MockArgs(query, limit, fuzzy), idx,
                                    f"No matches for: {query}")

    def tool_project(self, idx, args):
        name = args.get("name")
        depth = args.get("depth", 1)
        expand_archive = args.get("expand_archive", False)
        result = vault.project_compact(idx, name, depth, expand_archive)
        # Minified: this payload is consumed by the model, so drop indent whitespace
        # to keep large projects parseable. (The CLI `project` text view is for humans.)
        return {
            "content": [{"type": "text", "text": json.dumps(result, separators=(",", ":"), default=str)}]
        }

    def tool_show(self, idx, args):
        note = args.get("note")
        class MockArgs:
            def __init__(self, n):
                self.note = n
                self.json = True
        return self._call_capturing(vault.cmd_show, MockArgs(note), idx,
                                    f"Not found: {note}")

    def tool_links(self, idx, args):
        note = args.get("note")
        class MockArgs:
            def __init__(self, n):
                self.note = n
                self.json = True
                self.from_only = False
                self.to_only = False
        return self._call_capturing(vault.cmd_links, MockArgs(note), idx,
                                    f"Not found: {note}")

    def _ensure_semantic(self, idx):
        """Load the embedding model + vector store once per process. Returns
        (encode, store) or None if semantic search is unavailable here."""
        if not self.semantic_tried:
            self.semantic_tried = True
            try:
                import vault_embed
                # Use the store's OWN model, not DEFAULT_MODEL — else a custom-model
                # store fails the model check and gets silently rebuilt with the default.
                model = vault_embed.stored_model(self.vault_path) or vault_embed.DEFAULT_MODEL
                encode = vault_embed.make_encoder(model)
                vec_path, _ = vault_embed.store_paths(self.vault_path)
                if not vec_path.exists():
                    print("vault-mcp: Building vector store...", file=sys.stderr, flush=True)
                # Sync the store to the current index (incremental: near-instant when
                # already fresh, a full build when absent) so the first query isn't
                # served from a between-session-stale or missing store.
                vault_embed.build_vectors(self.vault_path, idx, model_name=model, encode=encode)
                vectors, meta = vault_embed.load_store(self.vault_path, model)
                if vectors is not None:
                    self.semantic = (encode, (vectors, meta))
            except Exception as e:
                print(f"vault-mcp: semantic search disabled — {e}",
                      file=sys.stderr, flush=True)
        return self.semantic

    def tool_semantic_search(self, idx, args):
        query = args.get("query")
        limit = args.get("limit", 10)
        if not query:
            return {"content": [{"type": "text", "text": "Error: 'query' is required."}]}
        sem = self._ensure_semantic(idx)
        if sem is None:
            return {"content": [{"type": "text", "text": (
                "Semantic search unavailable: the dependencies (see requirements.txt) "
                "are not installed, or the vector store has not been built "
                "(run `vault embed`). Fall back to vault_find for this query.")}]}
        import vault_embed
        encode, store = sem
        hits = vault_embed.search(query, k=limit, encode=encode, store=store)
        results = []
        for h in hits:
            n = idx["notes"].get(h["key"])
            fm = n["frontmatter"] if n else {}
            results.append({
                "score": round(h["score"], 4),
                "path": h["path"],
                "lines": f'{h["line_start"]}-{h["line_end"]}',
                "title": n.get("title") if n else None,
                "project": fm.get("project"),
                "text": h["text"],
            })
        return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

    def run(self):
        # Simple JSON-RPC loop over stdio
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    continue   # JSON-RPC batch arrays / bare scalars: skip, don't crash
                # Notifications have no "id" — must not send a response
                if "id" not in request:
                    self.handle_request(request)
                    continue
                response_data = self.handle_request(request)

                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": response_data
                }
                if "error" in response_data:
                    response["error"] = response_data.pop("error")
                    del response["result"]

                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                continue

if __name__ == "__main__":
    try:
        server = VaultMCPServer()
        server.run()
    except Exception as e:
        print(f"vault-mcp fatal error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
