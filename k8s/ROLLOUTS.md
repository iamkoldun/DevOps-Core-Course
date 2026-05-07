# Argo Rollouts — Progressive Delivery (Lab 14)

This document describes the progressive delivery setup for the
`devops-info-service` application using
[Argo Rollouts](https://argoproj.github.io/argo-rollouts/).

The Helm chart that drives every rollout used in this lab lives at
[`k8s/devops-info-service-rollout/`](./devops-info-service-rollout). The
chart depends on the shared `common-lib` chart introduced in Lab 10 and
exposes a single switch — `strategy.type` — that selects either the
**canary** or **blue-green** strategy. The same chart also ships an
`AnalysisTemplate` for the bonus task (auto promotion / auto rollback).

---

## 1. Argo Rollouts Setup

### 1.1 Install the controller

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

Verify:

```bash
$ kubectl get pods -n argo-rollouts
NAME                                       READY   STATUS    RESTARTS   AGE
argo-rollouts-74bcdffffc-7gnv8             1/1     Running   0          2m
argo-rollouts-dashboard-78677bc878-5hkgb   1/1     Running   0          2m
```

### 1.2 Install the kubectl plugin

```bash
brew install argoproj/tap/kubectl-argo-rollouts   # macOS

$ kubectl argo rollouts version
kubectl-argo-rollouts: v1.8.3+49fa151
```

### 1.3 Install and access the dashboard

```bash
kubectl apply -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/dashboard-install.yaml

kubectl port-forward svc/argo-rollouts-dashboard -n argo-rollouts 3100:3100
# open http://localhost:3100
```

### 1.4 Rollout vs Deployment

The `Rollout` CRD is a drop-in replacement for `Deployment`. Pod template,
selector, replicas — everything is identical. The differences:

| Field                | Deployment              | Rollout                          |
| -------------------- | ----------------------- | -------------------------------- |
| `strategy.type`      | `RollingUpdate`/`Recreate` | `canary` or `blueGreen`        |
| Traffic management   | service selector only   | active/preview services + steps  |
| Pause / promotion    | not supported           | first-class (`pause`, `promote`) |
| Metric-based gating  | not supported           | `analysis` step + `AnalysisTemplate` |
| Instant rollback     | `kubectl rollout undo`  | switch traffic back to stable RS |
| Replica scaling      | one ReplicaSet active   | two ReplicaSets during rollout   |

The other resources (Service, ConfigMap, Secret, Ingress) keep working
unchanged — Argo Rollouts updates the service `selector` to point traffic
at the right ReplicaSet.

---

## 2. Canary Deployment

### 2.1 Strategy

`values.yaml` ships with the canary strategy enabled:

```yaml
strategy:
  type: canary
  canary:
    steps:
      - setWeight: 20
      - pause: {}                 # manual promotion gate
      - setWeight: 40
      - pause: { duration: 30s }
      - setWeight: 60
      - pause: { duration: 30s }
      - setWeight: 80
      - pause: { duration: 30s }
      - setWeight: 100
```

Five replicas → 20% means one canary pod is brought up, the controller
patches the service selector with the canary's `rollouts-pod-template-hash`
so 1/5 of the traffic goes to the new version. The first `pause: {}` is
indefinite and requires `kubectl argo rollouts promote` to continue.

### 2.2 Install and trigger

```bash
helm install canary k8s/devops-info-service-rollout -n default

# Trigger an update (changes the pod template → new revision)
helm upgrade canary k8s/devops-info-service-rollout -n default \
  --reuse-values \
  --set 'env[0].name=HOST,env[0].value=0.0.0.0' \
  --set 'env[1].name=PORT,env[1].value=5000' \
  --set 'env[2].name=APP_VERSION,env[2].value=v2'

# or use the Argo Rollouts CLI directly:
kubectl argo rollouts set image canary-devops-info-service-rollout \
  devops-info-service-rollout=iamkoldun/devops-info-service:latest
```

### 2.3 Observed progression

```text
Step:  1/9   SetWeight: 20   Status: ॥ Paused        (CanaryPauseStep)
Step:  3/9   SetWeight: 40   Status: ◌ Progressing
Step:  5/9   SetWeight: 60   Status: ◌ Progressing
Step:  7/9   SetWeight: 80   Status: ◌ Progressing
Step:  9/9   SetWeight: 100  Status: ✔ Healthy
```

Screenshots from the dashboard (under `docs/lab14/`):

- `canary-paused-20.png` — canary stopped at the manual gate.
- `canary-progressing.png` — canary moving through 40/60/80 % steps.
- `canary-healthy.png` — fully promoted.

### 2.4 Promotion and abort

```bash
# Inspect
kubectl argo rollouts get rollout canary-devops-info-service-rollout -w

# Move past the manual pause
kubectl argo rollouts promote canary-devops-info-service-rollout

# Stop the rollout — traffic is rerouted entirely to the stable RS
kubectl argo rollouts abort canary-devops-info-service-rollout

# Resume the previously-aborted update
kubectl argo rollouts retry rollout canary-devops-info-service-rollout
```

`abort` is essentially instant: the service selector is rewritten to
point exclusively at the stable ReplicaSet and the canary pods are
scaled down. `retry` brings the canary back from step 0.

---

## 3. Blue-Green Deployment

### 3.1 Strategy

`values-bluegreen.yaml` overlays the canary defaults:

```yaml
strategy:
  type: blueGreen
  blueGreen:
    autoPromotionEnabled: false   # require explicit promote
    scaleDownDelaySeconds: 30     # keep old RS warm for fast rollback
```

The chart conditionally creates a second `Service`
(`<release>-…-preview`) whenever `strategy.type == blueGreen`. The
`Rollout` is wired to the two services:

```yaml
strategy:
  blueGreen:
    activeService: bg-devops-info-service-rollout
    previewService: bg-devops-info-service-rollout-preview
```

### 3.2 Install and trigger

```bash
helm install bg k8s/devops-info-service-rollout -n default \
  -f k8s/devops-info-service-rollout/values.yaml \
  -f k8s/devops-info-service-rollout/values-bluegreen.yaml

# Trigger green deployment
kubectl argo rollouts set image bg-devops-info-service-rollout \
  devops-info-service-rollout=healthapp:v2
```

The controller spins up the green ReplicaSet, points the **preview**
service at it, leaves the **active** service on blue, and pauses with
`Message: BlueGreenPause`.

### 3.3 Test preview vs active

```bash
$ kubectl run testcurl --rm -i --restart=Never \
    --image=curlimages/curl:latest -- \
    sh -c 'curl -s http://bg-devops-info-service-rollout/health; \
           echo; \
           curl -s http://bg-devops-info-service-rollout-preview/health'

{"status":"healthy","timestamp":"...","uptime_seconds":229}   # blue (active)
{"status":"ok","version":"v2"}                                # green (preview)
```

### 3.4 Promotion / instant rollback

```bash
kubectl argo rollouts promote bg-devops-info-service-rollout   # blue ↔ green cutover
kubectl argo rollouts undo    bg-devops-info-service-rollout   # instant rollback
```

Promotion is a single Service `selector` patch — every existing
client connection lands on the green ReplicaSet on the next request.
Rollback is the same operation in reverse, and because
`scaleDownDelaySeconds: 30` keeps the old ReplicaSet alive after the
cutover, the rollback is genuinely instantaneous (no pod startup time).

---

## 4. Strategy Comparison

| Aspect                         | Canary                              | Blue-Green                              |
| ------------------------------ | ----------------------------------- | --------------------------------------- |
| Traffic shift                  | Gradual (% per step)                | Instant (all-or-nothing)                |
| Resource usage during release  | Slightly more than 1× (canary pods) | 2× (full new RS alongside the old one)  |
| Rollback speed                 | Fast (re-route traffic)             | Instant (one-shot selector flip)        |
| Test environment for new ver.  | Mixed traffic, no isolation         | Dedicated preview service / URL         |
| Fit for stateful changes       | Tricky (mixed schemas in flight)    | Better (single version live at a time)  |
| Fit for metric-based analysis  | Native (`analysis` between steps)   | Possible via `prePromotionAnalysis`     |
| Operator effort                | Manual `promote` / auto-pause       | Manual `promote`, simple model          |

**Recommendation:**
- Use **canary** when the application is stateless and you have a SLO
  you can measure between traffic-shift steps — that is the natural
  habitat of automated rollback via `AnalysisTemplate`.
- Use **blue-green** when you need a clean preview environment for
  manual smoke tests, when running mixed versions concurrently is
  unsafe (e.g. backwards-incompatible API or DB migrations), or when
  the cost of a 2× pod footprint for a few minutes is acceptable in
  exchange for an instantaneous rollback.

---

## 5. Bonus — Automated Analysis

`templates/analysistemplate.yaml` defines a Web-provider check that
hits the application's `/health` endpoint via the active service and
expects `status == "ok"`:

```yaml
metrics:
  - name: webcheck
    provider:
      web:
        url: http://<release>-devops-info-service-rollout.<ns>.svc/health
        jsonPath: "{$.status}"
    successCondition: result == "ok"
    interval: 10s
    count: 3
    failureLimit: 1
```

`values-canary-analysis.yaml` wires the template into the canary
strategy as an analysis step right after the first traffic shift:

```yaml
strategy:
  canary:
    steps:
      - setWeight: 20
      - pause: { duration: 20s }
      - analysis:
          templates:
            - templateName: canary-devops-info-service-rollout-success-rate
      - setWeight: 50
      - pause: { duration: 20s }
      - setWeight: 100
```

If three consecutive probes return `status == "ok"` the analysis run
is marked **Successful** and the rollout proceeds to the 50 % step.
If `failureLimit: 1` is hit (any probe returns a non-`ok` status, the
endpoint times out, or returns a non-2xx), the analysis run is marked
**Failed**, the rollout enters the `Degraded` status, traffic is
restored to the stable ReplicaSet and the canary pods are scaled down
— i.e. an automatic rollback.

To demonstrate auto-rollback locally, point the analysis template at a
URL that returns non-`ok` (e.g. an in-cluster httpbin returning
`/status/500`) or break the `/health` endpoint of the canary image.

---

## 6. CLI Commands Reference

| Command                                             | Purpose                                |
| --------------------------------------------------- | -------------------------------------- |
| `kubectl argo rollouts get rollout <name>`          | Static snapshot of a rollout           |
| `kubectl argo rollouts get rollout <name> -w`       | Live tree view of a rollout            |
| `kubectl argo rollouts list rollouts -A`            | List rollouts cluster-wide             |
| `kubectl argo rollouts set image <r> <ctr>=<img>`   | Change the container image             |
| `kubectl argo rollouts promote <name>`              | Continue past a manual pause           |
| `kubectl argo rollouts promote <name> --full`       | Skip remaining steps and go to 100 %   |
| `kubectl argo rollouts abort <name>`                | Stop in-flight rollout, keep stable    |
| `kubectl argo rollouts retry rollout <name>`        | Retry an aborted rollout from step 0   |
| `kubectl argo rollouts undo <name>`                 | Roll back to the previous revision     |
| `kubectl argo rollouts pause <name>`                | Pause a running rollout                |
| `kubectl argo rollouts status <name>`               | Wait until rollout reaches Healthy     |
| `kubectl argo rollouts dashboard`                   | Local dashboard launcher (port 3100)   |

---

## 7. References

- [Argo Rollouts docs](https://argoproj.github.io/argo-rollouts/)
- [Canary strategy](https://argoproj.github.io/argo-rollouts/features/canary/)
- [Blue-Green strategy](https://argoproj.github.io/argo-rollouts/features/bluegreen/)
- [Analysis & progressive delivery](https://argoproj.github.io/argo-rollouts/features/analysis/)
- [Rollout specification](https://argoproj.github.io/argo-rollouts/features/specification/)
