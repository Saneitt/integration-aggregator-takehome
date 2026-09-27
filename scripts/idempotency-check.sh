#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$repo_root/.build/reports"
log_file="$repo_root/.build/idempotency-check.log"

snapshot() {
  printf 'openbao_release=%s\n' \
    "$(helm -n openbao list -f '^openbao$' -o json | jq -r '.[0].revision')"
  printf 'openbao_statefulset=%s\n' \
    "$(kubectl -n openbao get statefulset openbao -o json \
      | jq -r '[.metadata.generation,.metadata.resourceVersion,.status.observedGeneration] | @tsv')"
  printf 'openbao_pods=%s\n' \
    "$(kubectl -n openbao get pods -l app.kubernetes.io/instance=openbao -o json \
      | jq -r '[.items[] | [.metadata.uid,([.status.containerStatuses[]?.restartCount] | add // 0)] | @tsv] | sort | .[]')"
  printf 'app_release=%s\n' \
    "$(helm -n aggregator list -f '^integration-aggregator$' -o json | jq -r '.[0].revision')"
  printf 'app_deployment=%s\n' \
    "$(kubectl -n aggregator get deployment integration-aggregator -o json \
      | jq -r '[.metadata.generation,.metadata.resourceVersion,.status.observedGeneration] | @tsv')"
  printf 'app_pods=%s\n' \
    "$(kubectl -n aggregator get pods -l app.kubernetes.io/instance=integration-aggregator -o json \
      | jq -r '[.items[] | [.metadata.uid,([.status.containerStatuses[]?.restartCount] | add // 0)] | @tsv] | sort | .[]')"
  printf 'oidc_deployment=%s\n' \
    "$(kubectl -n oidc get deployment mock-oauth2-server -o json \
      | jq -r '[.metadata.generation,.metadata.resourceVersion,.status.observedGeneration] | @tsv')"
  printf 'oidc_config=%s\n' \
    "$(kubectl -n oidc get configmap mock-oidc-config -o json | jq -r '.metadata.resourceVersion')"
  printf 'bootstrap_secret=%s\n' \
    "$(kubectl -n openbao get secret openbao-bootstrap -o json | jq -r '.metadata.resourceVersion')"
}

before="$(snapshot)"
if ! make -C "$repo_root" up >"$log_file" 2>&1; then
  printf 'Full-stack reconciliation failed; see %s\n' "$log_file" >&2
  exit 1
fi
after="$(snapshot)"
if ! TF_ACTION=plan make -C "$repo_root" configure >>"$log_file" 2>&1; then
  printf 'Terraform detailed-exitcode plan detected changes; see %s\n' "$log_file" >&2
  exit 1
fi
if [[ "$before" != "$after" ]]; then
  printf 'Deployed stack state changed on the second make up.\n' >&2
  diff -u <(printf '%s\n' "$before") <(printf '%s\n' "$after") >&2 || true
  exit 1
fi
grep -Fq 'No changes.' "$log_file" || {
  printf 'Terraform did not report No changes; see %s\n' "$log_file" >&2
  exit 1
}
grep -Fq 'Application release is already current' "$log_file" || {
  printf 'Helm did not report the app release as current; see %s\n' "$log_file" >&2
  exit 1
}
cat >"$repo_root/.build/reports/idempotency.md" <<'EOF'
# Idempotency report

The second `make up` left the Helm releases, application and OIDC workloads, OIDC configuration, and OpenBao bootstrap Secret unchanged. Terraform's apply reported `No changes.`, and a separate `plan -detailed-exitcode` returned zero. The Kubernetes Terraform backend updates its own state Secret while persisting an apply result, so its resource version is not used as a deployed-stack change signal.
EOF
printf 'PASS second make up made no deployed infrastructure changes.\n'
