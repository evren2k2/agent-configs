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
import vault

def get_vault_root():
    return vault.vault_root()

class VaultMCPServer:
    def __init__(self):
        self.vault_path = get_vault_root()
        self.index = None

    def ensure_index(self):
        """Lazy-load or refresh the index."""
        if self.index is None:
            # First load
            self.index = vault.load_index(self.vault_path)
        else:
            # Check for updates (fast if no changes)
            self.index = vault.load_index(self.vault_path)
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
        # We don't build the index here to avoid handshake timeouts (3.3s cold start)
        return {
            "protocolVersion": "2024-11-05",
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
                    "description": "List all notes belonging to a specific project.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Project name (e.g. 'brawlstars-ranked-app')"}
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
        else:
            return {"error": {"code": -32601, "message": f"Tool not found: {name}"}}

    def tool_find(self, idx, args):
        query = args.get("query")
        limit = args.get("limit", 10)
        fuzzy = args.get("fuzzy", False)
        
        # Mocking an args object for the vault handler
        class MockArgs:
            def __init__(self, q, l, f):
                self.query = q
                self.limit = l
                self.fuzzy = f
                self.json = True
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            vault.cmd_find(MockArgs(query, limit, fuzzy), idx)
        
        return {
            "content": [{"type": "text", "text": f.getvalue()}]
        }

    def tool_project(self, idx, args):
        name = args.get("name")
        class MockArgs:
            def __init__(self, n):
                self.name = n
                self.json = True
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            vault.cmd_project(MockArgs(name), idx)
        
        return {
            "content": [{"type": "text", "text": f.getvalue()}]
        }

    def tool_show(self, idx, args):
        note = args.get("note")
        class MockArgs:
            def __init__(self, n):
                self.note = n
                self.json = True
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            vault.cmd_show(MockArgs(note), idx)
        
        return {
            "content": [{"type": "text", "text": f.getvalue()}]
        }

    def tool_links(self, idx, args):
        note = args.get("note")
        class MockArgs:
            def __init__(self, n):
                self.note = n
                self.json = True
                self.from_only = False
                self.to_only = False
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            vault.cmd_links(MockArgs(note), idx)
        
        return {
            "content": [{"type": "text", "text": f.getvalue()}]
        }

    def run(self):
        # Simple JSON-RPC loop over stdio
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
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
    server = VaultMCPServer()
    server.run()
