#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

kubectl -n oidc create configmap mock-oidc-config \
  --from-file=config.json="$repo_root/deploy/mock-oidc/config.json" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$repo_root/deploy/mock-oidc/deployment.yaml"
kubectl -n oidc rollout status deployment/mock-oauth2-server --timeout=180s

pid_file="$repo_root/.build/mock-oidc-port-forward.pid"
start_port_forward oidc svc/mock-oauth2-server 8090:8080 "$pid_file"
trap 'stop_process "$pid_file"' EXIT
wait_http http://127.0.0.1:8090/ci/.well-known/openid-configuration 60
curl --silent --show-error --fail \
  http://127.0.0.1:8090/ci/.well-known/openid-configuration \
  | jq -e '.authorization_endpoint | endswith("/ci/authorize")' >/dev/null
log "Mock OIDC discovery endpoint is ready on localhost:8090"
