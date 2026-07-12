#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${ROOT}/logs/fastmcp_tailnet_http.log"
PID_FILE="${ROOT}/logs/fastmcp_tailnet_http.pid"
VENV_PATH="${ROOT}/.venv/bin/activate"

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-8766}"
ENABLE_TAILSCALE_SERVE="${EBAY_MCP_ENABLE_TAILSCALE_SERVE:-1}"

mkdir -p "$(dirname "${LOG_FILE}")"

if [ -f "${VENV_PATH}" ]; then
  # shellcheck disable=SC1090
  source "${VENV_PATH}"
else
  echo "Virtual environment not found at ${VENV_PATH}." >&2
  exit 1
fi

if [ -f "${PID_FILE}" ]; then
  OLD_PID="$(cat "${PID_FILE}")"
  if [ -n "${OLD_PID}" ] && ps -p "${OLD_PID}" >/dev/null 2>&1; then
    echo "Stopping previous tailnet HTTP server PID ${OLD_PID}."
    kill "${OLD_PID}" || true
    sleep 1
  fi
fi

export MCP_TRANSPORT=streamable-http
export MCP_HOST="${HOST}"
export MCP_PORT="${PORT}"
export MCP_ALLOWED_HOSTS="${MCP_ALLOWED_HOSTS:-127.0.0.1,localhost,${HOST}}"
export FASTMCP_CHECK_FOR_UPDATES="${FASTMCP_CHECK_FOR_UPDATES:-off}"

echo "Starting eBay MCP Streamable HTTP server on http://${HOST}:${PORT}/mcp"
cd "${ROOT}"
nohup python src/main_server.py >> "${LOG_FILE}" 2>&1 &
SERVER_PID=$!
echo "${SERVER_PID}" > "${PID_FILE}"
sleep 2

if ! ps -p "${SERVER_PID}" >/dev/null; then
  echo "Server failed to start. Last log lines:" >&2
  tail -n 20 "${LOG_FILE}" >&2 || true
  exit 1
fi

if [ "${ENABLE_TAILSCALE_SERVE}" = "1" ]; then
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "tailscale CLI not found; server is running locally without HTTPS tailnet serve." >&2
  else
    echo "Publishing tailnet HTTPS with Tailscale Serve."
    tailscale serve --bg --yes "http://127.0.0.1:${PORT}"
    tailscale serve status
  fi
fi

echo "Server PID: ${SERVER_PID}"
echo "Local MCP endpoint: http://${HOST}:${PORT}/mcp"
