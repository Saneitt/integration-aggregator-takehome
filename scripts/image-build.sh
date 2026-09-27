#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

if [[ "${BUILD_IMAGE:-1}" != "1" ]]; then
  log "BUILD_IMAGE=0; skipping local image build"
  exit 0
fi

profile="${MINIKUBE_PROFILE:-aggregator}"
image_repo="${IMAGE_REPO:-integration-aggregator}"
image_tag="${IMAGE_TAG:-}"
if [[ -z "$image_tag" || "$image_tag" == "dev-local" ]]; then
  image_tag="$("$repo_root/scripts/image-tag.sh")"
fi

minikube -p "$profile" image build \
  --tag "$image_repo:$image_tag" \
  "$repo_root/app"
if ! minikube -p "$profile" image ls | grep -Fq "$image_repo:$image_tag"; then
  die "Minikube did not add image $image_repo:$image_tag"
fi
printf 'Built %s:%s inside minikube.\n' "$image_repo" "$image_tag"
