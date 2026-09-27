#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

for pid_file in \
  "$repo_root/.build/aggregator-port-forward.pid" \
  "$repo_root/.build/oidc-port-forward.pid" \
  "$repo_root/.build/openbao-port-forward.pid" \
  "$repo_root/.build/mock-oidc-port-forward.pid"; do
  stop_process "$pid_file"
done
