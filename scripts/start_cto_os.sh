#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

bash scripts/start_api.sh
bash scripts/start_worker.sh
bash scripts/start_web.sh

echo
ok "CTO OS up:"
echo "  API:    http://127.0.0.1:${API_PORT}"
echo "  Web:    http://127.0.0.1:${WEB_PORT}/projects"
echo "  Worker: see .cto_os/logs/worker.log"
echo "  MCP:    launched by the host (Claude Code / Cowork)"
echo
ok "Health:   curl http://127.0.0.1:${API_PORT}/system/health | jq ."
