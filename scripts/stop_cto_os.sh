#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

stop_one() {
  local name="$1"
  if is_running "$name"; then
    local pid
    pid="$(cat "$(pid_file "$name")")"
    kill "$pid" 2>/dev/null || true
    local i=0
    while [ $i -lt 30 ] && kill -0 "$pid" 2>/dev/null; do
      sleep 0.1
      i=$((i+1))
    done
    if kill -0 "$pid" 2>/dev/null; then
      warn "$name (pid $pid) did not stop in 3s; sending KILL"
      kill -9 "$pid" 2>/dev/null || true
    fi
    ok "$name stopped (was pid $pid)"
  else
    warn "$name not running"
  fi
  clear_pid "$name"
}

stop_one web
stop_one worker
stop_one api
