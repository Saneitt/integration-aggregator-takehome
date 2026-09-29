#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Validation must not reuse a live cluster backend or race with make configure.
TF_DATA_DIR="$(mktemp -d)"
export TF_DATA_DIR
trap 'rm -rf "$TF_DATA_DIR"' EXIT
terraform -chdir="$repo_root/terraform" fmt -check -recursive
terraform -chdir="$repo_root/terraform" init -backend=false -input=false
terraform -chdir="$repo_root/terraform" validate
terraform -chdir="$repo_root/terraform" test
