# Lab 12 — ConfigMaps & PVC

## App changes

Added a file-backed visits counter and two new endpoints.

- `GET /` increments the counter (read → `+1` → atomic write via `tmp` + `os.replace`).
- `GET /visits` — returns current value without incrementing.
- `GET /config` — dumps `${CONFIG_PATH}` + relevant env vars.
- Counter lives in `${DATA_DIR}/visits` (default `/data/visits`).
- `threading.Lock` around the read/write pair; `OSError` on write is logged, not fatal.

### Local test (docker-compose)

```yaml
volumes:
  - ./data:/data
  - ./config:/config:ro
```

```text
$ docker compose up -d --build
[+] Running 1/1
 ✔ Container devops-info-service  Started

$ for i in 1 2 3 4 5; do curl -s localhost:5000/ | jq -r .visits; done
1
2
3
4
5
$ cat data/visits
5
$ docker compose restart
$ curl -s localhost:5000/visits | jq -r .visits
5
$ curl -s localhost:5000/ | jq -r .visits
6
```

Counter survives restart — the volume is on the host.

## ConfigMaps

Two maps in `templates/configmap.yaml`:

| Name | Shape | Consumed as |
|------|-------|-------------|
| `…-config` | single key `config.json` | volume at `/config/config.json` |
| `…-env` | key/value pairs | `envFrom.configMapRef` |

File-based map uses `.Files.Get`:

```yaml
data:
  config.json: |-
{{ .Files.Get "files/config.json" | indent 4 }}
```

Env map:

```yaml
data:
  APP_ENV: {{ .Values.config.appEnv | quote }}
  LOG_LEVEL: {{ .Values.config.logLevel | quote }}
  FEATURE_FLAG_BETA: {{ .Values.config.featureFlagBeta | quote }}
  DATA_DIR: {{ .Values.persistence.mountPath | quote }}
  CONFIG_PATH: {{ printf "%s/config.json" .Values.configMount.mountPath | quote }}
```

Deployment wiring:

```yaml
envFrom:
  - secretRef:      { name: devops-info-service-secret }
  - configMapRef:   { name: devops-info-service-env }
volumeMounts:
  - name: config-volume
    mountPath: /config
    readOnly: true
```

### Verify

```text
$ kubectl get configmap,pvc
NAME                                             DATA   AGE
configmap/devops-devops-info-service-config      1      31s
configmap/devops-devops-info-service-env         5      31s
configmap/kube-root-ca.crt                       1      14d

NAME                                                    STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
persistentvolumeclaim/devops-devops-info-service-data   Bound    pvc-6e1f7c74-9f24-4d88-b3b6-78f4e83df9a1   100Mi      RWO            standard       31s

$ POD=$(kubectl get pod -l app.kubernetes.io/name=devops-info-service -o jsonpath='{.items[0].metadata.name}')
$ kubectl exec $POD -- cat /config/config.json
{
  "app_name": "devops-info-service",
  "environment": "production",
  "features": { "greeting": true, "experimental_metrics": false },
  "limits": { "max_payload_bytes": 65536 }
}

$ kubectl exec $POD -- printenv | grep -E 'APP_ENV|LOG_LEVEL|FEATURE_|DATA_DIR|CONFIG_PATH' | sort
APP_ENV=production
CONFIG_PATH=/config/config.json
DATA_DIR=/data
FEATURE_FLAG_BETA=false
LOG_LEVEL=INFO
```

## PVC

`templates/pvc.yaml`:

```yaml
{{- if .Values.persistence.enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "devops-info-service.fullname" . }}-data
spec:
  accessModes: [ {{ .Values.persistence.accessMode | default "ReadWriteOnce" }} ]
  resources:
    requests:
      storage: {{ .Values.persistence.size }}
  {{- if .Values.persistence.storageClass }}
  storageClassName: {{ .Values.persistence.storageClass | quote }}
  {{- end }}
{{- end }}
```

Defaults: `100Mi`, `ReadWriteOnce`, empty `storageClass` (→ cluster default, `standard` on minikube).

Notes:

- RWO + minikube `hostpath` → single node, single replica. Strategy is `Recreate` so the old pod releases the PVC before the new one attaches. Rolling update would deadlock.
- `securityContext.fsGroup: 1000` — without it the non-root container can't write to the freshly provisioned volume.
- RWX (NFS/CSI) or externalizing the counter to Redis would be the next step if we ever need to scale past one replica.

### Persistence test

```text
$ for i in $(seq 1 7); do curl -s http://$(minikube ip):30080/ > /dev/null; done
$ kubectl exec $POD -- cat /data/visits
7

$ kubectl delete pod $POD
pod "devops-devops-info-service-7cdb4f9f8b-nq9zm" deleted

$ kubectl rollout status deploy/devops-devops-info-service
deployment "devops-devops-info-service" successfully rolled out

$ NEWPOD=$(kubectl get pod -l app.kubernetes.io/name=devops-info-service -o jsonpath='{.items[0].metadata.name}')
$ kubectl exec $NEWPOD -- cat /data/visits
7
$ curl -s http://$(minikube ip):30080/ > /dev/null
$ kubectl exec $NEWPOD -- cat /data/visits
8
```

Data survived pod deletion. Done.

## ConfigMap vs Secret

| | ConfigMap | Secret |
|---|-----------|--------|
| For | config, flags, non-sensitive files | passwords, tokens, TLS material |
| Storage | plaintext in etcd | base64; optional encryption-at-rest |
| RBAC | usually broad | keep tight |
| Size | 1 MiB | 1 MiB |
| Updates | live (except `subPath`) | same |

Rule of thumb: if leaking it would be an incident — use a Secret. Otherwise ConfigMap.

## Bonus — hot reload

### kubelet propagation delay

The volume is not real-time. kubelet refreshes on a sync period + its local cache TTL (defaults ≈ 60 s each).

```text
$ kubectl edit configmap devops-devops-info-service-config     # environment: production → staging
configmap/devops-devops-info-service-config edited
$ START=$(date +%s)
$ until kubectl exec $POD -- grep -q staging /config/config.json; do sleep 5; done
$ echo "delay: $(( $(date +%s) - START )) s"
delay: 74 s
```

So ~1–2 minutes in minikube. Fine for config, not OK for anything requiring atomic flip.

### Why `subPath` breaks updates

`subPath` resolves once at mount time and copies the file into the container FS — it's no longer part of the projected-volume symlink tree, so later edits to the ConfigMap don't propagate. Full-directory mount (what we do at `/config`) keeps the symlinks and updates live.

Use `subPath` when you need to drop one file into an already-populated directory (`/etc/nginx/conf.d/app.conf`). Avoid it anywhere you want live reloads.

### Chosen approach — checksum annotation

```yaml
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

Any change to the rendered ConfigMap flips the hash → pod template changes → Helm rolls the deployment. No sidecars, no extra controllers, only reacts to `helm upgrade` (no surprise rollouts).

```text
$ kubectl get deploy devops-devops-info-service -o jsonpath='{.spec.template.metadata.annotations.checksum/config}'
a3c12ef7b49f...

# flip greeting: true → false in files/config.json
$ helm upgrade devops k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml
Release "devops" has been upgraded. REVISION: 3

$ kubectl get deploy devops-devops-info-service -o jsonpath='{.spec.template.metadata.annotations.checksum/config}'
b91f4ad0e221...

$ kubectl rollout status deploy/devops-devops-info-service
deployment "devops-devops-info-service" successfully rolled out

$ kubectl exec $(kubectl get pod -l app.kubernetes.io/name=devops-info-service -o jsonpath='{.items[0].metadata.name}') -- grep greeting /config/config.json
  "greeting": false,
```

Stakater Reloader is the other option — we skipped it to avoid an extra controller for a one-replica service.
