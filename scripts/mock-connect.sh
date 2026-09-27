#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"
api="${API_URL:-http://127.0.0.1:8080}"
callback="${CALLBACK_URL:-http://localhost:8080/callback}"
user="${1:?usage: mock-connect.sh USER}"

providers="$(curl --silent --show-error --fail "$api/providers")"
if ! jq -e 'any(.[]; .name == "mock")' <<<"$providers" >/dev/null; then
  client_secret="$(openssl rand -hex 16)"
  mask_value "$client_secret"
  body="$(jq -cn --arg secret "$client_secret" \
    '{name:"mock",provider:"custom",client_id:"smoke-client",client_secret:$secret,scopes:["openid"],provider_options:{auth_code_url:"http://localhost:8090/ci/authorize",token_url:"http://mock-oauth2-server.oidc.svc.cluster.local:8080/ci/token"}}')"
  curl --silent --show-error --fail -H 'Content-Type: application/json' \
    --data-binary "$body" "$api/providers" >/dev/null
  unset client_secret body
fi

connection="$(curl --silent --show-error --fail --request POST \
  "$api/providers/mock/users/$user/connect")"
auth_url="$(jq -er '.auth_url' <<<"$connection")"
state="$(jq -er '.state' <<<"$connection")"
unset connection
redirect_url="$(curl --silent --show-error --output /dev/null --write-out '%{redirect_url}' \
  --request POST --data-urlencode "username=$user" "$auth_url")"
callback_query="$(printf '%s' "$redirect_url" | python3 -c 'import sys,urllib.parse; q=urllib.parse.parse_qs(urllib.parse.urlsplit(sys.stdin.read()).query); print(urllib.parse.urlencode({"code":q["code"][0],"state":q["state"][0]}))')"
[[ "$redirect_url" == "$callback?"* ]] || die "Mock consent did not redirect to callback"
[[ "$redirect_url" == *"$state"* ]] || die "Mock consent returned an unexpected state"
callback_result="$(curl --silent --show-error --fail "$callback?$callback_query")"
[[ "$(jq -r '.status' <<<"$callback_result")" == connected ]] || die "Mock callback did not connect $user"
unset auth_url state redirect_url callback_query callback_result
printf 'PASS mock OAuth connection is ready for %s.\n' "$user"
