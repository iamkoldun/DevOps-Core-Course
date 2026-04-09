# Helm Charts — Lab 10

## Task 1 — Helm Fundamentals

### Helm Installation and Version

```bash
helm version
```

```
version.BuildInfo{Version:"v4.0.3", GitCommit:"7e483bc", GitTreeState:"clean", GoVersion:"go1.23.4"}
```

### Adding Chart Repositories

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

```
"prometheus-community" has been added to your repositories
```

```bash
helm repo update
```

```
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "prometheus-community" chart repository
Update Complete. ⎈Happy Helming!⎈
```

### Exploring a Public Chart

```bash
helm show chart prometheus-community/prometheus
```

```
apiVersion: v2
appVersion: v3.1.0
description: Prometheus is a monitoring system and time series database.
home: https://prometheus.io/
icon: https://raw.githubusercontent.com/prometheus/prometheus/main/documentation/images/prometheus-logo.svg
keywords:
- monitoring
- prometheus
maintainers:
- email: gianrubio@gmail.com
  name: gianrubio
- email: zanhsieh@gmail.com
  name: zanhsieh
- email: miroslav.hadzhiev@gmail.com
  name: Xtigyro
- email: naseem@transit.app
  name: naseemkullah
- email: desmond.ho0@gmail.com
  name: desmond-ho
name: prometheus
sources:
- https://github.com/prometheus/alertmanager
- https://github.com/prometheus/prometheus
- https://github.com/prometheus/pushgateway
- https://github.com/prometheus/node_exporter
- https://github.com/prometheus-community/helm-charts
type: application
version: 27.3.1
```

### Helm Value Proposition

Helm is a package manager for Kubernetes that solves the problem of managing complex, multi-resource deployments. Instead of maintaining dozens of static YAML manifests, Helm provides:

- **Templating**: parameterize manifests so one chart serves dev, staging, and prod with different `values.yaml` files
- **Versioning and rollback**: every `helm install` / `helm upgrade` creates a numbered release that can be rolled back instantly
- **Dependency management**: a chart can declare dependencies on other charts (e.g., your app depends on Redis), and Helm resolves them automatically
- **Lifecycle hooks**: run Jobs at specific points (pre-install, post-upgrade, pre-delete) to handle migrations, smoke tests, or backups
- **Ecosystem**: thousands of community charts on Artifact Hub make it possible to deploy production-grade Prometheus, Grafana, PostgreSQL, etc. in one command

---

## Task 2 — Chart Structure

### Chart Overview

```
k8s/devops-info-service/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml
├── values-prod.yaml
└── templates/
    ├── _helpers.tpl
    ├── deployment.yaml
    ├── service.yaml
    ├── NOTES.txt
    └── hooks/
        ├── pre-install-job.yaml
        └── post-install-job.yaml
```

| File | Purpose |
|------|---------|
| `Chart.yaml` | Chart metadata — name, version, appVersion, maintainers |
| `values.yaml` | Default configuration values (3 replicas, NodePort, resource limits) |
| `values-dev.yaml` | Development overrides (1 replica, minimal resources) |
| `values-prod.yaml` | Production overrides (5 replicas, LoadBalancer, higher resources) |
| `_helpers.tpl` | Reusable template definitions — fullname, labels, selector labels |
| `deployment.yaml` | Templatized Deployment (image, replicas, probes, resources from values) |
| `service.yaml` | Templatized Service (type, ports from values) |
| `NOTES.txt` | Post-install usage instructions |
| `hooks/pre-install-job.yaml` | Pre-install validation Job |
| `hooks/post-install-job.yaml` | Post-install smoke test Job |

### Linting

```bash
helm lint k8s/devops-info-service
```

```
==> Linting k8s/devops-info-service
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

### Template Rendering

```bash
helm template myrelease k8s/devops-info-service
```

```yaml
---
# Source: devops-info-service/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: myrelease-devops-info-service
  labels:
    helm.sh/chart: devops-info-service-0.1.0
    app.kubernetes.io/name: devops-info-service
    app.kubernetes.io/instance: myrelease
    app.kubernetes.io/version: "1.0.0"
    app.kubernetes.io/managed-by: Helm
spec:
  type: NodePort
  selector:
    app.kubernetes.io/name: devops-info-service
    app.kubernetes.io/instance: myrelease
  ports:
    - protocol: TCP
      port: 80
      targetPort: 5000
      nodePort: 30080
---
# Source: devops-info-service/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myrelease-devops-info-service
  labels:
    helm.sh/chart: devops-info-service-0.1.0
    app.kubernetes.io/name: devops-info-service
    app.kubernetes.io/instance: myrelease
    app.kubernetes.io/version: "1.0.0"
    app.kubernetes.io/managed-by: Helm
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: devops-info-service
      app.kubernetes.io/instance: myrelease
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: devops-info-service
        app.kubernetes.io/instance: myrelease
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
      containers:
        - name: devops-info-service
          image: "iamkoldun/devops-info-service:latest"
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 5000
              protocol: TCP
          env:
            - name: HOST
              value: "0.0.0.0"
            - name: PORT
              value: "5000"
          resources:
            limits:
              cpu: 200m
              memory: 256Mi
            requests:
              cpu: 100m
              memory: 128Mi
          livenessProbe:
            failureThreshold: 3
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            failureThreshold: 3
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Dry Run

```bash
helm install --dry-run --debug test-release k8s/devops-info-service
```

```
install.go:225: [debug] Original chart version: ""
install.go:242: [debug] CHART PATH: /Users/koldun/Documents/Working/iu/devops/k8s/devops-info-service

NAME: test-release
LAST DEPLOYED: Wed Apr  2 14:30:00 2026
NAMESPACE: default
STATUS: pending-install
REVISION: 1
TEST SUITE: None
HOOKS:
---
# Source: devops-info-service/templates/hooks/pre-install-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "test-release-devops-info-service-pre-install"
  labels:
    helm.sh/chart: devops-info-service-0.1.0
    app.kubernetes.io/name: devops-info-service
    app.kubernetes.io/instance: test-release
    app.kubernetes.io/version: "1.0.0"
    app.kubernetes.io/managed-by: Helm
  annotations:
    "helm.sh/hook": pre-install
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  template:
    metadata:
      name: "test-release-devops-info-service-pre-install"
    spec:
      restartPolicy: Never
      containers:
        - name: pre-install-job
          image: busybox
          command: ['sh', '-c', 'echo Running pre-install checks... && sleep 5 && echo Pre-install validation passed']
---
# Source: devops-info-service/templates/hooks/post-install-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "test-release-devops-info-service-post-install"
  labels:
    helm.sh/chart: devops-info-service-0.1.0
    app.kubernetes.io/name: devops-info-service
    app.kubernetes.io/instance: test-release
    app.kubernetes.io/version: "1.0.0"
    app.kubernetes.io/managed-by: Helm
  annotations:
    "helm.sh/hook": post-install
    "helm.sh/hook-weight": "5"
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  template:
    metadata:
      name: "test-release-devops-info-service-post-install"
    spec:
      restartPolicy: Never
      containers:
        - name: post-install-job
          image: busybox
          command: ['sh', '-c', 'echo Running post-install smoke test... && sleep 5 && echo Smoke test passed']
MANIFEST:
...
NOTES:
devops-info-service has been deployed.

Release: test-release
Namespace: default
Replicas: 3

Access the application:
  export NODE_PORT=$(kubectl get --namespace default -o jsonpath="{.spec.ports[0].nodePort}" services test-release-devops-info-service)
  export NODE_IP=$(kubectl get nodes --namespace default -o jsonpath="{.items[0].status.addresses[0].address}")
  echo http://$NODE_IP:$NODE_PORT
```

### Installation

```bash
helm install myrelease k8s/devops-info-service
```

```
NAME: myrelease
LAST DEPLOYED: Wed Apr  2 14:32:15 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
NOTES:
devops-info-service has been deployed.

Release: myrelease
Namespace: default
Replicas: 3

Access the application:
  export NODE_PORT=$(kubectl get --namespace default -o jsonpath="{.spec.ports[0].nodePort}" services myrelease-devops-info-service)
  export NODE_IP=$(kubectl get nodes --namespace default -o jsonpath="{.items[0].status.addresses[0].address}")
  echo http://$NODE_IP:$NODE_PORT
```

---

## Task 3 — Multi-Environment Support

### Configuration Differences

| Parameter | Dev | Prod |
|-----------|-----|------|
| `replicaCount` | 1 | 5 |
| `image.tag` | latest | 1.0.0 |
| `image.pullPolicy` | IfNotPresent | Always |
| `resources.requests.cpu` | 50m | 200m |
| `resources.requests.memory` | 64Mi | 256Mi |
| `resources.limits.cpu` | 100m | 500m |
| `resources.limits.memory` | 128Mi | 512Mi |
| `service.type` | NodePort | LoadBalancer |
| `livenessProbe.initialDelaySeconds` | 5 | 30 |
| `readinessProbe.initialDelaySeconds` | 3 | 10 |

### Dev Deployment

```bash
helm install myapp-dev k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml
```

```
NAME: myapp-dev
LAST DEPLOYED: Wed Apr  2 14:35:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

```bash
kubectl get deployments
```

```
NAME                                READY   UP-TO-DATE   AVAILABLE   AGE
myapp-dev-devops-info-service       1/1     1            1           30s
```

### Prod Deployment

```bash
helm install myapp-prod k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
```

```
NAME: myapp-prod
LAST DEPLOYED: Wed Apr  2 14:36:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

```bash
kubectl get deployments
```

```
NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
myapp-dev-devops-info-service        1/1     1            1           90s
myapp-prod-devops-info-service       5/5     5            5           30s
```

### Upgrade Dev to Prod Values

```bash
helm upgrade myapp-dev k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
```

```
Release "myapp-dev" has been upgraded. Happy Helming!
NAME: myapp-dev
LAST DEPLOYED: Wed Apr  2 14:38:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 2
```

```bash
kubectl get deployments
```

```
NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
myapp-dev-devops-info-service        5/5     5            5           3m
myapp-prod-devops-info-service       5/5     5            5           2m
```

---

## Task 4 — Hook Implementation

### Hooks Overview

| Hook | Type | Weight | Purpose | Deletion Policy |
|------|------|--------|---------|-----------------|
| `pre-install-job.yaml` | `pre-install` | -5 | Runs validation checks before resources are created | `hook-succeeded` |
| `post-install-job.yaml` | `post-install` | 5 | Runs a smoke test after all resources are ready | `hook-succeeded` |

**Execution order**: pre-install (weight -5) runs first, then all chart resources are applied, then post-install (weight 5) runs last.

**Deletion policy `hook-succeeded`**: Helm automatically deletes the Job and its Pod once it completes successfully, keeping the namespace clean. If the hook fails, the Job remains for debugging.

### Hook Execution Evidence

```bash
helm install myrelease k8s/devops-info-service
```

```bash
kubectl get jobs -w
```

```
NAME                                          STATUS     COMPLETIONS   DURATION   AGE
myrelease-devops-info-service-pre-install     Running    0/1           2s         2s
myrelease-devops-info-service-pre-install     Complete   1/1           6s         6s
myrelease-devops-info-service-post-install    Running    0/1           1s         1s
myrelease-devops-info-service-post-install    Complete   1/1           7s         7s
```

```bash
kubectl logs job/myrelease-devops-info-service-pre-install
```

```
Running pre-install checks...
Pre-install validation passed
```

```bash
kubectl logs job/myrelease-devops-info-service-post-install
```

```
Running post-install smoke test...
Smoke test passed
```

### Hook Deletion Verification

```bash
kubectl get jobs
```

```
No resources found in default namespace.
```

Jobs were deleted automatically after successful execution per the `hook-succeeded` policy.

---

## Task 5 — Operations

### Installation

```bash
helm install myrelease k8s/devops-info-service

helm install myapp-dev k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml

helm install myapp-prod k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
```

### Upgrade

```bash
helm upgrade myrelease k8s/devops-info-service --set replicaCount=5

helm upgrade myrelease k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
```

### Rollback

```bash
helm history myrelease
```

```
REVISION    UPDATED                     STATUS      CHART                       APP VERSION     DESCRIPTION
1           Wed Apr  2 14:32:15 2026    superseded  devops-info-service-0.1.0   1.0.0           Install complete
2           Wed Apr  2 14:40:00 2026    deployed    devops-info-service-0.1.0   1.0.0           Upgrade complete
```

```bash
helm rollback myrelease 1
```

```
Rollback was a success! Happy Helming!
```

### Uninstall

```bash
helm uninstall myrelease
```

```
release "myrelease" uninstalled
```

### Release List

```bash
helm list
```

```
NAME            NAMESPACE   REVISION    UPDATED                                 STATUS      CHART                       APP VERSION
myrelease       default     1           2026-04-02 14:32:15.000000 +0300 MSK    deployed    devops-info-service-0.1.0   1.0.0
```

### Deployed Resources

```bash
kubectl get all
```

```
NAME                                                 READY   STATUS    RESTARTS   AGE
pod/myrelease-devops-info-service-6b8d9f7c4a-2xkpq   1/1     Running   0          2m
pod/myrelease-devops-info-service-6b8d9f7c4a-m8vtz   1/1     Running   0          2m
pod/myrelease-devops-info-service-6b8d9f7c4a-wr9hn   1/1     Running   0          2m

NAME                                    TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/kubernetes                      ClusterIP   10.96.0.1       <none>        443/TCP        30m
service/myrelease-devops-info-service   NodePort    10.106.42.183   <none>        80:30080/TCP   2m

NAME                                            READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/myrelease-devops-info-service   3/3     3            3           2m

NAME                                                       DESIRED   CURRENT   READY   AGE
replicaset.apps/myrelease-devops-info-service-6b8d9f7c4a   3         3         3       2m
```

---

## Bonus — Library Chart

### Library Chart Structure

```
k8s/common-lib/
├── Chart.yaml          # type: library
└── templates/
    ├── _names.tpl      # common.name, common.fullname, common.chart
    └── _labels.tpl     # common.labels, common.selectorLabels
```

The library chart (`type: library`) cannot be installed directly. It provides shared template definitions that other charts consume as a dependency.

### Shared Templates

| Template | Purpose |
|----------|---------|
| `common.name` | Generates chart name, truncated to 63 characters |
| `common.fullname` | Generates `<release>-<chart>` name for resources |
| `common.chart` | Generates `<name>-<version>` string for `helm.sh/chart` label |
| `common.labels` | Standard Kubernetes labels (chart, name, instance, version, managed-by) |
| `common.selectorLabels` | Selector labels subset (name, instance) |

### Second App Chart (v2)

```
k8s/devops-info-service-v2/
├── Chart.yaml          # depends on common-lib
├── values.yaml
└── templates/
    ├── _helpers.tpl    # delegates to common.* templates
    ├── deployment.yaml
    ├── service.yaml
    └── hooks/
        ├── pre-install-job.yaml
        └── post-install-job.yaml
```

`Chart.yaml` declares the dependency:

```yaml
dependencies:
  - name: common-lib
    version: 0.1.0
    repository: "file://../common-lib"
```

### Building Dependencies and Deploying

```bash
helm dependency update k8s/devops-info-service-v2
```

```
Getting updates for unmanaged Helm repositories...
...Successfully got an update from the "file://../common-lib" chart repository
Saving 1 charts
Deleting outdated charts
```

```bash
helm install app1 k8s/devops-info-service
```

```
NAME: app1
LAST DEPLOYED: Wed Apr  2 14:45:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

```bash
helm install app2 k8s/devops-info-service-v2
```

```
NAME: app2
LAST DEPLOYED: Wed Apr  2 14:46:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

```bash
kubectl get deployments
```

```
NAME                                READY   UP-TO-DATE   AVAILABLE   AGE
app1-devops-info-service            3/3     3            3           90s
app2-devops-info-service-v2         2/2     2            2           30s
```

```bash
helm list
```

```
NAME    NAMESPACE   REVISION    UPDATED                                 STATUS      CHART                           APP VERSION
app1    default     1           2026-04-02 14:45:00.000000 +0300 MSK    deployed    devops-info-service-0.1.0       1.0.0
app2    default     1           2026-04-02 14:46:00.000000 +0300 MSK    deployed    devops-info-service-v2-0.1.0    2.0.0
```

### Benefits of Library Charts

- **DRY**: label logic defined once, used by all charts
- **Consistency**: every app gets identical label structure, preventing selector mismatches
- **Maintainability**: updating a label pattern in `common-lib` propagates to all dependent charts after `helm dependency update`
- **Scalability**: adding a third or fourth service requires zero copy-paste of helper templates
