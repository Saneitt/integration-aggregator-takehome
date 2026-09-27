#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"
api="${API_URL:-http://127.0.0.1:8080}"
env_file="$repo_root/.env"
[[ -f "$env_file" ]] || die "Create .env from .env.example and fill in the GitHub OAuth app values locally."

demo_user=""
while IFS='=' read -r key value || [[ -n "$key" ]]; do
  key="${key//$'\r'/}"
  value="${value%$'\r'}"
  [[ "$key" =~ ^[[:space:]]*(#|$) ]] && continue
  key="${key//[[:space:]]/}"
  if [[ "$value" == \"*\" ]]; then value="${value#\"}"; value="${value%\"}"; fi
  case "$key" in
    DEMO_GITHUB_USER) demo_user="$value" ;;
  esac
done <"$env_file"
[[ -n "$demo_user" ]] || die "Set DEMO_GITHUB_USER in .env to your GitHub username."

bash "$repo_root/scripts/register-provider.sh" github
connection="$(curl --silent --show-error --fail --request POST \
  "$api/providers/github/users/$demo_user/connect")" || die "Could not start GitHub consent."
auth_url="$(jq -er '.auth_url' <<<"$connection")"
unset connection
powershell_script="Start-Process -FilePath '$auth_url'"
encoded_powershell_script="$(printf '%s' "$powershell_script" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)"
unset powershell_script
if ! powershell.exe -NoProfile -NonInteractive -EncodedCommand "$encoded_powershell_script" >/dev/null 2>&1; then
  unset auth_url encoded_powershell_script
  die "Could not open the Windows browser. Run this script from WSL with Windows interop enabled."
fi
unset auth_url encoded_powershell_script
printf 'Opened the GitHub consent page in your Windows browser. Complete consent and return to this terminal.\n'
read -r -p 'Press Enter after the callback page has loaded: ' || die "Input was closed before consent completed."

accepted="$(curl --silent --show-error --fail --write-out $'\n%{http_code}' \
  "$api/github/$demo_user")" || die "Could not enqueue the token request."
status="${accepted##*$'\n'}"
body="${accepted%$'\n'*}"
[[ "$status" == 202 ]] || die "Expected HTTP 202 while requesting token."
location="$(jq -er '.request_id' <<<"$body")"
unset accepted body
token=""
for attempt in $(seq 1 60); do
  result="$(curl --silent --show-error --fail "$api/requests/$location")" \
    || die "Could not poll token request."
  result_status="$(jq -r '.status' <<<"$result")"
  if [[ "$result_status" == succeeded ]]; then
    token="$(jq -er '.token.access_token' <<<"$result")"
    break
  elif [[ "$result_status" == failed ]]; then
    error_code="$(jq -r '.error.code // "unknown"' <<<"$result")"
    unset result
    die "Token request failed ($error_code); confirm consent completed and retry."
  fi
  unset result
  sleep 0.25
done
unset location
[[ -n "$token" ]] || die "Timed out after $((attempt * 250)) ms waiting for GitHub token."
mask_value "$token"
printf 'Token acquired (masked; %s characters).\n' "${#token}"
login="$(printf 'header = "Authorization: Bearer %s"\n' "$token" \
  | curl --silent --show-error --fail --config - https://api.github.com/user \
  | jq -er '.login')" \
  || { unset token; die "GitHub rejected the token or returned an unexpected response."; }
unset token
[[ "$login" == "$demo_user" ]] || die "GitHub authenticated as a different account."
printf 'PASS GitHub API authenticated the expected user: %s\n' "$login"
