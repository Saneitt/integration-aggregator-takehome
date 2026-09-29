# AI usage

OpenAI Codex was used as an implementation and review assistant for this take-home. The project plan remained the source of requirements and defaults. The assistant helped draft the FastAPI service, Terraform configuration, Helm chart, shell scripts, CI workflow, tests, and documentation.

The implementation was checked against the take-home and the repository build plan, then exercised locally in WSL and minikube. Verification completed so far includes:

- Ruff lint and formatting, strict mypy, and pytest: 24 application tests passed at 89.9% total coverage. Eight deployment-script regression tests also passed.
- Terraform formatting, validation, and two mocked-provider tests.
- Helm lint and kubeconform validation for the pinned Kubernetes version.
- ShellCheck and Bash syntax checks.
- A live local mock OAuth flow covering provider registration/redaction, consent callback, one-use state, async request polling, and token-result placement.
- A 1,000-request concurrent API exercise.
- The service's non-token responses and recent logs passed the current credential-pattern leak gate.
- The OpenBao token refresh proof passed with the 30-second mock issuer; readiness also refreshes expired Kubernetes-auth login tokens.
- The pinned in-cluster k6 test passed at 1, 10, and 50 VUs locally and in [hosted run 36614839224](https://github.com/Saneitt/integration-aggregator-takehome/actions/runs/36614839224). Both sets of measurements and their limits are in `perf/REPORT.md`.

The leak gate was strengthened after it caught `null` optional token fields on pending responses. The response schema now omits those fields until there is a result. This was confirmed by the API test and local smoke flow.

AI output was not treated as proof of upstream behavior. The oauthapp v3 endpoint path, plugin binary/checksums, container image digests, OpenBao Kubernetes authentication, Helm rendering, and minikube image-build path were verified through source metadata or local execution. The minikube image build command needed adjustment after its Docker BuildKit endpoint failed in this environment.

The full hosted run passed lint/tests, artifact publication, a fresh minikube deploy, unchanged second deploy, OAuth smoke, secret checks, k6, and Helm readiness. The image and chart both answered anonymous GHCR pull requests with HTTP 200. A real GitHub consent flow also passed: the user approved in the browser, and the script authenticated the expected username through GitHub without displaying a token. Its sanitized evidence is in `docs/demo/`. Human review is still important, especially the architecture trade-offs and explaining `DESIGN.md` in the candidate's own words. `app/uv.lock` is a generated dependency lockfile and intentionally exceeds the source-file size guideline. No real client secret or token is included in this document.
