#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=versions.env
source "$repo_root/versions.env"
source "$repo_root/scripts/lib.sh"

helm repo add openbao https://openbao.github.io/openbao-helm --force-update
kubectl -n openbao create configmap openbao-plugin-config \
  --from-file=plugins.hcl="$repo_root/deploy/openbao/plugins.hcl" \
  --dry-run=client -o yaml | kubectl apply -f -

mkdir -p "$repo_root/.build"
# shellcheck disable=SC2016
envsubst '${OAUTHAPP_VERSION} ${OAUTHAPP_TARBALL_SHA256} ${OAUTHAPP_BINARY_SHA256} ${PLUGIN_FETCH_IMAGE}' \
  <"$repo_root/deploy/openbao/values.yaml.tpl" \
  >"$repo_root/.build/openbao-values.yaml"

set +e
helm diff upgrade openbao openbao/openbao \
  --version "$OPENBAO_CHART_VERSION" \
  -n openbao \
  -f "$repo_root/.build/openbao-values.yaml" \
  --allow-unreleased \
  --detailed-exitcode
status=$?
set -e
case "$status" in
  0) log "OpenBao release is already current" ;;
  2)
    helm upgrade --install openbao openbao/openbao \
      --version "$OPENBAO_CHART_VERSION" \
      -n openbao \
      -f "$repo_root/.build/openbao-values.yaml" \
      --wait --timeout 5m
    ;;
  *) die "helm diff failed with exit code $status" ;;
esac

# A new StatefulSet can exist before its first pod has been created.
kubectl -n openbao wait --for=create pod/openbao-0 --timeout=180s
kubectl -n openbao wait --for=condition=Ready pod/openbao-0 --timeout=180s
