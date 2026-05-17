#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

NAME="worker"
require_venv

if is_running "$NAME"; then
  ok "Worker already running (pid $(cat "$(pid_file "$NAME")"))"
  exit 0
fi

LOG="$(log_file "$NAME")"
nohup "${REPO_ROOT}/.venv/bin/python" -m cto_os_api.worker >> "$LOG" 2>&1 &
PID=$!
write_pid "$NAME" "$PID"
ok "Worker started (pid $PID)"
ok "Logs: $LOG"
