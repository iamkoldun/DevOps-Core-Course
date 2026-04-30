# Lab 13 — GitOps with ArgoCD

GitOps continuous delivery for the `devops-info-service` Helm chart using ArgoCD. Git is the single source of truth; ArgoCD syncs cluster state to match the repository.

**Tech Stack:** ArgoCD 2.13 (server) / 3.3 (client), Kubernetes (minikube), Helm chart from Labs 10–12.

---

## 1. ArgoCD Setup

### Installation

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
kubectl create namespace argocd
helm install argocd argo/argo-cd --namespace argocd --version 7.7.0
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
```

### Accessing the UI

The ArgoCD server runs with TLS by default. To avoid gRPC/TLS issues with the latest CLI against the 2.13 server, the server is switched to HTTP-only and exposed via port-forward:

```bash
kubectl -n argocd patch configmap argocd-cmd-params-cm --type merge \
  -p '{"data":{"server.insecure":"true"}}'
kubectl -n argocd rollout restart deploy/argocd-server

kubectl port-forward svc/argocd-server -n argocd 8080:80
# → http://localhost:8080
```

Retrieve the bootstrap password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
# Username: admin
```

### CLI Login

```bash
brew install argocd
argocd login localhost:8080 --insecure --plaintext \
  --username admin --password <password> --grpc-web
argocd app list
```

Verification output:

```
NAME                             NAMESPACE  STATUS  HEALTH   SYNCPOLICY
argocd/devops-info-service       default    Synced  Healthy  Manual
argocd/devops-info-service-dev   dev        Synced  Healthy  Auto-Prune
argocd/devops-info-service-prod  prod       Synced  Healthy  Manual
```

---

## 2. Application Configuration

Manifests live in `k8s/argocd/`:

| File | Namespace | Values | Sync |
|------|-----------|--------|------|
| `application.yaml` | `default` | `values.yaml` | Manual |
| `application-dev.yaml` | `dev` | `values-dev.yaml` | Automated + selfHeal + prune |
| `application-prod.yaml` | `prod` | `values-prod.yaml` | Manual |
| `applicationset.yaml` | dev + prod | both | Manual (generated) |

All Applications point at:

- **repoURL:** `https://github.com/iamkoldun/DevOps-Core-Course.git`
- **targetRevision:** `lab13`
- **path:** `k8s/devops-info-service`

The `destination.server` is the in-cluster URL `https://kubernetes.default.svc`; each app deploys to a different namespace with its own `helm.valueFiles` entry.

Apply:

```bash
kubectl apply -f k8s/argocd/application.yaml
kubectl apply -f k8s/argocd/application-dev.yaml
kubectl apply -f k8s/argocd/application-prod.yaml

argocd app sync devops-info-service
argocd app sync devops-info-service-prod
# dev auto-syncs
```

### GitOps workflow test

1. Change `replicaCount` in `values-dev.yaml` and push to `lab13`.
2. ArgoCD detects drift within ≤3 min (polling) or immediately on manual refresh.
3. Because dev has `automated: { selfHeal: true, prune: true }`, it converges on its own.

---

## 3. Multi-Environment

| Aspect | Dev | Prod |
|--------|-----|------|
| Namespace | `dev` | `prod` |
| Values file | `values-dev.yaml` | `values-prod.yaml` |
| Replicas | 1 | 5 |
| CPU requests / limits | 50m / 100m | 200m / 500m |
| Memory requests / limits | 64Mi / 128Mi | 256Mi / 512Mi |
| Service type | NodePort (30081) | LoadBalancer |
| Image tag | `latest` | `1.0.0` |
| Sync policy | `automated` + `selfHeal` + `prune` | manual |

### Why manual for prod

- Human review of the diff before deployment.
- Controlled release window (no surprises while oncall is asleep).
- Reversible: a bad commit to Git does not automatically hit prod.
- Matches SOX / change-management processes common in production.

Dev is auto-synced to give fast feedback on chart changes; its blast radius is limited to a developer-facing namespace.

### Verification

```bash
kubectl get pods -n dev
#   1/1 Running          <-- replicas=1 from values-dev.yaml
kubectl get pods -n prod
#   5/5 Running          <-- replicas=5 from values-prod.yaml
argocd app list
kubectl get svc -A | grep devops-info
```

Confirmed: same chart, three independent deployments, each driven by its own values file.

---

## 4. Self-Healing & Sync Policies

### Manual scale test (selfHeal)

```
Before:   replicas=1
$ kubectl scale deployment devops-info-service-dev-devops-info-service \
    -n dev --replicas=5
After scale (t=0):   deployment shows desired=5
After selfHeal (≤20s): ArgoCD reverted to desired=1

Final: 1/1 Running, Sync Status: Synced
```

The `syncPolicy.automated.selfHeal: true` flag causes ArgoCD to periodically reconcile (default 3 min, but cluster-local changes are noticed quickly through the Kubernetes watch cache) and revert any drift from the Git-defined state.

### Pod deletion test

```
$ kubectl delete pod -n dev -l app.kubernetes.io/name=devops-info-service
# Pod recreated in <5s by the ReplicaSet controller
```

This is **Kubernetes** self-healing, not ArgoCD. The `Deployment` → `ReplicaSet` controller enforces the pod count declared in the Deployment spec. ArgoCD did nothing here because the Deployment object itself did not drift — only the owned Pod (a dependent object) was transiently missing.

### Configuration drift test

```
$ kubectl label deployment devops-info-service-dev-devops-info-service \
    -n dev drifted=true --overwrite
# ArgoCD UI: OutOfSync -> diff shows the spurious label
# Within the next reconcile, label is stripped (selfHeal)
```

### When does ArgoCD sync vs Kubernetes heal?

| Event | Reconciled by | Why |
|-------|---------------|-----|
| Pod crash or deletion | Kubernetes (ReplicaSet) | Replica count is the Deployment's concern |
| Node failure | Kubernetes (scheduler + RS) | |
| Manual `kubectl scale` / edit | **ArgoCD** (selfHeal) | The live object diverged from Git |
| Git commit | **ArgoCD** (auto-sync / manual sync) | New desired state in source of truth |
| ConfigMap deleted by mistake | **ArgoCD** (prune off) — it is recreated | Object is tracked in the Application tree |
| Resource removed from Git | **ArgoCD** (prune on) — it is deleted from cluster | Keeps cluster in sync with Git |

**Sync interval:** 3 minutes by default (`timeout.reconciliation` in `argocd-cm`). Can be shortened, or bypassed entirely via a Git webhook.

**Sync triggers:**

- Timer-based poll of the repo.
- Kubernetes watch on live resources (drift detection for selfHeal).
- Manual via UI / `argocd app sync`.
- Optional Git webhook for instant reaction to pushes.

---

## 5. ApplicationSet (Bonus — replaces individual dev/prod Applications)

Per the lab's bonus requirement, the ApplicationSet **replaces** the individual `application-dev.yaml` / `application-prod.yaml` in the live cluster. Those files still live in `k8s/argocd/` as reference for Task 3's configuration, but the running deployments for `dev` and `prod` are generated by the ApplicationSet below.

`k8s/argocd/applicationset.yaml` uses the **List generator** plus `goTemplate` and a `templatePatch` to express the per-environment sync policy in a single manifest:

```yaml
spec:
  goTemplate: true
  generators:
    - list:
        elements:
          - {env: dev,  namespace: dev,  valuesFile: values-dev.yaml,  autoSync: "true"}
          - {env: prod, namespace: prod, valuesFile: values-prod.yaml, autoSync: "false"}
  template:
    metadata: { name: 'devops-info-service-set-{{.env}}' }
    spec:
      source:
        path: k8s/devops-info-service
        helm: { valueFiles: ['{{.valuesFile}}'] }
      destination: { namespace: '{{.namespace}}' }
      syncPolicy:
        syncOptions: [CreateNamespace=true, ServerSideApply=true]
  templatePatch: |
    {{- if eq .autoSync "true" }}
    spec:
      syncPolicy:
        automated: { prune: true, selfHeal: true }
    {{- end }}
```

After `kubectl apply -f applicationset.yaml`, ArgoCD generates two Applications automatically:

```
devops-info-service-set-dev    dev    Auto-Prune + selfHeal
devops-info-service-set-prod   prod   Manual
```

The `templatePatch` conditionally adds `syncPolicy.automated` only for entries with `autoSync: "true"`, so dev and prod keep different sync semantics (Task 3 rationale) while being generated from one manifest.

### Benefits vs individual Applications

| Individual Applications | ApplicationSet |
|--------------------------|---------------|
| One manifest per env — duplicated boilerplate | Single templated spec |
| Manual changes must be repeated N times | One edit applies to all generated apps |
| Adding a new env = copy/paste new YAML | Add one element to the `list` generator |
| No discovery | `git` / `cluster` / `matrix` generators can auto-discover |

### Generator choice

- **List** — small, fixed number of environments; explicit and readable.
- **Git (files / directories)** — mono-repo with many micro-services; auto-onboarding.
- **Cluster** — one app fanned out across every registered cluster (multi-region / fleet).
- **Matrix / Merge** — combine the above (e.g., every service × every cluster).

For this lab the List generator is the right tool: two hard-coded environments, no cluster fleet, no mono-repo discovery.

---

## 6. Directory Layout

```
k8s/argocd/
├── application.yaml          # default ns, manual sync
├── application-dev.yaml      # dev ns, auto-sync + selfHeal + prune
├── application-prod.yaml     # prod ns, manual sync
└── applicationset.yaml       # bonus: List generator for both envs
```

---

## 7. Screenshots

All screenshots are in `docs/lab13/`:

| File | What it shows |
|------|---------------|
| `01-argocd-ui-apps.png` | ArgoCD UI applications list with all apps synced/healthy |
| `02-app-detail-dev.png` | Application details view for `devops-info-service-dev` (tree of resources) |
| `03-app-detail-prod.png` | Application details view for `devops-info-service-prod` |
| `04-selfheal-before.png` | Terminal showing `kubectl get deploy -n dev` with replicas=5 right after manual scale |
| `05-selfheal-after.png` | Terminal showing replicas back to 1 after ArgoCD self-healed |
| `06-applicationset.png` | ApplicationSet-generated apps in the UI |
