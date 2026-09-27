#!/usr/bin/env bash
set -euo pipefail

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }

wait_http() {
  local url="$1" deadline=$((SECONDS + ${2:-120}))
  until curl --silent --fail --output /dev/null "$url"; do
    (( SECONDS < deadline )) || die "Timed out waiting for HTTP endpoint: $url"
    sleep 2
  done
}

start_port_forward() {
  local namespace="$1" target="$2" mapping="$3" pid_file="$4"
  mkdir -p "$(dirname "$pid_file")"
  if [[ -f "$pid_file" ]] && kill -0 "$(<"$pid_file")" 2>/dev/null; then
    return 0
  fi
  rm -f "$pid_file"
  nohup kubectl -n "$namespace" port-forward "$target" "$mapping" \
    >"${pid_file%.pid}.log" 2>&1 </dev/null &
  printf '%s\n' "$!" >"$pid_file"
}

stop_process() {
  local pid_file="$1" pid
  [[ -f "$pid_file" ]] || return 0
  pid=$(<"$pid_file")
  kill "$pid" 2>/dev/null || true
  rm -f "$pid_file"
}

mask_value() {
  [[ -n "${GITHUB_ACTIONS:-}" && -n "${1:-}" ]] || return 0
  printf '::add-mask::%s\n' "$1"
}
