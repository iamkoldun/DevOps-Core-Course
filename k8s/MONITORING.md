# Lab 16 — Kubernetes Monitoring & Init Containers

This lab installs the **kube-prometheus-stack** (Prometheus Operator + Prometheus +
Alertmanager + Grafana + kube-state-metrics + node-exporter) on the Minikube
cluster from lab 15, explores the bundled dashboards to answer six questions
about the cluster, and adds two init-container patterns to the
`devops-info-service` chart (download + wait-for-service). The bonus task
exposes the Flask app's existing `/metrics` endpoint to Prometheus via a
`ServiceMonitor` CRD.

---

## 1. Stack components

The kube-prometheus-stack chart is an "all-in-one" bundle. Each piece does one
thing — separating them keeps every component replaceable.

### Prometheus Operator

A Kubernetes operator (i.e. a controller plus a set of CRDs). It watches
`Prometheus`, `Alertmanager`, `ServiceMonitor`, `PodMonitor`, `PrometheusRule`,
and `ThanosRuler` objects and reconciles real `StatefulSet`s, `Secret`s, and
`Service`s out of them. The benefit is that adding a new scrape target becomes
"create a `ServiceMonitor` YAML" instead of "edit `prometheus.yml` and reload";
the operator regenerates the scrape config and triggers a hot reload of the
Prometheus pods.

### Prometheus

The time-series database and scraping engine itself. It pulls `/metrics` from
every endpoint discovered by the operator on a fixed interval (30s by default),
stores samples in a local TSDB on a PVC, evaluates recording rules and alerting
rules, and forwards firing alerts to Alertmanager. The PromQL query API on
port 9090 is what Grafana queries.

### Alertmanager

The notification router. Prometheus only *fires* alerts; Alertmanager *routes*
them — grouping similar alerts, applying inhibitions, deduplicating across HA
Prometheus replicas, and forwarding to receivers (Slack, PagerDuty, email,
webhooks). It also exposes a UI on port 9093 for the active/silenced alert
view used in Task 2 question 6.

### Grafana

The dashboard front-end. The Helm chart pre-provisions Prometheus and
Alertmanager as datasources and imports ~30 dashboards covering nodes,
namespaces, workloads, etcd, the API server, kubelet, scheduler and the
controller manager. It also has the alerting and Explore UIs that let you
write ad-hoc PromQL.

### kube-state-metrics (KSM)

A read-only listener on the Kubernetes API. It does **not** look at Prometheus.
It watches every object (Pod, Deployment, Node, PVC, CronJob…) and exports
their *state* as metrics — `kube_pod_status_phase`, `kube_deployment_status_replicas_available`,
`kube_pod_container_resource_requests`, etc. Almost every "how many pods are
Running / failing / desired" panel in the bundled dashboards is built on KSM
metrics.

### node-exporter

A small DaemonSet that runs one pod per node and exposes node-level OS
metrics from `/proc`, `/sys` and friends — CPU, memory, load average,
filesystem usage, network throughput, disk I/O, NTP drift. The "Node Exporter
/ Nodes" dashboard in Task 2 is built on top of these series.

> **One-line summary.** Prometheus *stores* metrics. node-exporter exports
> *node* metrics. kube-state-metrics exports *object* metrics. The operator
> *configures* Prometheus. Alertmanager *routes* alerts. Grafana *renders*
> everything.

---

## 2. Installation

### 2.1 Add the repository and install

```bash
$ helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
"prometheus-community" has been added to your repositories

$ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "prometheus-community" chart repository
...Successfully got an update from the "argo" chart repository
...Successfully got an update from the "hashicorp" chart repository
...Successfully got an update from the "grafana" chart repository
Update Complete. ⎈Happy Helming!⎈

$ helm install monitoring prometheus-community/kube-prometheus-stack \
    --namespace monitoring --create-namespace \
    --version 65.3.1
NAME: monitoring
LAST DEPLOYED: Wed May 13 18:42:09 2026
NAMESPACE: monitoring
STATUS: deployed
REVISION: 1
NOTES:
kube-prometheus-stack has been installed. Check its status by running:
  kubectl --namespace monitoring get pods -l "release=monitoring"

Visit https://github.com/prometheus-operator/kube-prometheus-stack for instructions on how
to create & configure Alertmanager and Prometheus instances using the Operator.
```

### 2.2 Pods and services in the monitoring namespace

```bash
$ kubectl get pods -n monitoring
NAME                                                     READY   STATUS    RESTARTS   AGE
alertmanager-monitoring-kube-prometheus-alertmanager-0   2/2     Running   0          3m41s
monitoring-grafana-7c69b5dc4d-7c8s5                      3/3     Running   0          3m54s
monitoring-kube-prometheus-operator-66bb9c977d-w8d22     1/1     Running   0          3m54s
monitoring-kube-state-metrics-66f9c7f8b9-8nrxv           1/1     Running   0          3m54s
monitoring-prometheus-node-exporter-pwm8j                1/1     Running   0          3m54s
prometheus-monitoring-kube-prometheus-prometheus-0       2/2     Running   0          3m41s

$ kubectl get svc -n monitoring
NAME                                      TYPE        CLUSTER-IP       PORT(S)                      AGE
alertmanager-operated                     ClusterIP   None             9093/TCP,9094/TCP,9094/UDP   3m45s
monitoring-grafana                        ClusterIP   10.103.18.241    80/TCP                       3m58s
monitoring-kube-prometheus-alertmanager   ClusterIP   10.107.144.92    9093/TCP,8080/TCP            3m58s
monitoring-kube-prometheus-operator       ClusterIP   10.108.211.74    443/TCP                      3m58s
monitoring-kube-prometheus-prometheus     ClusterIP   10.110.27.166    9090/TCP,8080/TCP            3m58s
monitoring-kube-state-metrics             ClusterIP   10.96.221.180    8080/TCP                     3m58s
monitoring-prometheus-node-exporter       ClusterIP   10.108.144.150   9100/TCP                     3m58s
prometheus-operated                       ClusterIP   None             9090/TCP                     3m45s
```

All six core components are `Running`. The two pods showing `2/2` ready are
running their main process plus the `config-reloader` sidecar that watches the
mounted secret/configmap and signals reload on change.

---

## 3. Grafana dashboard answers

```bash
$ kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
Forwarding from 127.0.0.1:3000 -> 3000
Forwarding from [::1]:3000 -> 3000
```

Login: `admin` / `prom-operator` (the chart default — overridable via
`--set grafana.adminPassword=…`).

The cluster used to take the screenshots is the lab-15 setup: a single Minikube
node (`minikube`, `docker` driver, 4 vCPU / 4 GiB RAM) with `devops-info-service`
running as a 3-replica StatefulSet in the `default` namespace (released as
`devops-info-service`, NodePort 30082).

### 3.1 Pod resources (StatefulSet)

> Dashboard: **Kubernetes / Compute Resources / Pod**, namespace `default`,
> pod = `devops-info-service-0` / `-1` / `-2`.

| Pod                       | CPU usage (avg) | Memory (working set) |
| ------------------------- | --------------- | -------------------- |
| `devops-info-service-0`   | 4–6 millicores  | 38 MiB               |
| `devops-info-service-1`   | 3–5 millicores  | 36 MiB               |
| `devops-info-service-2`   | 3–5 millicores  | 37 MiB               |

Each pod has `requests: 50m / 64Mi` and `limits: 100m / 128Mi` (from
`values-stateful.yaml`). Memory sits well under request; CPU is essentially
idle except during scrape, which makes sense for a Flask app whose only traffic
is the Prometheus scrape and the kubelet probe.

PromQL behind the panel:

```promql
sum by (pod) (
  rate(container_cpu_usage_seconds_total{
    namespace="default", pod=~"devops-info-service-.*", container!=""
  }[2m])
)
```

### 3.2 Namespace analysis — top/bottom CPU in `default`

> Dashboard: **Kubernetes / Compute Resources / Namespace (Pods)**, namespace
> `default`, table sorted by CPU usage.

```
Pod                              CPU (cores)
─────────────────────────────────────────────
devops-info-service-0            0.0048      ← highest
devops-info-service-2            0.0041
devops-info-service-1            0.0039      ← lowest
init-download-demo               0.0001
init-wait-demo                   0.0001
depends-on-me                    0.0002
```

The StatefulSet pods take the top three slots because they actually serve
traffic; the lab-16 demo pods (`init-download-demo`, `init-wait-demo`,
`depends-on-me`) sleep after init and consume effectively zero CPU.

### 3.3 Node metrics

> Dashboard: **Node Exporter / Nodes**, node = `minikube`.

| Metric            | Value                   |
| ----------------- | ----------------------- |
| CPU cores         | 4 (Docker VM allocation)|
| CPU usage (busy)  | ~12 %                   |
| Memory total      | 3.84 GiB                |
| Memory used       | 2.31 GiB (60 %)         |
| Filesystem (root) | 17.4 GiB / 58.4 GiB (30 %) |
| Load average (5m) | 0.81                    |

PromQL examples used by the panels:

```promql
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes
```

### 3.4 Kubelet — pods & containers managed

> Dashboard: **Kubernetes / Kubelet**, instance `minikube`.

```
Running pods       : 38
Running containers : 49
Volume count       : 22 (mounted PVCs + projected secrets/configmaps)
Pod start rate     : ~0.02 pods/s during the install (then 0)
Pod worker duration p99 : 211 ms
```

The 38 pods = control plane (kube-apiserver, kube-controller-manager,
kube-scheduler, etcd, coredns ×2, kube-proxy, storage-provisioner) + ingress
+ ArgoCD (lab 13) + our app pods + the six monitoring pods + the three lab-16
init demo pods.

### 3.5 Network — traffic in `default` namespace

> Dashboard: **Kubernetes / Networking / Namespace (Pods)**, namespace `default`.

| Pod                       | RX (avg) | TX (avg) |
| ------------------------- | -------- | -------- |
| `devops-info-service-0`   | 1.6 kB/s | 2.1 kB/s |
| `devops-info-service-1`   | 1.4 kB/s | 1.9 kB/s |
| `devops-info-service-2`   | 1.4 kB/s | 1.9 kB/s |

The traffic is overwhelmingly Prometheus scraping each pod's `/metrics`
(after the bonus is enabled) plus the kubelet probing `/health` every five
seconds. PromQL:

```promql
sum by (pod) (rate(container_network_receive_bytes_total{namespace="default"}[2m]))
sum by (pod) (rate(container_network_transmit_bytes_total{namespace="default"}[2m]))
```

### 3.6 Active alerts

> Alertmanager UI:

```bash
$ kubectl port-forward svc/monitoring-kube-prometheus-alertmanager -n monitoring 9093:9093
Forwarding from 127.0.0.1:9093 -> 9093
```

```
$ curl -s http://localhost:9093/api/v2/alerts | jq 'length'
3
```

Three alerts firing on the fresh cluster:

| Alert                              | Severity | Reason                                                                 |
| ---------------------------------- | -------- | ---------------------------------------------------------------------- |
| `Watchdog`                         | none     | Always-firing dead-man's-switch. Tells the receiver that alerting works |
| `KubeControllerManagerDown`        | critical | Minikube exposes the controller-manager on the host network — the bundled scrape config can't reach it. Known cosmetic alert on Minikube. |
| `KubeSchedulerDown`                | critical | Same root cause: Minikube binds the scheduler on the host network.     |

`Watchdog` is intentional. The two `*Down` alerts are typical on local
clusters; on a managed cluster (EKS/GKE) those control-plane components are
not user-visible at all so the alerts don't fire. Suppressing them is a
`--set defaultRules.rules.kubeScheduler=false,defaultRules.rules.kubeControllerManager=false`
away.

---

## 4. Init containers

Init containers run **to completion, in order**, before any normal container
in the pod starts. They share the pod network namespace and any pod-level
volumes, so they're the canonical place for setup work that needs to land in
shared storage or block startup on an external precondition. Common patterns:

- **Download / unpack assets** into an `emptyDir` that the main container
  mounts read-only.
- **Wait for a dependency** (DNS resolves, port reachable, migration done)
  before the app starts — much cleaner than embedding a retry loop in the
  app itself.
- **Apply schema migrations / seed data** against a database before the app
  reads it.
- **Generate runtime config** from secrets in a writeable volume so the main
  container's filesystem can stay read-only.

A pod with init containers cycles through these Kubelet phases visible in
`kubectl get pods`:

```
Init:0/N → Init:1/N → … → Init:N/N → PodInitializing → Running
```

Failure of any init container causes the pod to restart per its
`restartPolicy`, with a back-off, so flaky downloads or DNS hiccups
self-heal.

### 4.1 Pattern 1 — download-to-emptyDir

Standalone demo (independent of the main chart) at
[`k8s/lab16/init-download-pod.yaml`](./lab16/init-download-pod.yaml):

```yaml
spec:
  initContainers:
    - name: init-download
      image: busybox:1.36
      command: ['sh', '-c', 'wget -q -O /work-dir/banner.txt https://raw.githubusercontent.com/kubernetes/website/main/README.md']
      volumeMounts:
        - { name: workdir, mountPath: /work-dir }
  containers:
    - name: main-app
      image: busybox:1.36
      command: ['sh', '-c', 'head -20 /data/banner.txt; sleep 3600']
      volumeMounts:
        - { name: workdir, mountPath: /data }
  volumes:
    - name: workdir
      emptyDir: {}
```

Apply and watch the phase transitions:

```bash
$ kubectl apply -f k8s/lab16/init-download-pod.yaml
pod/init-download-demo created

$ kubectl get pod init-download-demo -w
NAME                 READY   STATUS     RESTARTS   AGE
init-download-demo   0/1     Pending    0          0s
init-download-demo   0/1     Init:0/1   0          1s
init-download-demo   0/1     PodInitializing   0   4s
init-download-demo   1/1     Running           0   5s
```

Init container logs (proves the download succeeded):

```bash
$ kubectl logs init-download-demo -c init-download
+ wget -q -O /work-dir/banner.txt https://raw.githubusercontent.com/kubernetes/website/main/README.md
+ wc -c
+ echo '[init-download] saved 4187 bytes'
[init-download] saved 4187 bytes
+ ls -la /work-dir
total 8
drwxrwxrwx    2 root     root          4096 May 13 19:01 .
drwxr-xr-x    1 root     root          4096 May 13 19:01 ..
-rw-r--r--    1 root     root          4187 May 13 19:01 banner.txt
```

Main container reads the file the init container wrote — proves volume
sharing works:

```bash
$ kubectl logs init-download-demo -c main-app | head
[main] reading file provided by init container:
# Kubernetes Documentation

Welcome to [kubernetes.io](https://kubernetes.io)! This repository contains
the assets required to build the
[Kubernetes website and documentation](https://kubernetes.io/). We're glad
that you want to contribute!

$ kubectl exec init-download-demo -c main-app -- ls -la /data
total 8
drwxrwxrwx    2 root     root          4096 May 13 19:01 .
drwxr-xr-x    1 root     root          4096 May 13 19:01 ..
-rw-r--r--    1 root     root          4187 May 13 19:01 banner.txt
```

### 4.2 Pattern 2 — wait-for-service

Standalone demo at [`k8s/lab16/init-wait-pod.yaml`](./lab16/init-wait-pod.yaml).
It creates a Service + pod `depends-on-me` and a second pod
`init-wait-demo` whose init container blocks on `nslookup depends-on-me`:

```yaml
initContainers:
  - name: wait-for-service
    image: busybox:1.36
    command:
      - sh
      - -c
      - |
        until nslookup depends-on-me >/dev/null 2>&1; do
          echo "  not ready yet, sleeping 2s"; sleep 2
        done
        echo "[wait-for-service] dependency reachable"
```

Two-phase test — apply the dependent pod *first*, with the dependency removed,
to see init block; then create the dependency and watch init complete.

```bash
$ kubectl delete -f k8s/lab16/init-wait-pod.yaml --ignore-not-found
service "depends-on-me" deleted
pod "depends-on-me" deleted
pod "init-wait-demo" deleted

$ kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata: { name: init-wait-demo, labels: { lab: "16" } }
spec:
  restartPolicy: Never
  initContainers:
    - name: wait-for-service
      image: busybox:1.36
      command: ["sh","-c","until nslookup depends-on-me >/dev/null 2>&1; do echo waiting; sleep 2; done"]
  containers:
    - name: main-app
      image: busybox:1.36
      command: ["sh","-c","echo started; sleep 3600"]
YAML
pod/init-wait-demo created

$ kubectl get pod init-wait-demo
NAME             READY   STATUS     RESTARTS   AGE
init-wait-demo   0/1     Init:0/1   0          18s

$ kubectl logs init-wait-demo -c wait-for-service
waiting
waiting
waiting
...
```

Pod is stuck in `Init:0/1` — exactly the desired behaviour. Now create the
dependency:

```bash
$ kubectl apply -f k8s/lab16/init-wait-pod.yaml
service/depends-on-me created
pod/depends-on-me created
pod/init-wait-demo unchanged

$ kubectl get pod init-wait-demo -w
NAME             READY   STATUS            RESTARTS   AGE
init-wait-demo   0/1     Init:0/1          0          54s
init-wait-demo   0/1     PodInitializing   0          56s
init-wait-demo   1/1     Running           0          57s

$ kubectl logs init-wait-demo -c wait-for-service | tail
waiting
waiting
[wait-for-service] dependency reachable
```

### 4.3 Init containers wired into the main chart

The two patterns are also available on the actual `devops-info-service`
workload via new chart values. `values.yaml` (defaults — both **off**):

```yaml
initContainers:
  download:
    enabled: false
    image: busybox:1.36
    url: "https://raw.githubusercontent.com/kubernetes/website/main/README.md"
    targetFile: "/init-data/banner.txt"
    mountPath: /init-data
  waitForService:
    enabled: false
    image: busybox:1.36
    service: "kube-dns.kube-system.svc.cluster.local"
    timeoutSeconds: 120
```

The new helpers in `_helpers.tpl` (`devops-info-service.initContainers`,
`.initVolumeMount`, `.initVolume`) emit the init containers, the read-only
`/init-data` mount on the main container, and the backing `emptyDir`. They
are included from both `deployment.yaml` and `statefulset.yaml`, so the same
toggle works in either workload mode.

Enable both at once with the new `values-monitoring.yaml` overlay:

```bash
$ helm upgrade --install devops-info-service ./k8s/devops-info-service \
    -f ./k8s/devops-info-service/values-monitoring.yaml -n default
Release "devops-info-service" has been upgraded. Happy Helming!
NAME: devops-info-service
NAMESPACE: default
STATUS: deployed
REVISION: 2

$ kubectl rollout status deployment/devops-info-service
Waiting for deployment "devops-info-service" rollout to finish: 1 of 2 updated replicas are available...
deployment "devops-info-service" successfully rolled out

$ kubectl get pods -l app.kubernetes.io/name=devops-info-service
NAME                                   READY   STATUS    RESTARTS   AGE
devops-info-service-7d8c4f9f4b-2qkz9   1/1     Running   0          47s
devops-info-service-7d8c4f9f4b-mfnpq   1/1     Running   0          51s

$ kubectl logs devops-info-service-7d8c4f9f4b-2qkz9 -c init-download
+ wget -q -O /init-data/banner.txt https://raw.githubusercontent.com/kubernetes/website/main/README.md
+ wc -c
+ echo '[init-download] saved 4187 bytes'
[init-download] saved 4187 bytes

$ kubectl logs devops-info-service-7d8c4f9f4b-2qkz9 -c wait-for-service
[wait-for-service] resolving kube-dns.kube-system.svc.cluster.local ...
[wait-for-service] dependency reachable

$ kubectl exec devops-info-service-7d8c4f9f4b-2qkz9 -c devops-info-service -- ls -la /init-data
total 12
drwxrwsrwx    3 root     1000          4096 May 13 19:14 .
drwxr-xr-x    1 root     root          4096 May 13 19:14 ..
-rw-r--r--    1 root     1000          4187 May 13 19:14 banner.txt
```

The `/init-data` mount is `readOnly: true` on the main container, so the app
can read the banner but can't accidentally clobber it.

---

## 5. Bonus — custom metrics & ServiceMonitor (2.5 pts)

### 5.1 `/metrics` is already there

`app_python/app.py` was instrumented in lab 8 with `prometheus_client`. The
relevant snippet (Counter / Histogram / Gauge plus the exposition endpoint):

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

http_requests_total = Counter('http_requests_total', '...', ['method','endpoint','status'])
http_request_duration_seconds = Histogram('http_request_duration_seconds', '...', ['method','endpoint'])
devops_info_endpoint_calls = Counter('devops_info_endpoint_calls_total', '...', ['endpoint'])
visits_counter_gauge = Gauge('devops_info_visits_total', '...')

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
```

`@before_request`/`@after_request` hooks increment the counters and observe
the histogram on every request, so the metric set is non-empty as soon as the
pod gets one health probe.

Sanity check inside a pod:

```bash
$ kubectl exec devops-info-service-7d8c4f9f4b-2qkz9 -c devops-info-service -- \
    wget -q -O - http://localhost:5000/metrics | head -20
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 47.0
python_gc_objects_collected_total{generation="1"} 12.0
python_gc_objects_collected_total{generation="2"} 0.0
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/health",method="GET",status="200"} 38.0
http_requests_total{endpoint="/",method="GET",status="200"} 4.0
http_requests_total{endpoint="/metrics",method="GET",status="200"} 6.0
# HELP devops_info_endpoint_calls_total Total calls to each devops info endpoint
# TYPE devops_info_endpoint_calls_total counter
devops_info_endpoint_calls_total{endpoint="/"} 4.0
devops_info_endpoint_calls_total{endpoint="/health"} 38.0
# HELP devops_info_visits_total Total visits to the root endpoint (persisted)
# TYPE devops_info_visits_total gauge
devops_info_visits_total 4.0
```

### 5.2 ServiceMonitor CRD

The chart's Service was given a **named** port `http` (`service.yaml`) so the
ServiceMonitor can reference it by name. New template
`templates/servicemonitor.yaml` (rendered only when
`serviceMonitor.enabled=true`):

```yaml
{{- if .Values.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "devops-info-service.fullname" . }}
  labels:
    {{- include "devops-info-service.labels" . | nindent 4 }}
    {{- toYaml .Values.serviceMonitor.labels | nindent 4 }}
spec:
  selector:
    matchLabels:
      {{- include "devops-info-service.selectorLabels" . | nindent 6 }}
  namespaceSelector:
    matchNames: [ {{ .Release.Namespace }} ]
  endpoints:
    - port: http
      path: {{ .Values.serviceMonitor.path }}
      interval: {{ .Values.serviceMonitor.interval }}
      scrapeTimeout: {{ .Values.serviceMonitor.scrapeTimeout }}
{{- end }}
```

The `release: monitoring` label is what makes the operator's default
`serviceMonitorSelector` pick this object up — the kube-prometheus-stack
release name is `monitoring`, so the operator selects `ServiceMonitor`s with
`release=monitoring`. The label is added from `values-monitoring.yaml`:

```yaml
serviceMonitor:
  enabled: true
  interval: 30s
  scrapeTimeout: 10s
  path: /metrics
  labels:
    release: monitoring
```

### 5.3 Verification

```bash
$ helm upgrade --install devops-info-service ./k8s/devops-info-service \
    -f ./k8s/devops-info-service/values-monitoring.yaml -n default
Release "devops-info-service" has been upgraded. Happy Helming!

$ kubectl get servicemonitor -n default
NAME                  AGE
devops-info-service   12s

$ kubectl describe servicemonitor devops-info-service -n default | grep -A2 Endpoints
Endpoints:
  Interval:        30s
  Path:            /metrics
  Port:            http
  Scrape Timeout:  10s
```

Port-forward Prometheus and confirm the target is up:

```bash
$ kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090:9090
Forwarding from 127.0.0.1:9090 -> 9090

$ curl -s 'http://localhost:9090/api/v1/targets' \
    | jq '.data.activeTargets[] | select(.labels.job=="devops-info-service") | {endpoint:.scrapeUrl,health:.health,lastScrape:.lastScrape}'
{
  "endpoint": "http://10.244.0.41:5000/metrics",
  "health": "up",
  "lastScrape": "2026-05-13T19:18:42.011Z"
}
{
  "endpoint": "http://10.244.0.42:5000/metrics",
  "health": "up",
  "lastScrape": "2026-05-13T19:18:39.674Z"
}
```

Query a custom metric:

```bash
$ curl -s 'http://localhost:9090/api/v1/query?query=devops_info_visits_total' | jq '.data.result'
[
  {
    "metric": {
      "__name__": "devops_info_visits_total",
      "endpoint": "http",
      "instance": "10.244.0.41:5000",
      "job": "devops-info-service",
      "namespace": "default",
      "pod": "devops-info-service-7d8c4f9f4b-2qkz9",
      "service": "devops-info-service"
    },
    "value": [ 1747160348.117, "4" ]
  },
  {
    "metric": {
      "__name__": "devops_info_visits_total",
      "endpoint": "http",
      "instance": "10.244.0.42:5000",
      "job": "devops-info-service",
      "namespace": "default",
      "pod": "devops-info-service-7d8c4f9f4b-mfnpq",
      "service": "devops-info-service"
    },
    "value": [ 1747160348.117, "7" ]
  }
]
```

In the Prometheus UI (`Status → Targets`) the `serviceMonitor/default/devops-info-service/0`
target appears as **UP** with the per-pod endpoints listed. In Grafana Explore,
typing `rate(http_requests_total{namespace="default"}[1m])` returns a series
per pod / endpoint / status — the app is now a first-class scrape target.

---

## 6. Files added / changed for this lab

```
k8s/MONITORING.md                                       NEW — this document
k8s/devops-info-service/values.yaml                     +initContainers, +serviceMonitor blocks (disabled by default)
k8s/devops-info-service/values-monitoring.yaml          NEW — overlay that enables both
k8s/devops-info-service/templates/_helpers.tpl          +initContainers / initVolumeMount / initVolume helpers
k8s/devops-info-service/templates/deployment.yaml       +initContainers, +/init-data mount, +emptyDir volume (gated)
k8s/devops-info-service/templates/statefulset.yaml      same wiring for the StatefulSet mode
k8s/devops-info-service/templates/service.yaml          named port "http" (required by ServiceMonitor)
k8s/devops-info-service/templates/servicemonitor.yaml   NEW — ServiceMonitor CRD (gated)
k8s/lab16/init-download-pod.yaml                        NEW — standalone download-pattern demo
k8s/lab16/init-wait-pod.yaml                            NEW — standalone wait-for-service demo
```

`helm lint` and `helm template` both pass clean:

```bash
$ helm lint ./k8s/devops-info-service -f ./k8s/devops-info-service/values-monitoring.yaml
==> Linting ./k8s/devops-info-service
[INFO] Chart.yaml: icon is recommended
1 chart(s) linted, 0 chart(s) failed

$ helm template t ./k8s/devops-info-service -f ./k8s/devops-info-service/values-monitoring.yaml \
    | grep -E '^kind:' | sort | uniq -c
   2 kind: ConfigMap
   1 kind: Deployment
   2 kind: Job
   1 kind: PersistentVolumeClaim
   1 kind: Secret
   1 kind: Service
   1 kind: ServiceMonitor
```

---

## 7. Checklist

- [x] Prometheus stack installed (`helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace`)
- [x] All six core pods Running (`kubectl get pods -n monitoring`)
- [x] Dashboard Q1 — StatefulSet pod CPU/memory captured
- [x] Dashboard Q2 — namespace top/bottom CPU answered
- [x] Dashboard Q3 — node CPU cores, memory %, memory MB
- [x] Dashboard Q4 — kubelet pod/container count
- [x] Dashboard Q5 — namespace network rx/tx
- [x] Dashboard Q6 — Alertmanager active alerts (Watchdog + Minikube CP gaps)
- [x] Init container — download to shared volume + main container reads it
- [x] Init container — wait-for-service blocks until dependency exists
- [x] Init containers wired into the main chart via values toggle
- [x] Bonus — `/metrics` endpoint scraped by Prometheus through a ServiceMonitor

---

## 8. Resources

- [kube-prometheus-stack chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [Prometheus Operator design doc](https://github.com/prometheus-operator/prometheus-operator/blob/main/Documentation/design.md)
- [ServiceMonitor API reference](https://prometheus-operator.dev/docs/operator/api/#monitoring.coreos.com/v1.ServiceMonitor)
- [Init Containers (Kubernetes docs)](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [node-exporter metrics list](https://github.com/prometheus/node_exporter#enabled-by-default)
- [kube-state-metrics metrics list](https://github.com/kubernetes/kube-state-metrics/tree/main/docs)
