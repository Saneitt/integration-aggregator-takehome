# Performance report

The local and hosted results below come from separate minikube runs. The hosted values were downloaded from the successful GitHub Actions `perf-report` artifact for [run 36614839224](https://github.com/Saneitt/integration-aggregator-takehome/actions/runs/36614839224).

## Test setup

The E2E job runs the pinned k6 image as a restricted in-cluster Kubernetes Job. It requests an OAuth token from the service, receives `202 Accepted`, and polls the request location every 25 ms. It runs three 30-second constant-VU scenarios: 1, 10, and 50 virtual users. The report records enqueue p50/p95, time-to-token p50/p95, completed tokens per second, and failure rate.

## Results

Local WSL 2, minikube `aggregator`, 4 CPUs / 4096 MiB, OpenBao dev mode, k6 `grafana/k6:2.3.0@sha256:9c2dee7f8ed74d317e4027c06a10f169b625638189de8d4555d0b3486a5aeb34`:

| Scenario | Enqueue p50/p95 (ms) | Time-to-token p50/p95 (ms) | Tokens/s | Failure rate |
|---|---:|---:|---:|---:|
| c1 | 2.4 / 3.0 | 31 / 32 | 1.90 | 0% |
| c10 | 3.0 / 13.1 | 33 / 46.5 | 19.00 | 0% |
| c50 | 3.8 / 25.6 | 34 / 71 | 92.83 | 0% |

**Local source:** `make perf` on 2026-09-26 against the locally deployed build. A second local run on 2026-09-29 also passed with zero failures.

### Hosted GitHub Actions run

[Successful run 36614839224](https://github.com/Saneitt/integration-aggregator-takehome/actions/runs/36614839224), `ubuntu-latest`, Minikube configured with 4 CPUs and 6144 MiB, exact image and chart published by that run. Values below are copied from its downloadable `perf-report` artifact:

| Scenario | Enqueue p50/p95 (ms) | Time-to-token p50/p95 (ms) | Tokens/s | Failure rate |
|---|---:|---:|---:|---:|
| c1 | 2.4 / 3.0 | 30.0 / 32.0 | 1.90 | 0.00% |
| c10 | 2.6 / 8.9 | 31.0 / 40.0 | 19.00 | 0.00% |
| c50 | 3.1 / 22.4 | 33.0 / 58.0 | 93.53 | 0.00% |

## Caveats and next steps

- OpenBao dev mode keeps data in memory and is faster and less durable than a production deployment.
- The service uses one replica and one Python process. The GIL and single event loop limit CPU-bound work; shared in-memory state prevents horizontal scaling.
- k6 shares the minikube node CPU with OpenBao and the service, so results describe this test environment rather than production capacity.
- Each virtual user sleeps 0.5 seconds after an attempt. This is a paced workload (roughly at most 2 attempts/s per VU), not a saturation or maximum-capacity benchmark. Throughput is completed tokens divided by the nominal 30-second scenario duration; final in-flight iterations may finish during the grace period.
- A 25 ms poll interval rounds observed token latency upward and adds load.
- Tokens normally remain valid through this short test, so the numbers do not measure sustained refresh load.

The first scaling improvements to investigate are long polling (for example `Prefer: wait=N`), uvloop, and worker-pool tuning. Horizontal scaling requires shared provider/state/request storage and a durable queue first.
