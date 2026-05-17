#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

NAME="api"
require_venv
require_env_file

if is_running "$NAME"; then
  ok "API already running (pid $(cat "$(pid_file "$NAME")")) — http://127.0.0.1:${API_PORT}"
  exit 0
fi

LOG="$(log_file "$NAME")"
nohup "${REPO_ROOT}/.venv/bin/uvicorn" cto_os_api.main:app \
  --host 127.0.0.1 --port "${API_PORT}" \
  >> "$LOG" 2>&1 &
PID=$!
write_pid "$NAME" "$PID"
ok "API started (pid $PID) — http://127.0.0.1:${API_PORT}"
ok "Logs: $LOG"
