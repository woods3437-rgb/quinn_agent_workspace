#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

NAME="web"
require_npm_deps

if is_running "$NAME"; then
  ok "Web already running (pid $(cat "$(pid_file "$NAME")")) — http://127.0.0.1:${WEB_PORT}/projects"
  exit 0
fi

LOG="$(log_file "$NAME")"
cd cto_os_web
nohup npm run dev -- --port "${WEB_PORT}" >> "$LOG" 2>&1 &
PID=$!
cd ..
write_pid "$NAME" "$PID"
ok "Web started (pid $PID) — http://127.0.0.1:${WEB_PORT}/projects"
ok "Logs: $LOG"
