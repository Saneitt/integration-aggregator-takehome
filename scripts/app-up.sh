#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

release="integration-aggregator"
namespace="aggregator"
chart="${CHART_REF:-$repo_root/charts/integration-aggregator}"
image_repo="${IMAGE_REPO:-integration-aggregator}"
image_tag="${IMAGE_TAG:-$("$repo_root/scripts/image-tag.sh")}"

args=(--namespace "$namespace" --set-string "image.repository=$image_repo"
  --set-string "image.tag=$image_tag")
if [[ -n "${CHART_VERSION:-}" ]]; then
  args+=(--version "$CHART_VERSION")
fi
if [[ -n "${IMAGE_PULL_SECRET:-}" ]]; then
  args+=(--set "imagePullSecrets[0].name=$IMAGE_PULL_SECRET")
fi

diff_log="$repo_root/.build/app-helm-diff.log"
mkdir -p "$(dirname "$diff_log")"
if helm diff upgrade "$release" "$chart" "${args[@]}" \
  --allow-unreleased --detailed-exitcode >"$diff_log" 2>&1; then
  log "Application release is already current"
else
  status=$?
  if [[ "$status" == 2 ]] || grep -Fq 'identified at least one change' "$diff_log"; then
    helm upgrade --install "$release" "$chart" "${args[@]}" --wait --timeout 5m
  else
    cat "$diff_log" >&2
    die "helm diff failed with exit code $status"
  fi
fi

# Wait for the singleton rollout even when Helm reports the release as current.
kubectl -n "$namespace" rollout status deployment/"$release" --timeout=300s
