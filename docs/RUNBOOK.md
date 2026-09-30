# Start, demonstrate, and stop the project

These instructions are for the configured Windows laptop using Ubuntu 24.04 through WSL. Run the commands in **Ubuntu**, not Windows PowerShell. The project checkout is `~/work/integration-aggregator-takehome`.

## What you are starting

The project provides an internal API that lets other software connect a user's GitHub account and request permission to use GitHub on that user's behalf. The user approves access in GitHub. OpenBao's OAuth plugin exchanges the temporary code, stores the tokens, and handles refresh. Our Python service coordinates these steps.

A browser dashboard lets you run a sample connection and watch each handoff. The separate API documentation still shows every endpoint and its exact request and response shape. Commands demonstrate what another software service would do when calling the API.

| Part | Its job in this project |
|---|---|
| WSL / Ubuntu | Provides the Linux environment inside Windows. |
| Docker | Runs the containers used by the local cluster. |
| Minikube | Creates the local Kubernetes cluster on this laptop. |
| Kubernetes | Runs the app, OpenBao, and the mock identity provider; checks their health. |
| Helm | Installs applications using a chart: a package of Kubernetes templates and settings. |
| Terraform | Sets up OpenBao's plugin, authentication, and access permissions from configuration files. |
| FastAPI service | Receives API requests, remembers consent state, and manages the token request queue. |
| OpenBao + oauthapp | Stores credentials and performs token exchange and refresh. |
| Mock OIDC provider | Simulates consent and short-lived tokens for repeatable tests. |
| GitHub Actions | Rebuilds, publishes, and tests the project on a separate clean machine. |

## 1. Open Ubuntu and select the project

Open **Start**, type **Ubuntu 24.04**, and open it. Leave this window open while using the project.

```bash
cd ~/work/integration-aggregator-takehome
```

`cd` means change directory. The `~` means your Linux home directory. Commands such as `make up` use the files in this project folder.

## 2. Start the stack

```bash
make up
```

`make` reads the repository's Makefile and runs the named set of commands. `up` checks the tools, starts Minikube, installs OpenBao, applies Terraform configuration, starts the mock provider, builds the app image, and deploys the app through Helm.

The first run can take several minutes while images download. Wait until the command returns to the prompt and prints **Stack is ready**. A later run checks and reconciles the same resources.

If it reports that Docker is unavailable, run `sudo systemctl start docker`, then retry `make up`. Type your Linux password into Ubuntu only if it prompts; password characters are not displayed.

## 3. Connect your browser to the cluster

```bash
make port-forward
```

This starts background connections from laptop ports to services inside Kubernetes:

- `localhost:8080`: the Integration Aggregator API.
- `localhost:8090`: the mock provider used by tests.

The command returns to your prompt. A separate terminal is not required. Closing a terminal or pressing Ctrl+C at an idle prompt is not a reliable way to stop these background connections; use the stopping commands below.

Open [the connection walkthrough](http://localhost:8080/) in your Windows browser. `localhost` means this computer. The full [API documentation](http://localhost:8080/docs) is linked from the dashboard and remains available for technical questions.

## 4. Confirm the app is ready

```bash
curl -fsS http://localhost:8080/readyz
kubectl get pods -n aggregator
kubectl get pods -n openbao
kubectl get pods -n oidc
```

`curl` makes an HTTP request. A successful readiness response means the app is able to serve requests and reach OpenBao. `kubectl` talks to Kubernetes. A namespace (`-n`) groups related resources. The app pod should show **1/1** ready and **Running**.

A pod is Kubernetes' unit for running one or more closely related containers. Our main service runs in one app pod.

## 5. Demonstrate the repeatable mock flow

In the dashboard, keep **Sample identity** selected and click **Start sample flow**. Click **Approve and continue** in the sample identity dialog. You should return to the dashboard and see all five steps marked done, a successful token status, recent events, and the actual API requests. This browser flow uses the running mock provider, OpenBao, the app, and its background worker. No real account is needed. The dashboard reads a token-free status endpoint and does not display the token.

For the automated version of the same flow, run:

```bash
make smoke
```

Read the `PASS` lines. This registers the mock provider, starts consent, completes its callback, requests a token asynchronously, and polls for the result. It also checks invalid requests, secret redaction, one-use state, and refresh of a short-lived token.

This command takes about a minute because it deliberately lets a short-lived token age before proving the plugin refreshes it. Results are saved in `.build/reports/smoke.md`.

For the interview, explain: "This test uses a local provider so the complete flow can run automatically in CI. It exercises the same API as the real GitHub integration."

## 6. Demonstrate real GitHub consent

The configured `.env` contains the OAuth app settings and your expected GitHub username. Keep that file private. The OAuth app's callback must be `http://localhost:8080/callback`.

```bash
make demo-github
```

1. The script registers the GitHub provider and opens the Windows browser.
2. Approve the app in GitHub if prompted.
3. Wait for the browser to return to the dashboard and show the completed connection.
4. Return to the Ubuntu window that ran the command and press **Enter**.
5. The script retrieves the token, masks it, and uses it to call GitHub.
6. Success ends with **PASS GitHub API authenticated the expected user** and your username.

Use a newly generated consent flow each time. Refreshing or reusing an old callback URL can produce `invalid_state`, because state is single-use and expires. If that happens, run `make demo-github` again and use its newly opened browser page.

Avoid showing the browser address bar during a recording: callback URLs contain temporary codes and state. The committed [demo transcript](demo/github-flow.md) and [terminal recording](demo/github-flow.cast) contain sanitized actual output.

After the demonstration, open GitHub **Settings → Applications → Authorized OAuth Apps**, choose this project's app, and revoke its authorization. A future demo can request consent again. Keep the OAuth app itself and its local configuration for future demonstrations.

## 7. Explain the asynchronous request

The first token request returns **202 Accepted**, a request ID, and a `Location` pointing to `/requests/{id}`. This means "your request has been queued." A background worker asks OpenBao for the credential while the caller can continue doing other work. The caller polls the request URL until it succeeds or fails.

The token appears only in the successful request result. The dashboard polls `/requests/{id}/status`, which reports progress without sending the token to the browser. `/activity` shows only recent non-secret events and clears on restart. The app does not implement token refresh; OpenBao's plugin does. Temporary request results remain in memory only and expire.

The deployment uses one replica and one Python process. With multiple independent copies, a callback or poll could reach a copy that does not know the state or request ID. Shared state and a durable queue would be needed before scaling this design.

## 8. Stop safely

To stop the running demo while retaining the cluster's configuration and downloaded images:

```bash
bash scripts/port-forward-stop.sh
minikube stop -p aggregator
```

Wait for Minikube to report that it has stopped. You can then close Ubuntu.

The OpenBao server uses development mode with memory-only storage. After its process or pod restarts, previous registrations and user tokens are lost. `make up` restores the declared configuration; `make smoke` or `make demo-github` establishes new test connections. Source code and the ignored `.env` stay on disk.

For a complete teardown, use this instead:

```bash
make down
```

This deletes the `aggregator` Minikube cluster, generated `.build` files, and the local generated OpenBao root token. It keeps the repository and `.env`. Save any uncommitted demo evidence from `.build` before doing this. Committed evidence in `docs/demo` is retained.

## 9. Start again after stopping or rebooting

Open Ubuntu and run:

```bash
cd ~/work/integration-aggregator-takehome
make up
make port-forward
make smoke
```

Then open `http://localhost:8080/` to run the sample browser demo. Open `/docs` from the dashboard to show the technical API reference. Run `make demo-github` when you want to show real consent. Keep Ubuntu open throughout the demonstration.

## Other useful evidence

```bash
make leak-check
make idempotency-check
make perf
helm test integration-aggregator -n aggregator --logs
```

The leak check scans app logs and non-token responses for credential patterns. Idempotency checks that a second `make up` makes no deployed infrastructure changes. The performance test runs k6 inside Kubernetes at 1, 10, and 50 simultaneous virtual users. See [the performance report](../perf/REPORT.md) for measured results and limits.

For the interview, also open the latest successful run on the repository's Actions page. Its clean-machine deployment is evidence that the build can be reproduced beyond this laptop. Read [DESIGN.md](../DESIGN.md) and practise explaining the choices in your own words. Describe this as a working local take-home; production would additionally need durable OpenBao storage, TLS, client authorization, and a design for shared application state.
