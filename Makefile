.DEFAULT_GOAL := help

include versions.env
export MINIKUBE_VERSION KUBERNETES_VERSION HELM_VERSION HELM_DIFF_VERSION TERRAFORM_VERSION
export OPENBAO_CHART_VERSION OAUTHAPP_VERSION OAUTHAPP_TARBALL_SHA256 OAUTHAPP_BINARY_SHA256
export PLUGIN_FETCH_IMAGE MOCK_OIDC_IMAGE K6_IMAGE CURL_IMAGE UV_VERSION KUBECONFORM_VERSION GITLEAKS_VERSION

MINIKUBE_PROFILE ?= aggregator
MINIKUBE_CPUS ?= 4
MINIKUBE_MEMORY ?= 4096
BUILD_IMAGE ?= 1
IMAGE_REPO ?= integration-aggregator
IMAGE_TAG ?= $(shell bash scripts/image-tag.sh)
CHART_REF ?= ./charts/integration-aggregator
CHART_VERSION ?=
IMAGE_PULL_SECRET ?=
CALLBACK_URL ?= http://localhost:8080/callback

export MINIKUBE_PROFILE MINIKUBE_CPUS MINIKUBE_MEMORY BUILD_IMAGE IMAGE_REPO IMAGE_TAG
export CHART_REF CHART_VERSION IMAGE_PULL_SECRET CALLBACK_URL

.PHONY: help preflight up down cluster namespaces bootstrap-secrets openbao configure mock-oidc image app
.PHONY: port-forward register-github register-gitlab smoke leak-check idempotency-check perf demo-github diagnostics
.PHONY: test lint chart-lint tf-check secret-scan shellcheck

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_.-]+:.*## / {printf "%-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

preflight: ## Check local tools and versions
	@bash scripts/preflight.sh

up: preflight cluster namespaces bootstrap-secrets openbao configure mock-oidc image app ## Bring up the complete local stack
	@echo "Stack is ready. Run 'make port-forward' in another terminal."

down: ## Delete the minikube profile and local generated secrets
	@bash scripts/port-forward-stop.sh
	@minikube delete -p "$(MINIKUBE_PROFILE)"
	@rm -rf .build .secrets/openbao-root-token

cluster: ## Start the minikube profile
	@bash scripts/cluster-up.sh

namespaces: ## Apply required namespaces and Pod Security labels
	@kubectl apply -f deploy/namespaces.yaml

bootstrap-secrets: ## Create local bootstrap secrets
	@bash scripts/bootstrap-secrets.sh

openbao: ## Install OpenBao with the oauthapp plugin
	@bash scripts/openbao-up.sh

configure: ## Configure OpenBao with Terraform
	@bash scripts/openbao-configure.sh

mock-oidc: ## Deploy the local OIDC test provider
	@bash scripts/mock-oidc-up.sh

image: ## Build the service image in minikube
	@bash scripts/image-build.sh

app: image ## Deploy the service with its Helm chart
	@bash scripts/app-up.sh

port-forward: ## Forward service and OIDC ports to localhost
	@bash scripts/port-forward.sh

register-github: ## Register GitHub from the local .env
	@bash scripts/register-provider.sh github

register-gitlab: ## Register GitLab from the local .env
	@bash scripts/register-provider.sh gitlab

smoke: ## Run the curl-driven local OIDC flow
	@bash scripts/smoke.sh

leak-check: ## Scan logs and non-token responses for secrets
	@bash scripts/leak-check.sh

idempotency-check: ## Prove make up makes no changes on its second run
	@bash scripts/idempotency-check.sh

perf: ## Run the in-cluster k6 test
	@bash scripts/perf.sh

demo-github: ## Run the real GitHub OAuth demo
	@bash scripts/demo-github.sh

diagnostics: ## Collect redacted diagnostics (never OpenBao logs)
	@bash scripts/diagnostics.sh

test: ## Run service and deployment-script unit tests
	@cd app && uv run pytest --cov=aggregator --cov-report=term-missing
	@python3 -m unittest discover -s scripts/tests -v

lint: ## Run service lint and type checks
	@cd app && uv run ruff check . && uv run ruff format --check . && uv run mypy src

chart-lint: ## Lint and validate the Helm chart
	@bash scripts/chart-lint.sh

tf-check: ## Validate Terraform configuration and tests
	@bash scripts/tf-check.sh

secret-scan: ## Scan repository history for secrets
	@gitleaks git --redact

shellcheck: ## Lint repository shell scripts
	@shellcheck -x scripts/*.sh
