#!/usr/bin/env bash
# The MCP server is launched by the host (Claude Code / Cowork / Claude Desktop)
# via stdio. This script is a smoke runner: it verifies the module imports,
# prints the recommended .mcp.json snippet, and exits.
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

require_venv

if "${REPO_ROOT}/.venv/bin/python" -c "import cto_os_api.mcp_server" 2>/dev/null; then
  ok "MCP module imports cleanly. Run via stdio:"
  echo "    .venv/bin/python -m cto_os_api.mcp_server"
  echo
  ok "Recommended .mcp.json (Claude Code):"
  cat <<JSON
{
  "mcpServers": {
    "cto-os": {
      "command": "${REPO_ROOT}/.venv/bin/python",
      "args": ["-m", "cto_os_api.mcp_server"],
      "cwd": "${REPO_ROOT}",
      "env": {
        "CTO_OS_LLM_PROVIDER": "deterministic",
        "CTO_OS_SQLITE_PATH": "cto_os_api/data/cto_os.sqlite3"
      }
    }
  }
}
JSON
else
  err "MCP module failed to import. Check .venv and requirements."
  exit 1
fi
