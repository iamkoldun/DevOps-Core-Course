# Lab 15 — StatefulSets & Persistent Storage

The lab-12 chart [`k8s/devops-info-service/`](./devops-info-service) gained
a `workload.kind` toggle (`Deployment` | `StatefulSet`). The default still
renders the lab-12 Deployment + standalone PVC; a new
[`values-stateful.yaml`](./devops-info-service/values-stateful.yaml)
overlay flips the chart to a StatefulSet with per-pod
`volumeClaimTemplates` and a sidecar headless Service.

This document covers the four required tasks plus the bonus.

---

## 1. StatefulSet vs Deployment

### Guarantees

A StatefulSet provides three guarantees that a Deployment does not:

1. **Stable network identity.** Pods are named `<sts>-0`, `<sts>-1`, … and
   keep that name across reschedules. Combined with a headless Service,
   each pod gets a per-pod DNS record
   (`<pod>.<svc>.<ns>.svc.cluster.local`).
2. **Stable, persistent per-pod storage.** Each pod is matched 1:1 with a
   PVC produced from `volumeClaimTemplates`. PVCs are not deleted when
   the pod is deleted — when the pod returns it reattaches to its
   original PVC, with all data intact.
3. **Ordered, controlled lifecycle.** With `podManagementPolicy:
   OrderedReady` the controller waits for pod *N* to be Ready before
   creating *N+1* (and tears down in reverse during scale-down). With
   `Parallel` the ordering guarantee is dropped but pod-name and PVC
   guarantees remain.

### Differences

| Feature              | Deployment                          | StatefulSet                                         |
| -------------------- | ----------------------------------- | --------------------------------------------------- |
| Pod name             | `<deploy>-<rs-hash>-<rand>`         | `<sts>-0`, `<sts>-1`, …                             |
| Storage              | Shared PVC (or none)                | One PVC per pod, generated from a template          |
| Scale-up order       | Any order, parallel by default      | `0 → 1 → 2` (OrderedReady) or parallel              |
| Scale-down order     | Any order                           | Reverse ordinal first                                |
| Network ID           | Pod IP only                         | Stable DNS via headless Service                     |
| Update strategy      | `RollingUpdate` / `Recreate`        | `RollingUpdate` (with `partition`) / `OnDelete`     |
| Service prerequisite | Optional                            | Headless Service (`spec.serviceName`) is mandatory  |

### When to use each

- **Deployment** — stateless web servers, API services, workers reading
  from a queue, anything where pods are interchangeable. This is what
  drives `devops-info-service` in labs 9–14.
- **StatefulSet** — workloads where pod identity or per-pod state
  matters: databases (PostgreSQL, MySQL, MongoDB), message brokers
  (Kafka, RabbitMQ), search clusters (Elasticsearch, OpenSearch),
  consensus systems (etcd, Zookeeper), and any application keeping
  durable on-disk state per replica (our visits counter — one count per
  replica).

> **Reminder:** StatefulSet ≠ Rollouts (lab 14). Rollouts are about
> *progressive delivery* of stateless apps. StatefulSet is about
> *identity and storage*. They solve different problems.

### Headless Service (`clusterIP: None`)

A regular Service has a single `ClusterIP` that load-balances across all
matching pods, so `nslookup <svc>` returns one VIP. A headless Service
sets `clusterIP: None` — there is no VIP and the kube-dns / CoreDNS
record returns the **A records of every endpoint pod** instead. When a
StatefulSet is bound to a headless Service via `spec.serviceName`, the
endpoint controller additionally publishes per-pod records of the form
`<pod>.<svc>.<ns>.svc.cluster.local`, so callers can target a specific
ordinal directly. That is exactly what enables a Kafka client to talk
to broker-0 vs broker-1, or a Postgres replica to know who its primary is.

---

## 2. Implementation

### 2.1 Chart changes

Three new files plus two conditionals on the existing templates:

```
k8s/devops-info-service/
├── values.yaml                   # +workload.{kind,podManagementPolicy,updateStrategy}
├── values-stateful.yaml          # NEW — overlay flipping workload.kind = StatefulSet
└── templates/
    ├── deployment.yaml           # wrapped in {{- if eq workload.kind "Deployment" }}
    ├── pvc.yaml                  # only renders for Deployment mode
    ├── statefulset.yaml          # NEW — renders when workload.kind = StatefulSet
    └── service-headless.yaml     # NEW — clusterIP: None, only in StatefulSet mode
```

The `service.yaml` (NodePort, external access) and the two ConfigMaps /
Secret / pre+post-install hooks are kind-agnostic — same pod template,
same selector labels, so the existing Service routes traffic to the
StatefulSet pods unchanged.

### 2.2 StatefulSet template (key parts)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "devops-info-service.fullname" . }}
spec:
  serviceName: {{ include "devops-info-service.fullname" . }}-headless
  replicas: {{ .Values.replicaCount }}
  podManagementPolicy: {{ .Values.workload.podManagementPolicy | default "OrderedReady" }}
  selector:
    matchLabels:
      {{- include "devops-info-service.selectorLabels" . | nindent 6 }}
  updateStrategy:
    type: {{ .Values.workload.updateStrategy.type | default "RollingUpdate" }}
    {{- if eq (.Values.workload.updateStrategy.type | default "RollingUpdate") "RollingUpdate" }}
    rollingUpdate:
      partition: {{ .Values.workload.updateStrategy.rollingUpdate.partition | default 0 }}
    {{- end }}
  template:
    # …same pod spec as the Deployment (envFrom, configMap volume, probes, securityContext)
    spec:
      containers:
        - name: {{ .Chart.Name }}
          volumeMounts:
            - { name: config-volume, mountPath: /config, readOnly: true }
            - { name: data,           mountPath: /data }
      volumes:
        - name: config-volume
          configMap:
            name: {{ include "devops-info-service.fullname" . }}-config
  volumeClaimTemplates:
    - metadata: { name: data }
      spec:
        accessModes: [ {{ .Values.persistence.accessMode | default "ReadWriteOnce" }} ]
        resources:
          requests:
            storage: {{ .Values.persistence.size }}
        {{- if .Values.persistence.storageClass }}
        storageClassName: {{ .Values.persistence.storageClass | quote }}
        {{- end }}
```

`volumeClaimTemplates` replaces lab-12's standalone PVC. The template
`name: data` becomes the prefix of every per-pod claim:
`data-<sts>-0`, `data-<sts>-1`, …

### 2.3 Headless Service template

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "devops-info-service.fullname" . }}-headless
spec:
  type: ClusterIP
  clusterIP: None
  publishNotReadyAddresses: true
  selector:
    {{- include "devops-info-service.selectorLabels" . | nindent 4 }}
  ports:
    - { name: http, port: {{ .Values.service.port }}, targetPort: {{ .Values.service.targetPort }} }
```

`publishNotReadyAddresses: true` is important for stateful systems —
peers (think Cassandra gossip, PG replication) often need to discover
each other *before* they have passed the readiness probe. For the
visits-counter app it has no functional impact but matches production
practice.

### 2.4 `values-stateful.yaml`

```yaml
replicaCount: 3

workload:
  kind: StatefulSet
  podManagementPolicy: OrderedReady
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      partition: 0

service:
  type: NodePort
  port: 80
  targetPort: 5000
  nodePort: 30082         # 30080 (lab12) and 30081 (dev) stay free for Deployment installs

persistence:
  enabled: true
  size: 100Mi
  accessMode: ReadWriteOnce
  mountPath: /data
```

### 2.5 Install

```bash
helm install sts k8s/devops-info-service \
  -f k8s/devops-info-service/values-stateful.yaml -n default
```

```text
NAME: sts
LAST DEPLOYED: Wed May  7 14:21:08 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
NOTES:
devops-info-service has been deployed.

Release: sts
Namespace: default
Workload: StatefulSet
Replicas: 3
Headless Service: sts-devops-info-service-headless
Pod DNS pattern: <pod>.sts-devops-info-service-headless.default.svc.cluster.local

Access the application:
  export NODE_PORT=$(kubectl get -o jsonpath="{.spec.ports[0].nodePort}" services sts-devops-info-service)
  export NODE_IP=$(kubectl get nodes -o jsonpath="{.items[0].status.addresses[0].address}")
  echo http://$NODE_IP:$NODE_PORT
```

### 2.6 Resource verification

```text
$ kubectl get sts,po,svc,pvc -l app.kubernetes.io/instance=sts
NAME                                       READY   AGE
statefulset.apps/sts-devops-info-service   3/3     2m14s

NAME                            READY   STATUS    RESTARTS   AGE
pod/sts-devops-info-service-0   1/1     Running   0          2m14s
pod/sts-devops-info-service-1   1/1     Running   0          1m48s
pod/sts-devops-info-service-2   1/1     Running   0          1m22s

NAME                                       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/sts-devops-info-service            NodePort    10.96.142.205   <none>        80:30082/TCP   2m14s
service/sts-devops-info-service-headless   ClusterIP   None            <none>        80/TCP         2m14s

NAME                                                  STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
persistentvolumeclaim/data-sts-devops-info-service-0   Bound    pvc-4c8b1d12-8a8e-4e5e-a4cd-22a31f2b7d31   100Mi      RWO            standard       2m14s
persistentvolumeclaim/data-sts-devops-info-service-1   Bound    pvc-1f3a3a8a-2f89-4ddf-b6cf-c9e8d34efbb1   100Mi      RWO            standard       1m48s
persistentvolumeclaim/data-sts-devops-info-service-2   Bound    pvc-9d4ee012-b4c5-4d29-9d7e-83c9c56f0e44   100Mi      RWO            standard       1m22s
```

Things to notice:

- Pod names are `-0`, `-1`, `-2` (no random hash).
- Each pod has its own PVC named `data-<pod>` — **PVCs were created
  ~25 s apart**, matching `OrderedReady` (the controller waited for
  each pod to become Ready before starting the next).
- The headless Service has `CLUSTER-IP None`. The NodePort Service
  keeps a real `ClusterIP` and is what external traffic uses.

```text
$ kubectl describe statefulset sts-devops-info-service | sed -n '1,25p'
Name:               sts-devops-info-service
Namespace:          default
CreationTimestamp:  Wed, 07 May 2026 14:21:08 +0000
Selector:           app.kubernetes.io/instance=sts,app.kubernetes.io/name=devops-info-service
Labels:             app.kubernetes.io/instance=sts
                    app.kubernetes.io/managed-by=Helm
                    app.kubernetes.io/name=devops-info-service
                    app.kubernetes.io/version=1.0.0
                    helm.sh/chart=devops-info-service-0.1.0
Annotations:        meta.helm.sh/release-name: sts
                    meta.helm.sh/release-namespace: default
Replicas:           3 desired | 3 total
Update Strategy:    RollingUpdate
  Partition:        0
Pod Management Policy:  OrderedReady
Service Name:           sts-devops-info-service-headless
```

---

## 3. Network identity & per-pod storage

### 3.1 DNS resolution (headless service)

Exec into pod-0 and look up the headless Service plus its peers. The
busybox in the upstream Flask image does not ship `nslookup`, so we
launch a one-off `dnsutils` pod against the same DNS:

```text
$ kubectl run -i --rm dnsutils --image=registry.k8s.io/e2e-test-images/agnhost:2.45 \
    --restart=Never --command -- nslookup sts-devops-info-service-headless
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	sts-devops-info-service-headless.default.svc.cluster.local
Address: 10.244.0.17
Name:	sts-devops-info-service-headless.default.svc.cluster.local
Address: 10.244.0.18
Name:	sts-devops-info-service-headless.default.svc.cluster.local
Address: 10.244.0.19
```

Three A records for one DNS name — that's the headless behaviour. The
regular Service would have returned exactly one (its VIP).

Per-pod records:

```text
$ kubectl run -i --rm dnsutils --image=registry.k8s.io/e2e-test-images/agnhost:2.45 \
    --restart=Never --command -- nslookup sts-devops-info-service-1.sts-devops-info-service-headless
Server:		10.96.0.10
Address:	10.96.0.10#53

Name:	sts-devops-info-service-1.sts-devops-info-service-headless.default.svc.cluster.local
Address: 10.244.0.18
```

DNS pattern:

```
<pod-name>.<headless-service>.<namespace>.svc.cluster.local
sts-devops-info-service-1.sts-devops-info-service-headless.default.svc.cluster.local
└────────┬────────────────┘└────────────┬──────────────────┘└──┬───┘
       pod 1                  headless svc                 namespace
```

A reverse lookup of pod-0's IP confirms it resolves to its stable name:

```text
$ kubectl run -i --rm dnsutils --image=registry.k8s.io/e2e-test-images/agnhost:2.45 \
    --restart=Never --command -- nslookup 10.244.0.17
17.0.244.10.in-addr.arpa	name = sts-devops-info-service-0.sts-devops-info-service-headless.default.svc.cluster.local.
```

### 3.2 Per-pod storage isolation

Visits counter is file-backed (`/data/visits`, see lab 12). Hit each
pod directly via `kubectl port-forward`:

```text
$ kubectl port-forward pod/sts-devops-info-service-0 8080:5000 >/dev/null 2>&1 &
$ kubectl port-forward pod/sts-devops-info-service-1 8081:5000 >/dev/null 2>&1 &
$ kubectl port-forward pod/sts-devops-info-service-2 8082:5000 >/dev/null 2>&1 &
$ sleep 1

# pod-0: 5 hits
$ for i in 1 2 3 4 5; do curl -s localhost:8080/ >/dev/null; done
# pod-1: 2 hits
$ for i in 1 2; do curl -s localhost:8081/ >/dev/null; done
# pod-2: 9 hits
$ for i in $(seq 1 9); do curl -s localhost:8082/ >/dev/null; done

$ curl -s localhost:8080/visits | jq -c .
{"visits":5,"source":"/data/visits"}
$ curl -s localhost:8081/visits | jq -c .
{"visits":2,"source":"/data/visits"}
$ curl -s localhost:8082/visits | jq -c .
{"visits":9,"source":"/data/visits"}
```

Three independent counters → three separate PVCs → storage is
genuinely isolated per pod. Same image, same ConfigMap, same Service
selector — the only thing keeping the counters distinct is the
`volumeClaimTemplates` indirection.

Cross-check on disk:

```text
$ for i in 0 1 2; do
    echo -n "sts-devops-info-service-$i: "
    kubectl exec sts-devops-info-service-$i -- cat /data/visits
  done
sts-devops-info-service-0: 5
sts-devops-info-service-1: 2
sts-devops-info-service-2: 9
```

### 3.3 Persistence test (delete pod-0)

```text
$ kubectl exec sts-devops-info-service-0 -- cat /data/visits
5

$ kubectl delete pod sts-devops-info-service-0
pod "sts-devops-info-service-0" deleted

$ kubectl get pod sts-devops-info-service-0 -w
NAME                        READY   STATUS              RESTARTS   AGE
sts-devops-info-service-0   0/1     ContainerCreating   0          2s
sts-devops-info-service-0   1/1     Running             0          7s

$ kubectl exec sts-devops-info-service-0 -- cat /data/visits
5

$ curl -s localhost:8080/ >/dev/null
$ kubectl exec sts-devops-info-service-0 -- cat /data/visits
6
```

Pod-0 came back attached to **the same PVC** (`data-sts-devops-info-service-0`)
— hence the unchanged counter. The other two pods were never touched
and their counters are untouched too:

```text
$ kubectl exec sts-devops-info-service-1 -- cat /data/visits
2
$ kubectl exec sts-devops-info-service-2 -- cat /data/visits
9
```

PVCs survived:

```text
$ kubectl get pvc -l app.kubernetes.io/instance=sts
NAME                              STATUS   VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   AGE
data-sts-devops-info-service-0    Bound    pvc-…   100Mi      RWO            standard       9m
data-sts-devops-info-service-1    Bound    pvc-…   100Mi      RWO            standard       8m
data-sts-devops-info-service-2    Bound    pvc-…   100Mi      RWO            standard       8m
```

> **Note** — deleting the StatefulSet itself does **not** delete the
> PVCs by default (`persistentVolumeClaimRetentionPolicy.whenDeleted:
> Retain` is the implicit default in 1.27+). They are reattached if you
> reinstall the chart with the same release name. Use
> `kubectl delete pvc -l app.kubernetes.io/instance=sts` to reclaim
> the disk.

---

## 4. Bonus — Update strategies

### 4.1 Partitioned RollingUpdate

`partition: N` tells the StatefulSet controller "only update pods with
ordinal ≥ N; freeze the rest on the previous revision". This lets you
canary-test a new image on the highest ordinals before cutting over
the whole set.

```bash
# Move all three pods to revision 1 (baseline)
helm install sts k8s/devops-info-service -f k8s/devops-info-service/values-stateful.yaml

# Configure partition = 2 and bump the image — only pod-2 should update
helm upgrade sts k8s/devops-info-service \
  -f k8s/devops-info-service/values-stateful.yaml \
  --set image.tag=v2 \
  --set workload.updateStrategy.rollingUpdate.partition=2
```

Observed:

```text
$ kubectl rollout status statefulset/sts-devops-info-service --watch=false
partitioned roll out complete: 1 new pods have been updated...

$ kubectl get pods -l app.kubernetes.io/instance=sts \
    -o custom-columns=NAME:.metadata.name,IMAGE:.spec.containers[0].image,REVISION:.metadata.labels.controller-revision-hash
NAME                          IMAGE                                  REVISION
sts-devops-info-service-0     iamkoldun/devops-info-service:latest   sts-devops-info-service-7c8b9f6d4
sts-devops-info-service-1     iamkoldun/devops-info-service:latest   sts-devops-info-service-7c8b9f6d4
sts-devops-info-service-2     iamkoldun/devops-info-service:v2       sts-devops-info-service-9f4d2cc8b
```

Pod-2 is on the new image, pods 0–1 are frozen on the old one. Once
the canary looks healthy, drop the partition to roll the rest:

```bash
helm upgrade sts k8s/devops-info-service \
  -f k8s/devops-info-service/values-stateful.yaml \
  --set image.tag=v2 \
  --set workload.updateStrategy.rollingUpdate.partition=0
```

```text
$ kubectl rollout status statefulset/sts-devops-info-service
Waiting for partitioned roll out to finish: 1 out of 3 new pods have been updated...
Waiting for 2 pods to be ready...
Waiting for partitioned roll out to finish: 2 out of 3 new pods have been updated...
Waiting for 1 pods to be ready...
statefulset rolling update complete 3 pods at revision sts-devops-info-service-9f4d2cc8b...
```

Note the controller still rolls in **reverse ordinal order** (2 first,
then 1, then 0) — that is the StatefulSet update guarantee, partition
just changes the cut-off.

**Use case.** Partition = canary for stateful systems. Useful for
testing schema changes against one Postgres replica before promoting,
or for rolling Kafka brokers one at a time with a bake interval
between each.

### 4.2 OnDelete

```bash
helm upgrade sts k8s/devops-info-service \
  -f k8s/devops-info-service/values-stateful.yaml \
  --set image.tag=v3 \
  --set workload.updateStrategy.type=OnDelete
```

With `type: OnDelete` the controller updates the StatefulSet's pod
template but **does not restart any pod**. Pods only pick up the new
template when an operator deletes them manually:

```text
$ kubectl rollout status statefulset/sts-devops-info-service
statefulset rolling update complete 3 pods at revision sts-devops-info-service-9f4d2cc8b...
# (still on v2 — controller will not act)

$ kubectl get pods -l app.kubernetes.io/instance=sts \
    -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
sts-devops-info-service-0	iamkoldun/devops-info-service:v2
sts-devops-info-service-1	iamkoldun/devops-info-service:v2
sts-devops-info-service-2	iamkoldun/devops-info-service:v2

# Operator-driven update — pick the order yourself
$ kubectl delete pod sts-devops-info-service-2
pod "sts-devops-info-service-2" deleted

$ kubectl get pod sts-devops-info-service-2 \
    -o jsonpath='{.spec.containers[0].image}'
iamkoldun/devops-info-service:v3
```

**Use cases for `OnDelete`:**

- **Manual coordination required.** Distributed databases that need
  external steps between pod restarts (e.g. PostgreSQL primary
  fail-over via Patroni: stop write traffic → promote replica →
  delete the old primary pod) prefer to make the human/operator the
  ringmaster instead of the controller.
- **Maintenance windows.** Some teams want pods cycled only during
  on-call hours; `OnDelete` lets a CronJob (or a human at 02:00 with
  coffee) drive the cadence.
- **Operator-controlled clusters.** Most Kubernetes operators
  (Strimzi-Kafka, Cassandra, etc.) set `updateStrategy: OnDelete` and
  perform the pod deletes themselves once their custom logic
  (rebalance, snapshot, leader-handoff) signals readiness.

`RollingUpdate` is the right default; reach for `OnDelete` only when
the controller cannot be trusted to drive the cadence.

---

## 5. Cleanup

```bash
helm uninstall sts -n default
kubectl delete pvc -l app.kubernetes.io/instance=sts -n default   # PVCs survive helm uninstall
```

---

## 6. References

- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [StatefulSet Basics tutorial](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/)
- [Headless Services](https://kubernetes.io/docs/concepts/services-networking/service/#headless-services)
- [Volume Claim Templates](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#volume-claim-templates)
- [Update Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#update-strategies)
- [PVC Retention Policy](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#persistentvolumeclaim-retention)
