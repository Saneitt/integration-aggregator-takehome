#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=versions.env
source "$repo_root/versions.env"
chart="$repo_root/charts/integration-aggregator"

helm lint --strict "$chart"
helm template integration-aggregator "$chart" --namespace aggregator \
  | kubeconform -strict -summary -kubernetes-version "${KUBERNETES_VERSION#v}"

if helm template integration-aggregator "$chart" --namespace aggregator --set replicaCount=2 >/dev/null 2>&1; then
  printf 'The chart must reject more than one replica.\n' >&2
  exit 1
fi
