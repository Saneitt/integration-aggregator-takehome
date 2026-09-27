#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"
api="${API_URL:-http://127.0.0.1:8080}"
sensitive_dir="$repo_root/.build/sensitive"
response_dir="$repo_root/.build/responses"
report="$repo_root/.build/reports/leak-check.md"
mkdir -p "$(dirname "$report")"
wait_http "$api/readyz" 30

providers="$(curl --silent --show-error --fail "$api/providers")"
if ! jq -e 'all(.[]; (has("client_secret") or has("access_token") or has("refresh_token")) | not)' \
  <<<"$providers" >/dev/null; then
  unset providers
  die "Provider listing includes a sensitive field"
fi
unset providers

accepted="$(curl --silent --show-error --fail --write-out $'\n%{http_code}' "$api/mock/leak-check")"
status="${accepted##*$'\n'}"
body="${accepted%*$'\n'*}"
[[ "$status" == 202 ]] || die "Token request should return 202, got HTTP $status"
if jq -e 'has("token") or has("access_token") or has("client_secret")' <<<"$body" >/dev/null; then
  unset accepted body
  die "Non-token endpoint returned a sensitive field"
fi
unset accepted body

sources=()
while IFS= read -r file; do sources+=("$file"); done \
  < <(find "$response_dir" -maxdepth 1 -type f -name 'response-*.json' -print 2>/dev/null | sort)
for file in "$repo_root"/.build/reports/*.md "$repo_root"/.build/*.log \
  "$repo_root"/perf/results/perf-report.md "$repo_root"/perf/results/summary.json; do
  [[ -f "$file" ]] && sources+=("$file")
done

# Inspect only application logs. OpenBao logs expose the dev root token and are never read.
app_logs="$repo_root/.build/aggregator-leak-scan.log"
kubectl -n aggregator logs deployment/integration-aggregator --since=1h \
  >"$app_logs" 2>/dev/null || die "Could not read aggregator logs for the leak check"
chmod 600 "$app_logs"
if kubectl -n aggregator get pods -l app.kubernetes.io/instance=integration-aggregator \
  -o json | jq -e 'any(.items[]; any(.status.containerStatuses[]?; .restartCount > 0))' >/dev/null; then
  while IFS= read -r pod; do
    kubectl -n aggregator logs "$pod" --previous --since=1h \
      >>"$app_logs" 2>/dev/null || true
  done < <(kubectl -n aggregator get pods -l app.kubernetes.io/instance=integration-aggregator \
    -o jsonpath='{range .items[?(@.status.containerStatuses[0].restartCount>0)]}{.metadata.name}{"\n"}{end}')
fi
sources+=("$app_logs")

for source_file in "${sources[@]}"; do
  [[ -f "$source_file" ]] || continue
  for sensitive_file in "$sensitive_dir"/client-secret "$sensitive_dir"/access-token-* \
    "$sensitive_dir"/short-token-* "$sensitive_dir"/authorization-code-*; do
    [[ -s "$sensitive_file" ]] || continue
    sensitive_value="$(<"$sensitive_file")"
    if grep -Fq -- "$sensitive_value" "$source_file"; then
      unset sensitive_value
      die "Known credential material was found in a saved response, report, or app log."
    fi
    unset sensitive_value
  done
  if grep -Eiq 'gh[opsu]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9_.~+/=-]{24,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}' \
    "$source_file"; then
    die "Token-shaped material was found in a saved response, report, or app log."
  fi
done

# OAuth state is returned by connect by design; it must never leak into logs or reports.
for source_file in "$repo_root"/.build/reports/*.md "$repo_root"/.build/*.log "$app_logs"; do
  [[ -f "$source_file" ]] || continue
  for sensitive_file in "$sensitive_dir"/oauth-state-*; do
    [[ -s "$sensitive_file" ]] || continue
    sensitive_value="$(<"$sensitive_file")"
    if grep -Fq -- "$sensitive_value" "$source_file"; then
      unset sensitive_value
      die "OAuth state was found in a log or report."
    fi
    unset sensitive_value
  done
done

cat >"$report" <<'EOF'
# Secret leak check

PASS: provider listing redacts credentials; the pending 202 response omits token fields; saved non-token API responses, smoke/performance reports, and application logs contain no known client secrets, issued tokens, authorization codes, or token-shaped values. OAuth state values were checked against logs and reports. OpenBao pod logs were not read.
EOF
printf 'PASS known secrets, tokens, codes, token-shaped patterns, and logs were checked; no leak detected.\n'
