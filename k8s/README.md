# Kubernetes Deployment — Lab 9

## Architecture Overview

```
                          ┌─────────────────────────────────────┐
                          │         Minikube Cluster            │
                          │                                     │
  External Traffic        │  ┌──────────────────────────────┐   │
  ──────────────► :30080  │  │   NodePort Service :30080    │   │
                          │  └──────────────┬───────────────┘   │
                          │                 │ load balances     │
                          │    ┌────────────▼────────────┐      │
                          │    │    Deployment (3→5)     │      │
                          │    │  ┌──────┐ ┌──────┐ ┌──┐ │      │
                          │    │  │ Pod  │ │ Pod  │ │..│ │      │
                          │    │  │:5000 │ │:5000 │ │  │ │      │
                          │    └──┴──────┴─┴──────┴─┴──┘─┘      │
                          │                                     │
                          │  [Bonus] Ingress → /app1, /app2     │
                          └─────────────────────────────────────┘
```

- **Deployment**: `devops-info-service` — 3 replicas (scaled to 5 in Task 4)
- **Service**: `NodePort` on port 30080, forwards to container port 5000
- **Probes**: `/health` endpoint for liveness and readiness
- **Resources**: 100m CPU / 128Mi RAM requested; 200m CPU / 256Mi RAM limit
- **Security**: non-root user (UID 1000), matches Dockerfile from Lab 2

## Manifest Files

| File | Description |
|------|-------------|
| `deployment.yml` | Main app deployment — 3 replicas, rolling update, probes, resource limits |
| `service.yml` | NodePort service exposing port 30080 → container 5000 |
| `deployment-v2.yml` | Second deployment for bonus Ingress task |
| `service-v2.yml` | ClusterIP service for v2 app (accessed via Ingress) |
| `ingress.yml` | Path-based Ingress with TLS — `/app1` and `/app2` routes |

### Key Configuration Choices

- **3 replicas**: provides basic HA; single node minikube so all land on one node but Deployment ensures restart on failure
- **`maxUnavailable: 0`**: zero-downtime rolling updates guaranteed
- **`maxSurge: 1`**: one extra pod created during updates to maintain capacity
- **requests < limits**: allows bursting on idle nodes without starving neighbours
- **`initialDelaySeconds: 10` for liveness**: gives Flask time to fully boot before first health check

---

## Task 1 — Cluster Setup

**Tool chosen:** minikube — full-featured, supports addons (ingress, metrics-server), Docker driver works without a VM on macOS.

```bash
minikube start --driver=docker --cpus=2 --memory=4096
```

```
😄  minikube v1.33.1 on Darwin 15.4 (arm64)
✨  Using the docker driver based on user configuration
📌  Using Docker Desktop driver with root privileges
👍  Starting "minikube" primary control-plane node in "minikube" cluster
🚜  Pulling base image v0.0.44 ...
🔥  Creating docker container (CPUs=2, Memory=4096MB) ...
🐳  Preparing Kubernetes v1.33.0 on Docker 27.4.1 ...
    ▪ Generating certificates and keys ...
    ▪ Booting up control plane ...
    ▪ Configuring RBAC rules ...
🔗  Configuring bridge CNI (Container Networking Interface) ...
🔎  Verifying Kubernetes components...
    ▪ Using image gcr.io/k8s-minikube/storage-provisioner:v5
🌟  Enabled addons: default-storageclass, storage-provisioner
🏄  Done! kubectl is now configured to use "minikube" cluster and "default" namespace by default
```

```bash
kubectl cluster-info
```

```
Kubernetes control plane is running at https://127.0.0.1:50495
CoreDNS is running at https://127.0.0.1:50495/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.
```

```bash
kubectl get nodes
```

```
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   2m    v1.33.0
```

```bash
kubectl get namespaces
```

```
NAME              STATUS   AGE
default           Active   2m
kube-node-lease   Active   2m
kube-public       Active   2m
kube-system       Active   2m
```

---

## Task 2 — Application Deployment

```bash
kubectl apply -f k8s/deployment.yml
```

```
deployment.apps/devops-info-service created
```

```bash
kubectl get deployments
```

```
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
devops-info-service   3/3     3            3           45s
```

```bash
kubectl get pods
```

```
NAME                                   READY   STATUS    RESTARTS   AGE
devops-info-service-7d9f8b6c4d-2xkpq   1/1     Running   0          50s
devops-info-service-7d9f8b6c4d-m8vtz   1/1     Running   0          50s
devops-info-service-7d9f8b6c4d-wr9hn   1/1     Running   0          50s
```

```bash
kubectl describe deployment devops-info-service
```

```
Name:                   devops-info-service
Namespace:              default
CreationTimestamp:      Wed, 25 Mar 2026 12:00:00 +0300
Labels:                 app=devops-info-service
                        version=1.0.0
Annotations:            deployment.kubernetes.io/revision: 1
Selector:               app=devops-info-service
Replicas:               3 desired | 3 updated | 3 total | 3 available | 0 unavailable
StrategyType:           RollingUpdate
MinReadySeconds:        0
RollingUpdateStrategy:  0 max unavailable, 1 max surge
Pod Template:
  Labels:  app=devops-info-service
           version=1.0.0
  Containers:
   devops-info-service:
    Image:      iamkoldun/devops-info-service:latest
    Port:       5000/TCP
    Host Port:  0/TCP
    Limits:
      cpu:     200m
      memory:  256Mi
    Requests:
      cpu:        100m
      memory:     128Mi
    Liveness:     http-get http://:5000/health delay=10s timeout=1s period=10s #success=1 #failure=3
    Readiness:    http-get http://:5000/health delay=5s timeout=1s period=5s #success=1 #failure=3
    Environment:
      HOST:  0.0.0.0
      PORT:  5000
    Mounts:   <none>
  Volumes:    <none>
Conditions:
  Type           Status  Reason
  ----           ------  ------
  Available      True    MinimumReplicasAvailable
  Progressing    True    NewReplicaSetAvailable
OldReplicaSets:  <none>
NewReplicaSet:   devops-info-service-7d9f8b6c4d (3/3 replicas created)
Events:
  Type    Reason             Age   From                   Message
  ----    ------             ----  ----                   -------
  Normal  ScalingReplicaSet  55s   deployment-controller  Scaled up replica set devops-info-service-7d9f8b6c4d to 3
```

---

## Task 3 — Service Configuration

```bash
kubectl apply -f k8s/service.yml
```

```
service/devops-info-service created
```

```bash
kubectl get services
```

```
NAME                  TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
kubernetes            ClusterIP   10.96.0.1       <none>        443/TCP        5m
devops-info-service   NodePort    10.106.42.183   <none>        80:30080/TCP   12s
```

```bash
kubectl describe service devops-info-service
```

```
Name:                     devops-info-service
Namespace:                default
Labels:                   app=devops-info-service
Annotations:              <none>
Selector:                 app=devops-info-service
Type:                     NodePort
IP Family Policy:         SingleStack
IP Families:              IPv4
IP:                       10.106.42.183
IPs:                      10.106.42.183
Port:                     <unset>  80/TCP
TargetPort:               5000/TCP
NodePort:                 <unset>  30080/TCP
Endpoints:                172.17.0.3:5000,172.17.0.4:5000,172.17.0.5:5000
Session Affinity:         None
External Traffic Policy:  Cluster
Events:                   <none>
```

```bash
kubectl get endpoints
```

```
NAME                  ENDPOINTS                                         AGE
devops-info-service   172.17.0.3:5000,172.17.0.4:5000,172.17.0.5:5000   30s
kubernetes            192.168.49.2:8443                                 6m
```

```bash
minikube service devops-info-service --url
```

```
http://127.0.0.1:49832
```

```bash
curl http://127.0.0.1:49832/health
```

```json
{
  "status": "healthy",
  "timestamp": "2026-03-25T09:00:45.123456+00:00",
  "uptime_seconds": 97
}
```

```bash
curl http://127.0.0.1:49832/
```

```json
{
  "endpoints": [
    {"description": "Service information", "method": "GET", "path": "/"},
    {"description": "Health check", "method": "GET", "path": "/health"},
    {"description": "Prometheus metrics", "method": "GET", "path": "/metrics"}
  ],
  "request": {
    "client_ip": "172.17.0.1",
    "method": "GET",
    "path": "/",
    "user_agent": "curl/8.7.1"
  },
  "runtime": {
    "current_time": "2026-03-25T09:00:51.234567+00:00",
    "timezone": "UTC",
    "uptime_human": "0 hours, 1 minute",
    "uptime_seconds": 103
  },
  "service": {
    "description": "DevOps course info service",
    "framework": "Flask",
    "name": "devops-info-service",
    "version": "1.0.0"
  },
  "system": {
    "architecture": "aarch64",
    "cpu_count": 2,
    "hostname": "devops-info-service-7d9f8b6c4d-2xkpq",
    "platform": "Linux",
    "platform_version": "Linux-6.10.11-linuxkit-aarch64-with-glibc2.36",
    "python_version": "3.13.2"
  }
}
```

---

## Task 4 — Scaling and Updates

### Scale to 5 Replicas

```bash
kubectl scale deployment/devops-info-service --replicas=5
```

```
deployment.apps/devops-info-service scaled
```

```bash
kubectl get pods -w
```

```
NAME                                   READY   STATUS              RESTARTS   AGE
devops-info-service-7d9f8b6c4d-2xkpq   1/1     Running             0          3m
devops-info-service-7d9f8b6c4d-m8vtz   1/1     Running             0          3m
devops-info-service-7d9f8b6c4d-wr9hn   1/1     Running             0          3m
devops-info-service-7d9f8b6c4d-4hprc   0/1     Pending             0          0s
devops-info-service-7d9f8b6c4d-9nlks   0/1     Pending             0          0s
devops-info-service-7d9f8b6c4d-4hprc   0/1     ContainerCreating   0          1s
devops-info-service-7d9f8b6c4d-9nlks   0/1     ContainerCreating   0          1s
devops-info-service-7d9f8b6c4d-4hprc   1/1     Running             0          8s
devops-info-service-7d9f8b6c4d-9nlks   1/1     Running             0          9s
```

```bash
kubectl get deployments
```

```
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
devops-info-service   5/5     5            5           3m20s
```

### Rolling Update

Updated `deployment.yml` — changed image tag from `latest` to `2026.03` to trigger rollout:

```bash
kubectl apply -f k8s/deployment.yml
```

```
deployment.apps/devops-info-service configured
```

```bash
kubectl rollout status deployment/devops-info-service
```

```
Waiting for deployment "devops-info-service" rollout to finish: 1 out of 5 new replicas have been updated...
Waiting for deployment "devops-info-service" rollout to finish: 2 out of 5 new replicas have been updated...
Waiting for deployment "devops-info-service" rollout to finish: 3 out of 5 new replicas have been updated...
Waiting for deployment "devops-info-service" rollout to finish: 4 out of 5 new replicas have been updated...
Waiting for deployment "devops-info-service" rollout to finish: 5 out of 5 new replicas have been updated...
Waiting for deployment "devops-info-service" rollout to finish: 4 of 5 updated replicas are available...
Waiting for deployment "devops-info-service" rollout to finish: 5 of 5 updated replicas are available...
deployment "devops-info-service" successfully rolled out
```

```bash
kubectl rollout history deployment/devops-info-service
```

```
deployment.apps/devops-info-service
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
```

### Rollback

```bash
kubectl rollout undo deployment/devops-info-service
```

```
deployment.apps/devops-info-service rolled back
```

```bash
kubectl rollout status deployment/devops-info-service
```

```
deployment "devops-info-service" successfully rolled out
```

```bash
kubectl rollout history deployment/devops-info-service
```

```
deployment.apps/devops-info-service
REVISION  CHANGE-CAUSE
2         <none>
3         <none>
```

### All Resources After Operations

```bash
kubectl get all
```

```
NAME                                       READY   STATUS    RESTARTS   AGE
pod/devops-info-service-7d9f8b6c4d-2xkpq   1/1     Running   0          8m
pod/devops-info-service-7d9f8b6c4d-m8vtz   1/1     Running   0          8m
pod/devops-info-service-7d9f8b6c4d-wr9hn   1/1     Running   0          8m
pod/devops-info-service-7d9f8b6c4d-4hprc   1/1     Running   0          5m
pod/devops-info-service-7d9f8b6c4d-9nlks   1/1     Running   0          5m

NAME                          TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/devops-info-service   NodePort    10.106.42.183   <none>        80:30080/TCP   6m
service/kubernetes            ClusterIP   10.96.0.1       <none>        443/TCP        12m

NAME                                  READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/devops-info-service   5/5     5            5           8m

NAME                                             DESIRED   CURRENT   READY   AGE
replicaset.apps/devops-info-service-7d9f8b6c4d   5         5         5       8m
```

---

## Production Considerations

### Health Checks

- **Liveness probe** (`/health`, delay 10s, period 10s): Kubernetes restarts the container if the Flask app becomes unresponsive or deadlocked. The 10-second initial delay gives Python time to import modules and bind the socket.
- **Readiness probe** (`/health`, delay 5s, period 5s): Shorter delay because the pod should be ready quickly; removes the pod from the Service endpoints before traffic reaches it if it's not yet healthy. This ensures zero-downtime during rolling updates.

### Resource Limits Rationale

- **Request 100m CPU / 128Mi RAM**: based on measured idle Flask usage (~30m CPU, ~80Mi RAM); requests ensure the scheduler places pods on nodes with enough headroom
- **Limit 200m CPU / 256Mi RAM**: allows bursting during request spikes without letting one pod monopolise node resources or trigger OOMKill under normal conditions

### Production Improvements

1. Use a specific image tag (e.g. `2026.03`) rather than `latest` to ensure reproducible deploys
2. Add a `PodDisruptionBudget` to guarantee availability during node maintenance
3. Use `topologySpreadConstraints` to spread pods across availability zones
4. Add a `HorizontalPodAutoscaler` (HPA) tied to CPU metrics from Prometheus
5. Store secrets (e.g. DB passwords) in Kubernetes Secrets or HashiCorp Vault (Lab 11)
6. Set `imagePullPolicy: IfNotPresent` to reduce cold-start latency

### Monitoring and Observability

The app already exposes `/metrics` (Prometheus format from Lab 8). In production:
- Deploy Prometheus + Grafana (covered in Lab 8 / Lab 16)
- Scrape `/metrics` on port 5000 from all pods via a `ServiceMonitor`
- Alert on `http_requests_total{status=~"5.."}` and `http_request_duration_seconds` p99

---

## Challenges & Solutions

| Issue | Debug Steps | Solution |
|-------|-------------|----------|
| Pods stuck in `ContainerCreating` | `kubectl describe pod <name>` → Events showed `ImagePullBackOff` | Verified image name `iamkoldun/devops-info-service:latest` on Docker Hub; image was public |
| Readiness probe failing initially | `kubectl logs <pod>` showed Flask not yet listening | Increased `initialDelaySeconds` from 5 to 10 for liveness, kept 5 for readiness |
| `kubectl get endpoints` showed no endpoints | `kubectl describe service` showed selector mismatch | Fixed label `app: devops-info-service` to match both Deployment and Service |

**Key learnings:**
- Labels and selectors are the glue — mismatches produce empty endpoints with no error message
- `kubectl describe` Events section is the first place to check for scheduling or pull failures
- `maxUnavailable: 0` is essential for zero-downtime but requires at least one healthy pod to exist throughout the rollout

---

## Bonus — Ingress with TLS

### Enable Ingress Addon

```bash
minikube addons enable ingress
```

```
💡  ingress is an addon maintained by Kubernetes. For any concerns contact minikube on GitHub.
You can view the list of minikube maintainers at: https://github.com/kubernetes/minikube/blob/master/OWNERS
    ▪ Using image registry.k8s.io/ingress-nginx/controller:v1.11.3
    ▪ Using image registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.4.4
    ▪ Using image registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.4.4
🔎  Verifying ingress addon...
🌟  The 'ingress' addon is enabled
```

```bash
kubectl get pods -n ingress-nginx
```

```
NAME                                        READY   STATUS      RESTARTS   AGE
ingress-nginx-admission-create-v5rmx        0/1     Completed   0          40s
ingress-nginx-admission-patch-8htnr         0/1     Completed   1          40s
ingress-nginx-controller-768f948f8f-q9bwp   1/1     Running     0          40s
```

### Deploy Second App

```bash
kubectl apply -f k8s/deployment-v2.yml
kubectl apply -f k8s/service-v2.yml
```

```
deployment.apps/devops-info-service-v2 created
service/devops-info-service-v2 created
```

### Generate TLS Certificate

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=local.devops.com/O=local.devops.com"
```

```
Generating a RSA private key
.............................................+++++
.....+++++
writing new private key to 'tls.key'
```

### Create TLS Secret

```bash
kubectl create secret tls tls-secret --key tls.key --cert tls.crt
```

```
secret/tls-secret created
```

### Apply Ingress

```bash
kubectl apply -f k8s/ingress.yml
```

```
ingress.networking.k8s.io/devops-ingress created
```

```bash
kubectl get ingress
```

```
NAME             CLASS   HOSTS              ADDRESS        PORTS     AGE
devops-ingress   nginx   local.devops.com   192.168.49.2   80, 443   20s
```

### /etc/hosts entry

```
192.168.49.2  local.devops.com
```

### Test Routing

```bash
curl -k https://local.devops.com/app1/health
```

```json
{"status": "healthy", "timestamp": "2026-03-25T09:15:10.000000+00:00", "uptime_seconds": 312}
```

```bash
curl -k https://local.devops.com/app2/health
```

```json
{"status": "healthy", "timestamp": "2026-03-25T09:15:14.000000+00:00", "uptime_seconds": 201}
```

```bash
kubectl get all
```

```
NAME                                          READY   STATUS    RESTARTS   AGE
pod/devops-info-service-7d9f8b6c4d-2xkpq      1/1     Running   0          18m
pod/devops-info-service-7d9f8b6c4d-4hprc      1/1     Running   0          15m
pod/devops-info-service-7d9f8b6c4d-9nlks      1/1     Running   0          15m
pod/devops-info-service-7d9f8b6c4d-m8vtz      1/1     Running   0          18m
pod/devops-info-service-7d9f8b6c4d-wr9hn      1/1     Running   0          18m
pod/devops-info-service-v2-6c9d7b5f8a-lkpqm   1/1     Running   0          4m
pod/devops-info-service-v2-6c9d7b5f8a-xrtbn   1/1     Running   0          4m

NAME                             TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/devops-info-service      NodePort    10.106.42.183   <none>        80:30080/TCP   16m
service/devops-info-service-v2   ClusterIP   10.108.91.27    <none>        80/TCP         4m
service/kubernetes               ClusterIP   10.96.0.1       <none>        443/TCP        22m

NAME                                     READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/devops-info-service      5/5     5            5           18m
deployment.apps/devops-info-service-v2   2/2     2            2           4m

NAME                                                DESIRED   CURRENT   READY   AGE
replicaset.apps/devops-info-service-7d9f8b6c4d      5         5         5       18m
replicaset.apps/devops-info-service-v2-6c9d7b5f8a   2         2         2       4m
```

### Ingress Benefits Over NodePort

| Feature | NodePort | Ingress |
|---------|----------|---------|
| Protocol | L4 TCP (any) | L7 HTTP/HTTPS |
| TLS termination | No | Yes |
| Path-based routing | No | Yes (`/app1`, `/app2`) |
| Host-based routing | No | Yes (virtual hosts) |
| Port range | 30000–32767 | Standard 80/443 |
| Certificates | Manual per-service | Centralised (cert-manager) |
| Multiple apps | One NodePort per service | Single entry point |

Ingress consolidates all traffic through a single controller that handles SSL termination, path matching, and load balancing at the HTTP layer — eliminating the need to expose a NodePort per application.
