# CLAUDE.md: rules for AI assistants in this repo

## What this is
Integration Aggregator: a small Python (FastAPI) service that brokers OAuth access tokens.
OpenBao and the oauthapp plugin do all OAuth work and hold every secret; this service only orchestrates.
Architecture and trade-offs: DESIGN.md. Problem statement: docs/PROBLEM.md.

## Commands
- Fast checks (run before every commit): make lint test chart-lint tf-check shellcheck
- Full local end to end on minikube: make up && make smoke && make leak-check && make perf; make down

## Invariants (never break these)
1. Never log, print, echo, commit or return a client secret, access or refresh token,
   authorization code or OAuth state value. The only exception is the token in GET /requests/{id}.
   Use pydantic SecretStr for secrets; mask values in scripts; no set -x in scripts that touch secrets.
2. No token caching or refresh logic in the service. The plugin owns freshness; always read creds from OpenBao.
3. The service writes nothing to disk (read-only root filesystem).
4. The service is deployed only through charts/integration-aggregator. No raw manifests.
5. Keep files under ~300 lines. Keep boundaries: api -> core -> openbao gateway. The api layer never calls httpx.
6. Pin every version in versions.env; never use :latest.
7. OpenBao dev mode prints its root token: never print OpenBao pod logs in CI or scripts.
8. Every behaviour change comes with a test. CI must stay green.

## Style
Python 3.13, fully typed, ruff-formatted, small functions, explicit errors mapped to problem+json.
Bash: set -euo pipefail, shellcheck-clean. Commits: Conventional Commits; AI-assisted commits
carry a Co-Authored-By trailer.