#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=versions.env
source "$repo_root/versions.env"
source "$repo_root/scripts/lib.sh"

pid_file="$repo_root/.build/openbao-port-forward.pid"
start_port_forward openbao svc/openbao 18200:8200 "$pid_file"
trap 'stop_process "$pid_file"' EXIT
wait_http http://127.0.0.1:18200/v1/sys/health 120

export VAULT_ADDR=http://127.0.0.1:18200
VAULT_TOKEN="$(<"$repo_root/.secrets/openbao-root-token")"
export VAULT_TOKEN
export TF_VAR_openbao_addr="$VAULT_ADDR"
export TF_VAR_plugin_version="$OAUTHAPP_VERSION"
export TF_VAR_plugin_sha256="$OAUTHAPP_BINARY_SHA256"

terraform -chdir="$repo_root/terraform" init -input=false -reconfigure \
  -backend-config="config_path=${KUBECONFIG:-$HOME/.kube/config}" \
  -backend-config="config_context=${MINIKUBE_PROFILE:-aggregator}" \
  -backend-config="namespace=openbao" \
  -backend-config="secret_suffix=openbao-config"
if [[ "${TF_ACTION:-apply}" == plan ]]; then
  set +e
  terraform -chdir="$repo_root/terraform" plan -input=false -detailed-exitcode
  status=$?
  set -e
  case "$status" in
    0) log "Terraform plan confirms there are no changes" ;;
    2) die "Terraform plan found changes" ;;
    *) die "Terraform plan failed with exit code $status" ;;
  esac
else
  terraform -chdir="$repo_root/terraform" apply -input=false -auto-approve
fi
unset VAULT_TOKEN
