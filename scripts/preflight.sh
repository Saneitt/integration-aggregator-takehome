#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=versions.env
source "$repo_root/versions.env"
source "$repo_root/scripts/lib.sh"

required=(docker minikube kubectl helm terraform jq envsubst openssl curl make)
missing=()
for tool in "${required[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing+=("$tool")
  fi
done
if ((${#missing[@]})); then
  die "Missing required tools: ${missing[*]}. Run scripts/bootstrap-wsl.sh first."
fi

log "Checking Docker daemon"
docker info >/dev/null || die "Docker daemon is unavailable; check systemctl status docker in WSL."

log "Checking pinned tool versions"
minikube version --short | grep -F "$MINIKUBE_VERSION" >/dev/null || die "Expected minikube $MINIKUBE_VERSION"
kubectl version --client -o json | jq -e --arg prefix "${KUBERNETES_VERSION%.*}." '.clientVersion.gitVersion | startswith($prefix)' >/dev/null || die "Expected kubectl minor $KUBERNETES_VERSION"
helm version --short | grep -F "$HELM_VERSION" >/dev/null || die "Expected Helm $HELM_VERSION"
terraform version -json | jq -e --arg v "$TERRAFORM_VERSION" '.terraform_version == $v' >/dev/null || die "Expected Terraform $TERRAFORM_VERSION"

if ! helm plugin list 2>/dev/null | awk 'NR > 1 && $1 == "diff" { found=1 } END { exit !found }'; then
  log "Installing helm-diff $HELM_DIFF_VERSION"
  helm plugin install https://github.com/databus23/helm-diff --version "$HELM_DIFF_VERSION" --verify=false
fi
helm plugin list

log "Tool versions"
docker --version
minikube version --short
kubectl version --client -o json | jq -r '.clientVersion.gitVersion'
helm version --short
terraform version -json | jq -r '"Terraform v" + .terraform_version'
jq --version
make --version | sed -n '1p'
