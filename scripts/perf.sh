#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"
mkdir -p "$repo_root/.build/reports" "$repo_root/perf/results"

start_port_forward aggregator svc/integration-aggregator 8080:8080 \
  "$repo_root/.build/aggregator-port-forward.pid"
start_port_forward oidc svc/mock-oauth2-server 8090:8080 \
  "$repo_root/.build/oidc-port-forward.pid"
wait_http http://127.0.0.1:8080/readyz 60
wait_http http://127.0.0.1:8090/ci/.well-known/openid-configuration 60
bash "$repo_root/scripts/mock-connect.sh" perf-user

kubectl -n perf create configmap k6-scripts \
  --from-file=token-retrieval.js="$repo_root/perf/token-retrieval.js" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
envsubst "\${K6_IMAGE}" <"$repo_root/perf/k6-job.yaml.tpl" >"$repo_root/.build/perf-job.yaml"
kubectl -n perf delete job k6-token-retrieval --ignore-not-found >/dev/null
kubectl apply -f "$repo_root/.build/perf-job.yaml" >/dev/null

deadline=$((SECONDS + 300))
while (( SECONDS < deadline )); do
  job="$(kubectl -n perf get job k6-token-retrieval -o json)"
  if jq -e '.status.conditions[]? | select(.type == "Complete" and .status == "True")' \
    <<<"$job" >/dev/null; then
    break
  fi
  if jq -e '.status.conditions[]? | select(.type == "Failed" and .status == "True")' \
    <<<"$job" >/dev/null; then
    kubectl -n perf logs job/k6-token-retrieval --tail=80 >&2 || true
    die "k6 performance job failed"
  fi
  sleep 3
done
if (( SECONDS >= deadline )); then
  kubectl -n perf logs job/k6-token-retrieval --tail=80 >&2 || true
  die "k6 performance job timed out"
fi

kubectl -n perf logs job/k6-token-retrieval >"$repo_root/.build/perf-k6.log"
awk '/=====PERF-REPORT-BEGIN=====/{capture=1} capture{print} /=====PERF-REPORT-END=====/{capture=0}' \
  "$repo_root/.build/perf-k6.log" >"$repo_root/perf/results/perf-report.md"
grep -q '^# Token retrieval performance' "$repo_root/perf/results/perf-report.md" \
  || die "k6 output did not contain the performance report"
grep '^PERF_JSON:' "$repo_root/.build/perf-k6.log" | tail -n 1 | cut -d: -f2- \
  >"$repo_root/perf/results/summary.json"
cp "$repo_root/perf/results/perf-report.md" "$repo_root/.build/reports/perf.md"
kubectl -n perf delete job k6-token-retrieval --wait=false >/dev/null
cat "$repo_root/perf/results/perf-report.md"
