#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
provider="${1:?usage: register-provider.sh github|gitlab}"
env_file="$repo_root/.env"
api="${API_URL:-http://127.0.0.1:8080}"

case "$provider" in
  github|gitlab) ;;
  *) printf 'Only github and gitlab are supported by this script.\n' >&2; exit 2 ;;
esac
[[ -f "$env_file" ]] || { printf 'Create %s from .env.example first.\n' "$env_file" >&2; exit 1; }

client_id=""
client_secret=""
while IFS='=' read -r key value || [[ -n "$key" ]]; do
  key="${key//$'\r'/}"
  value="${value%$'\r'}"
  [[ "$key" =~ ^[[:space:]]*(#|$) ]] && continue
  key="${key//[[:space:]]/}"
  if [[ "$value" == \"*\" ]]; then value="${value#\"}"; value="${value%\"}"; fi
  if [[ "$value" == \'*\' ]]; then value="${value#\'}"; value="${value%\'}"; fi
  case "$provider:$key" in
    github:GITHUB_CLIENT_ID|gitlab:GITLAB_CLIENT_ID) client_id="$value" ;;
    github:GITHUB_CLIENT_SECRET|gitlab:GITLAB_CLIENT_SECRET) client_secret="$value" ;;
  esac
done <"$env_file"

[[ -n "$client_id" && -n "$client_secret" ]] || {
  printf 'The %s client ID or secret is empty in .env.\n' "$provider" >&2
  exit 1
}

case "$provider" in
  github) scopes='["read:user"]' ;;
  gitlab) scopes='["read_user"]' ;;
esac
response="$(JQ_CLIENT_ID="$client_id" JQ_CLIENT_SECRET="$client_secret" \
  jq -nc --arg name "$provider" --arg provider "$provider" --argjson scopes "$scopes" \
    '{name:$name,provider:$provider,client_id:env.JQ_CLIENT_ID,client_secret:env.JQ_CLIENT_SECRET,scopes:$scopes}' \
  | curl --silent --show-error --request POST "$api/providers" \
      -H 'Content-Type: application/json' --data-binary @- --write-out $'\n%{http_code}')" || {
  unset client_secret
  printf 'Provider registration request failed.\n' >&2
  exit 1
}
unset client_secret
status="${response##*$'\n'}"
case "$status" in
  200|201) printf '%s provider registered (HTTP %s).\n' "$provider" "$status" ;;
  *) printf '%s provider registration failed (HTTP %s).\n' "$provider" "$status" >&2; exit 1 ;;
esac
