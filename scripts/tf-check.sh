#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
terraform -chdir="$repo_root/terraform" fmt -check -recursive
terraform -chdir="/terraform" init -backend=false -input=false
terraform -chdir="$repo_root/terraform" validate
terraform -chdir="$repo_root/terraform" test
