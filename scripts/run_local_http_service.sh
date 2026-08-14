#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROOT="${0:A:h:h}"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  print -u2 "Seller MCP virtual environment is unavailable at $ROOT/.venv."
  exit 1
fi

export MCP_TRANSPORT=streamable-http
export MCP_HOST="${MCP_HOST:-127.0.0.1}"
export MCP_PORT="${MCP_PORT:-8766}"
export MCP_ALLOWED_HOSTS="${MCP_ALLOWED_HOSTS:-127.0.0.1,localhost,$MCP_HOST}"
export FASTMCP_CHECK_FOR_UPDATES="${FASTMCP_CHECK_FOR_UPDATES:-off}"

exec doppler run --project ebay-mcp --config dev -- \
  .venv/bin/python src/main_server.py
