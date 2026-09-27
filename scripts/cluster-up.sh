#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=versions.env
source "$repo_root/versions.env"
source "$repo_root/scripts/lib.sh"

profile="${MINIKUBE_PROFILE:-aggregator}"
cpus="${MINIKUBE_CPUS:-4}"
memory="${MINIKUBE_MEMORY:-4096}"

if minikube -p "$profile" status >/dev/null 2>&1; then
  log "Minikube profile '$profile' is already running"
  exit 0
fi

log "Starting Minikube profile '$profile'"
minikube start \
  -p "$profile" \
  --driver=docker \
  --kubernetes-version="$KUBERNETES_VERSION" \
  --cpus="$cpus" \
  --memory="$memory"
