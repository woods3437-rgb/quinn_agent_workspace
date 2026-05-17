#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/_lib.sh

status_one() {
  local name="$1" port="$2"
  if is_running "$name"; then
    local pid
    pid="$(cat "$(pid_file "$name")")"
    printf "%-7s  RUNNING (pid %s)" "$name" "$pid"
    if [ -n "$port" ]; then
      if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$port" 2>/dev/null; then
        printf "  port %s reachable" "$port"
      elif [ -n "$port" ]; then
        printf "  port %s not yet reachable" "$port"
      fi
    fi
    echo
  else
    printf "%-7s  stopped\n" "$name"
  fi
}

status_one api    "$API_PORT"
status_one worker ""
status_one web    "$WEB_PORT"
echo
echo "Logs: ${LOG_DIR}"
echo "PIDs: ${RUN_DIR}"
