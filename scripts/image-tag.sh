#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/app"
find . -type f \
  ! -path '*/.venv/*' \
  ! -path '*/.pytest_cache/*' \
  ! -path '*/.mypy_cache/*' \
  ! -path '*/.ruff_cache/*' \
  ! -name '.coverage' \
  -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16
