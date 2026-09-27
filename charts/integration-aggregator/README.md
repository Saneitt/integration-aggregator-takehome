# integration-aggregator chart

This handwritten chart deploys the single-process FastAPI service. The default values target the local minikube stack and OpenBao service in namespace `openbao`.

## Values

| Key | Default | Meaning |
|---|---|---|
| `replicaCount` | `1` | Must stay at one while OAuth/request state is in process memory. |
| `image.repository` / `image.tag` | `integration-aggregator` / content tag | Service image. |
| `openbao.address` | `http://openbao.openbao.svc:8200` | OpenBao API address. |
| `resources` | modest CPU/memory requests and limits | Pod scheduling and resource ceiling. |
| `probes` | startup, liveness, readiness | Startup grace and process/dependency health. |
| `serviceAccount.tokenAudience` | `openbao` | Audience expected by the OpenBao Kubernetes auth role. |

Run `helm show values ./charts/integration-aggregator` for the complete configuration, including callback URL, service port, image pull secrets, and optional NetworkPolicy. The JSON schema rejects unsupported values and more than one replica.

## Local use

```bash
make up
make port-forward
make smoke
helm test integration-aggregator -n aggregator --logs
```

The chart creates a ServiceAccount with automatic token mounting disabled and explicitly projects a short-lived token for audience `openbao`. The container runs non-root with a read-only root filesystem, dropped capabilities, resource limits, and health probes. `helm test` runs a pinned curl image against `/readyz`.
