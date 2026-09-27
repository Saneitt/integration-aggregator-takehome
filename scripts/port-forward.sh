#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

start_port_forward aggregator svc/integration-aggregator 8080:8080 \
  "$repo_root/.build/aggregator-port-forward.pid"
start_port_forward oidc svc/mock-oauth2-server 8090:8080 \
  "$repo_root/.build/oidc-port-forward.pid"
wait_http http://127.0.0.1:8080/readyz 60
wait_http http://127.0.0.1:8090/ci/.well-known/openid-configuration 60
log "Service: http://localhost:8080"
log "Mock OIDC: http://localhost:8090"
