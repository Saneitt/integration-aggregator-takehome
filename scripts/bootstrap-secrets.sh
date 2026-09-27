#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

umask 077
install -d -m 0700 "$repo_root/.secrets" "$repo_root/.build"
root_token="$repo_root/.secrets/openbao-root-token"
if [[ ! -s "$root_token" ]]; then
  openssl rand -hex 24 >"$root_token"
  chmod 0600 "$root_token"
fi

kubectl -n openbao create secret generic openbao-bootstrap \
  --from-file="root-token=$root_token" \
  --dry-run=client -o yaml | kubectl apply -f -

if [[ -n "${IMAGE_PULL_SECRET:-}" ]]; then
  [[ -n "${GHCR_PULL_USER:-}" && -n "${GHCR_PULL_TOKEN:-}" ]] || die "GHCR_PULL_USER and GHCR_PULL_TOKEN are required when IMAGE_PULL_SECRET is set"
  mask_value "$GHCR_PULL_TOKEN"
  kubectl -n aggregator create secret docker-registry "$IMAGE_PULL_SECRET" \
    --docker-server=ghcr.io \
    --docker-username="$GHCR_PULL_USER" \
    --docker-password="$GHCR_PULL_TOKEN" \
    --dry-run=client -o yaml | kubectl apply -f -
fi