#!/usr/bin/env bash
S="$(dirname "$0")/vault-mcp.py"

for P in python3 python py; do
  if command -v "$P" >/dev/null 2>&1 && "$P" -c "" >/dev/null 2>&1; then
    exec "$P" "$S"
  fi
done

echo "vault-mcp: no working python in PATH" >&2
exit 1
