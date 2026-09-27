# Integration Aggregator

[![CI](https://github.com/Saneitt/integration-aggregator-takehome/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Saneitt/integration-aggregator-takehome/actions/workflows/ci.yml)

A small Python service that brokers OAuth access tokens for GitHub and GitLab. OpenBao and its `oauthapp` plugin own OAuth client secrets, code exchange, token storage, and refresh. The service orchestrates consent and returns tokens asynchronously to callers.

## Local quickstart

Run these commands from the WSL Ubuntu checkout. The pinned tools and versions are listed in `versions.env`; Docker must be available to minikube.

```bash
make preflight
make up
make port-forward
```

In another WSL terminal:

```bash
make smoke
make leak-check
make idempotency-check
make perf
helm test integration-aggregator -n aggregator --logs
```

`make up` provisions the local minikube profile, OpenBao, its checksum-verified plugin, Terraform-managed policy/auth configuration, the mock OIDC service, and this service's Helm release. A second run reconciles the same stack. `make down` deletes the cluster and generated bootstrap credentials; it keeps `.env`.

## Real provider demo

The callback URL for the GitHub OAuth App must be `http://localhost:8080/callback`. Copy `.env.example` to `.env`, fill the GitHub OAuth app ID and secret locally, and set `DEMO_GITHUB_USER`. Never send those values in chat or commit `.env`.

```bash
make port-forward
make register-github
make demo-github
```

The demo opens the consent page in the Windows browser, retrieves a token after callback, and verifies the authenticated GitHub login without printing the token. Revoke the app authorization afterward. The recording and transcript belong under `docs/demo/` and must pass the leak check before commit.

## API

- `POST /providers` registers or updates a provider. The client secret is written to OpenBao and omitted from the response.
- `GET /providers` lists non-secret provider metadata.
- `POST /providers/{provider}/users/{user}/connect` starts consent and returns the plugin-generated authorization URL and one-time state.
- `GET /callback` validates and consumes that state, then passes the authorization code to OpenBao.
- `GET /{provider}/{user}` immediately returns `202 Accepted` and a `Location` for polling.
- `GET /requests/{request_id}` reports queued, running, failed, or succeeded. Only this successful result endpoint contains the access token.
- `GET /healthz`, `/readyz`, `/metrics`, and `/docs` provide health, readiness, Prometheus metrics, and local API docs.

For exact schemas, run `make up`, `make port-forward`, then open [http://localhost:8080/docs](http://localhost:8080/docs).

## How CI proves the build

The `lint-test` job runs Python checks and tests, Helm validation, Terraform tests, gitleaks, and ShellCheck. `publish` builds the image with provenance/SBOM and publishes the Helm chart to GHCR. `e2e` deploys those exact artifacts to a fresh minikube cluster and runs reconciliation, mock OAuth, leak, performance, and Helm readiness checks. Reports appear in the Actions job summary and downloadable artifacts.

GHCR packages created by a fork may need their visibility changed to public in the repository's **Packages** settings. The E2E job uses a temporary pull secret while the package is private.

The local k6 measurements and their limitations are documented in [perf/REPORT.md](perf/REPORT.md). Hosted-run results are added after the first green GitHub Actions E2E run.

## Security and design

The service has no database, token cache, or persistent volume. Its single-replica, single-process deployment uses a bounded in-memory queue, one-use OAuth state, Kubernetes authentication with a restricted OpenBao policy, a projected short-lived service token, a read-only root filesystem, and Pod Security `restricted`. Local OpenBao dev mode is intentionally ephemeral and unsuitable for production. See [DESIGN.md](DESIGN.md), [AI usage](docs/AI_USAGE.md), and the preserved [problem statement](docs/PROBLEM.md).

## Repository map

- `app/`: FastAPI service, OpenBao client, async worker, and unit tests.
- `charts/integration-aggregator/`: handwritten deployment chart and Helm readiness test.
- `terraform/`: OpenBao plugin, mount, Kubernetes auth, and least-privilege service identity.
- `deploy/`: local cluster namespaces, OpenBao configuration, and mock OIDC fixture.
- `scripts/`: bootstrap, deploy, smoke, security, performance, and demo workflows.
- `perf/`: k6 test, job template, and performance report.
