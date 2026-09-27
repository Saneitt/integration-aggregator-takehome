#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/scripts/lib.sh"

api="${API_URL:-http://127.0.0.1:8080}"
callback="${CALLBACK_URL:-http://localhost:8080/callback}"
client_secret="$(openssl rand -hex 16)"
mask_value "$client_secret"
umask 077
sensitive_dir="$repo_root/.build/sensitive"
response_dir="$repo_root/.build/responses"
rm -rf "$sensitive_dir" "$response_dir"
mkdir -p "$sensitive_dir" "$response_dir" "$repo_root/.build/reports"
chmod 700 "$sensitive_dir" "$response_dir"
printf '%s' "$client_secret" >"$sensitive_dir/client-secret"
response_count=0
report="$repo_root/.build/reports/smoke.md"
mkdir -p "$(dirname "$report")"
printf '# Mock OAuth smoke report\n\n| Check | Result |\n|---|---|\n' >"$report"

pass() {
  printf 'PASS %s\n' "$1"
  printf '| %s | PASS |\n' "$1" >>"$report"
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  printf '| %s | FAIL |\n' "$1" >>"$report"
  exit 1
}

expect_code() {
  [[ "$http_status" == "$1" ]] || fail "$2 (HTTP $http_status)"
  pass "$2"
}

request() {
  local method="$1" url="$2" response
  shift 2
  response="$(curl --silent --show-error --request "$method" --write-out $'\n%{http_code}' "$url" "$@")" \
    || fail "HTTP request failed"
  http_status="${response##*$'\n'}"
  http_body="${response%$'\n'*}"
  if [[ "$url" != */requests/* ]]; then
    response_count=$((response_count + 1))
    jq -cn --arg status "$http_status" --arg body "$http_body" \
      '{status:$status,body:$body}' >"$response_dir/response-$response_count.json"
    chmod 600 "$response_dir/response-$response_count.json"
  fi
}

post_provider() {
  local status name provider client_id secret scopes options
  name="$1"; provider="$2"; client_id="$3"; secret="$4"; scopes="$5"; options="$6"
  response="$(jq -n --arg name "$name" --arg provider "$provider" --arg client_id "$client_id" \
      --arg client_secret "$secret" --argjson scopes "$scopes" --argjson provider_options "$options" \
      '{name:$name,provider:$provider,client_id:$client_id,client_secret:$client_secret,scopes:$scopes,provider_options:$provider_options}' \
    | curl --silent --show-error --request POST "$api/providers" \
        -H 'Content-Type: application/json' --data-binary @- --write-out $'\n%{http_code}')" \
    || fail "Provider registration request failed"
  http_status="${response##*$'\n'}"
  http_body="${response%$'\n'*}"
  response_count=$((response_count + 1))
  jq -cn --arg status "$http_status" --arg body "$http_body" \
    '{status:$status,body:$body}' >"$response_dir/response-$response_count.json"
  chmod 600 "$response_dir/response-$response_count.json"
}

request GET "$api/readyz"
expect_code 200 "service is ready"

mock_options="$(jq -cn --arg auth 'http://localhost:8090/ci/authorize' \
  --arg token 'http://mock-oauth2-server.oidc.svc.cluster.local:8080/ci/token' \
  '{auth_code_url:$auth,token_url:$token}')"
post_provider mock custom smoke-client "$client_secret" '["openid"]' "$mock_options"
[[ "$http_status" == 201 || "$http_status" == 200 ]] || fail "mock provider registration failed (HTTP $http_status)"
pass "mock provider registered or updated"
if grep -Fq "$client_secret" <<<"$http_body"; then fail "client secret was returned"; fi
post_provider mock custom smoke-client "$client_secret" '["openid"]' "$mock_options"
expect_code 200 "provider registration is idempotent"
request GET "$api/providers"
expect_code 200 "provider list is available"
if grep -Fq "$client_secret" <<<"$http_body"; then fail "client secret appeared in provider list"; fi
pass "provider responses redact client secret"

post_provider providers custom fake "$client_secret" '[]' "$mock_options"
expect_code 422 "reserved provider name is rejected"
missing_secret="$(jq -cn --arg options "$mock_options" \
  '{name:"missing-secret",provider:"custom",client_id:"fake",provider_options:($options|fromjson)}')"
request POST "$api/providers" -H 'Content-Type: application/json' --data-binary "$missing_secret"
expect_code 422 "missing client secret is rejected"

request POST "$api/providers/mock/users/alice/connect"
expect_code 200 "connection returns authorization URL"
auth_url="$(jq -r '.auth_url' <<<"$http_body")"
state="$(jq -r '.state' <<<"$http_body")"
printf '%s' "$state" >"$sensitive_dir/oauth-state-alice"
chmod 600 "$sensitive_dir/oauth-state-alice"
[[ "$auth_url" == http://localhost:8090/ci/authorize* ]] || fail "authorization URL uses an unexpected host"
[[ "$auth_url" == *"$state"* ]] || fail "authorization URL omitted OAuth state"
pass "browser authorization URL points to the local mock issuer"

redirect_url="$(curl --silent --output /dev/null --write-out '%{redirect_url}' \
  --request POST --data-urlencode 'username=alice' "$auth_url")"
printf '%s' "$redirect_url" >"$sensitive_dir/mock-consent-redirect"
chmod 600 "$sensitive_dir/mock-consent-redirect"
[[ "$redirect_url" == "$callback?"* ]] || fail "mock consent did not redirect to the configured callback"
callback_query="$(printf '%s' "$redirect_url" | python3 -c 'import sys,urllib.parse; q=urllib.parse.parse_qs(urllib.parse.urlsplit(sys.stdin.read()).query); print(urllib.parse.urlencode({"code":q["code"][0],"state":q["state"][0]}))')"
printf '%s' "$callback_query" | python3 -c 'import sys,urllib.parse; q=urllib.parse.parse_qs(sys.stdin.read()); print(q["code"][0])' >"$sensitive_dir/authorization-code-alice"
chmod 600 "$sensitive_dir/authorization-code-alice"
request GET "$callback?$callback_query"
expect_code 200 "callback exchanges code"
[[ "$(jq -r '.status' <<<"$http_body")" == connected ]] || fail "callback response status is unexpected"
pass "callback response does not return OAuth code"
request GET "$callback?$callback_query"
expect_code 400 "callback state is single-use"
request GET "$callback?code=fake-code&state=not-a-real-state"
expect_code 400 "unknown OAuth state is rejected"
request GET "$api/mock/bad_user%2Fpart"
expect_code 422 "encoded path separator is rejected"
request GET "$api/nope/alice"
expect_code 404 "unknown provider is rejected"
request GET "$api/requests/00000000-0000-4000-8000-000000000000"
expect_code 404 "unknown request is rejected"
post_provider bad_name custom fake "$client_secret" '[]' "$mock_options"
expect_code 422 "provider name path-injection character is rejected"

request GET "$api/mock/alice"
expect_code 202 "token retrieval is asynchronous"
request_id="$(jq -r '.request_id' <<<"$http_body")"
[[ -n "$request_id" && "$request_id" != null ]] || fail "accepted response omitted request ID"
request_url="$api/requests/$request_id"
for _ in $(seq 1 60); do
  request GET "$request_url"
  status="$(jq -r '.status' <<<"$http_body")"
  [[ "$status" == succeeded || "$status" == failed ]] && break
  sleep 0.2
done
[[ "$status" == succeeded ]] || fail "token request did not succeed"
[[ -n "$(jq -r '.token.access_token // empty' <<<"$http_body")" ]] || fail "successful result omitted access token"
printf '%s' "$(jq -r '.token.access_token' <<<"$http_body")" >"$sensitive_dir/access-token-alice"
chmod 600 "$sensitive_dir/access-token-alice"
pass "token is returned only from the token-request result"

short_options="$(jq -cn --arg auth 'http://localhost:8090/ci-short/authorize' \
  --arg token 'http://mock-oauth2-server.oidc.svc.cluster.local:8080/ci-short/token' \
  '{auth_code_url:$auth,token_url:$token}')"
post_provider mock-short custom smoke-short "$client_secret" '["openid"]' "$short_options"
[[ "$http_status" == 201 || "$http_status" == 200 ]] || fail "short-lived mock provider registration failed"
request POST "$api/providers/mock-short/users/carol/connect"
expect_code 200 "short-lived token consent starts"
short_auth_url="$(jq -r '.auth_url' <<<"$http_body")"
short_state="$(jq -r '.state' <<<"$http_body")"
printf '%s' "$short_state" >"$sensitive_dir/oauth-state-carol"
chmod 600 "$sensitive_dir/oauth-state-carol"
short_redirect="$(curl --silent --show-error --output /dev/null --write-out '%{redirect_url}' \
  --request POST --data-urlencode 'username=carol' "$short_auth_url")"
printf '%s' "$short_redirect" >"$sensitive_dir/short-consent-redirect"
chmod 600 "$sensitive_dir/short-consent-redirect"
[[ "$short_redirect" == "$callback?"* ]] || fail "short-lived mock consent returned an error redirect"
short_keys="$(printf '%s' "$short_redirect" | python3 -c 'import sys,urllib.parse; print(",".join(sorted(urllib.parse.parse_qs(urllib.parse.urlsplit(sys.stdin.read()).query))))')"
[[ ",$short_keys," == *,code,* && ",$short_keys," == *,state,* ]] \
  || fail "short-lived mock consent redirect omitted code or state"
short_query="$(printf '%s' "$short_redirect" | python3 -c 'import sys,urllib.parse; q=urllib.parse.parse_qs(urllib.parse.urlsplit(sys.stdin.read()).query); print(urllib.parse.urlencode({"code":q["code"][0],"state":q["state"][0]}))')"
printf '%s' "$short_query" | python3 -c 'import sys,urllib.parse; q=urllib.parse.parse_qs(sys.stdin.read()); print(q["code"][0])' >"$sensitive_dir/authorization-code-carol"
chmod 600 "$sensitive_dir/authorization-code-carol"
[[ "$short_redirect" == *"$short_state"* ]] \
  || fail "short-lived mock consent returned an unexpected redirect"
request GET "$callback?$short_query"
expect_code 200 "short-lived mock callback connects"

retrieve_token() {
  local provider_name="$1" user_name="$2" id state response
  response="$(curl --silent --show-error --fail --write-out $'\n%{http_code}' \
    "$api/$provider_name/$user_name")" || fail "token retrieval request failed"
  [[ "${response##*$'\n'}" == 202 ]] || fail "token retrieval did not return HTTP 202"
  id="$(jq -er '.request_id' <<<"${response%$'\n'*}")"
  for _ in $(seq 1 60); do
    state="$(curl --silent --show-error --fail "$api/requests/$id")" \
      || fail "token request polling failed"
    case "$(jq -r '.status' <<<"$state")" in
      succeeded) jq -er '.token.access_token' <<<"$state"; return 0 ;;
      failed) fail "short-lived token request failed" ;;
    esac
    sleep 0.2
  done
  fail "token request polling timed out"
}

short_token_one="$(retrieve_token mock-short carol)"
mask_value "$short_token_one"
printf '%s' "$short_token_one" >"$sensitive_dir/short-token-before-refresh"
chmod 600 "$sensitive_dir/short-token-before-refresh"
short_hash_one="$(printf '%s' "$short_token_one" | sha256sum | cut -d' ' -f1)"
unset short_token_one
refreshed=0
for _ in $(seq 1 30); do
  sleep 3
  short_token_two="$(retrieve_token mock-short carol)"
  mask_value "$short_token_two"
  printf '%s' "$short_token_two" >"$sensitive_dir/short-token-after-refresh"
  chmod 600 "$sensitive_dir/short-token-after-refresh"
  short_hash_two="$(printf '%s' "$short_token_two" | sha256sum | cut -d' ' -f1)"
  unset short_token_two
  if [[ "$short_hash_two" != "$short_hash_one" ]]; then
    refreshed=1
    break
  fi
done
[[ "$refreshed" == 1 ]] || fail "short-lived OAuth token did not refresh within 90 seconds"
pass "OpenBao plugin refreshed a short-lived token without service refresh logic"
unset short_hash_one short_hash_two short_options short_auth_url short_state short_redirect short_keys short_query
unset client_secret callback_query auth_url redirect_url http_body response

printf '\nReport: %s\n' "$report"
