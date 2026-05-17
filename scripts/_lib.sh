#!/usr/bin/env bash
# Shared helpers for CTO OS lifecycle scripts.
set -eu

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${REPO_ROOT}/.cto_os/run"
LOG_DIR="${REPO_ROOT}/.cto_os/logs"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

API_PORT="${CTO_OS_API_PORT:-8787}"
WEB_PORT="${CTO_OS_WEB_PORT:-3000}"

color() {
  local code="$1"; shift
  if [ -t 1 ]; then printf "\033[%sm%s\033[0m\n" "$code" "$*"; else printf "%s\n" "$*"; fi
}
ok()   { color "32" "$@"; }
warn() { color "33" "$@"; }
err()  { color "31" "$@" 1>&2; }

pid_file() { echo "${RUN_DIR}/$1.pid"; }
log_file() { echo "${LOG_DIR}/$1.log"; }

is_running() {
  local name="$1"
  local pf
  pf="$(pid_file "$name")"
  [ -f "$pf" ] || return 1
  local pid
  pid="$(cat "$pf" 2>/dev/null || true)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null
}

write_pid() {
  local name="$1" pid="$2"
  echo "$pid" > "$(pid_file "$name")"
}

clear_pid() {
  rm -f "$(pid_file "$1")"
}

require_venv() {
  if [ ! -x "${REPO_ROOT}/.venv/bin/python" ]; then
    err "Python venv missing at ${REPO_ROOT}/.venv. Run: python3 -m venv .venv && .venv/bin/pip install -r cto_os_api/requirements.txt"
    exit 1
  fi
}

require_env_file() {
  if [ ! -f "${REPO_ROOT}/.env" ] && [ ! -f "${REPO_ROOT}/.env.example" ]; then
    warn "No .env or .env.example in repo root — services will use defaults."
  fi
}

require_npm_deps() {
  if [ ! -d "${REPO_ROOT}/cto_os_web/node_modules" ]; then
    err "cto_os_web/node_modules missing. Run: (cd cto_os_web && npm install)"
    exit 1
  fi
}
