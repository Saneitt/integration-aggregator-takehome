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

# Include process start time so a stale PID cannot identify an unrelated process.
process_stamp() {
  [[ -r "/proc/$1/stat" ]] || return 0
  awk '$3 != "Z" {print $22}' "/proc/$1/stat" 2>/dev/null || true
}

start_port_forward() {
  local namespace="$1" target="$2" mapping="$3" pid_file="$4" pid stamp
  mkdir -p "$(dirname "$pid_file")"
  # A live forward may still target a pod that a completed rollout replaced.
  stop_process "$pid_file"
  nohup kubectl -n "$namespace" port-forward "$target" "$mapping" \
    >"${pid_file%.pid}.log" 2>&1 </dev/null &
  pid=$!
  stamp="$(process_stamp "$pid")"
  [[ -n "$stamp" ]] || die "Port forward exited; inspect ${pid_file%.pid}.log"
  printf '%s %s\n' "$pid" "$stamp" >"$pid_file"
}

stop_process() {
  local pid_file="$1" pid stamp current _attempt
  [[ -f "$pid_file" ]] || return 0
  read -r pid stamp <"$pid_file" || true
  if [[ "$pid" =~ ^[0-9]+$ ]]; then
    current="$(process_stamp "$pid")"
    # Migrate older PID-only files only when they still identify kubectl.
    if [[ -z "$stamp" && -n "$current" && -r "/proc/$pid/comm" ]] \
      && [[ "$(<"/proc/$pid/comm")" == kubectl ]] \
      && grep -azq 'port-forward' "/proc/$pid/cmdline"; then
      stamp="$current"
    fi
    if [[ -n "$stamp" && "$stamp" == "$current" ]]; then
      kill "$pid" 2>/dev/null || true
      for _attempt in {1..100}; do
        [[ "$(process_stamp "$pid")" == "$stamp" ]] || break
        sleep 0.05
      done
    fi
  fi
  rm -f "$pid_file"
}

mask_value() {
  [[ -n "${GITHUB_ACTIONS:-}" && -n "${1:-}" ]] || return 0
  printf '::add-mask::%s\n' "$1"
}
