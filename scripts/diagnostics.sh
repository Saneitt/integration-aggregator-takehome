#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"
out="$repo_root/.build/diagnostics.md"
mkdir -p "$(dirname "$out")"

{
  printf '# Local diagnostics\n\n'
  printf 'Generated: %s UTC\n\n' "$(date -u +%FT%TZ)"
  printf '## Cluster\n\n```text\n'
  minikube -p "${MINIKUBE_PROFILE:-aggregator}" status 2>&1 || true
  printf '\n## Pods and releases\n\n```text\n'
  kubectl get pods -A -o wide 2>&1 || true
  helm list -A 2>&1 || true
  printf '\n## Aggregator logs (redacted)\n\n```text\n'
  if kubectl -n aggregator get deployment integration-aggregator >/dev/null 2>&1; then
    kubectl -n aggregator logs deployment/integration-aggregator --since=15m 2>/dev/null \
      | sed -E 's/(gh[opsu]_[[:alnum:]_]{20,}|glpat-[[:alnum:]_-]{20,}|Bearer[[:space:]]+[[:alnum:]_.~+\/=:-]{20,}|eyJ[[:alnum:]_-]{10,}\.[[:alnum:]_.-]+)/[REDACTED]/g' \
      || true
  fi
  printf '\n```\n\nOpenBao pod logs are intentionally excluded.\n'
} >"$out"

printf 'Wrote redacted diagnostics to %s\n' "$out"
