# Secrets Management — Lab 11

## Task 1 — Kubernetes Secrets Fundamentals

### Creating a Secret

```bash
kubectl create secret generic app-credentials \
  --from-literal=username=admin \
  --from-literal=password=S3cur3P@ssw0rd
```

```
secret/app-credentials created
```

### Viewing the Secret

```bash
kubectl get secret app-credentials -o yaml
```

```yaml
apiVersion: v1
data:
  password: UzNjdXIzUEBzc3cwcmQ=
  username: YWRtaW4=
kind: Secret
metadata:
  creationTimestamp: "2026-04-09T10:15:32Z"
  name: app-credentials
  namespace: default
  resourceVersion: "4521"
  uid: 3a7f2e1b-8c4d-4f6a-b1e3-9d5c7a8f2b4e
type: Opaque
```

### Decoding Base64 Values

```bash
echo "YWRtaW4=" | base64 -d
```

```
admin
```

```bash
echo "UzNjdXIzUEBzc3cwcmQ=" | base64 -d
```

```
S3cur3P@ssw0rd
```

### Base64 Encoding vs Encryption

**Base64 encoding** is a reversible transformation that converts binary data into ASCII text. It provides zero security — anyone with access to the encoded string can decode it instantly using `base64 -d`. Kubernetes Secrets use base64 only for safe transport of arbitrary byte sequences inside YAML.

**Encryption** uses a cryptographic key to transform data so that only holders of the correct key can recover the plaintext. Without the key, the ciphertext is computationally infeasible to reverse.

By default, Kubernetes Secrets are stored **unencrypted** in etcd. This means anyone with etcd access or Kubernetes API access (with appropriate RBAC permissions) can read all secrets in plaintext.

### etcd Encryption at Rest

Kubernetes supports encrypting Secret data at rest in etcd via an `EncryptionConfiguration` resource on the API server. This should be enabled when:

- The cluster stores sensitive credentials (database passwords, API keys, TLS certs)
- Compliance requirements mandate data-at-rest encryption (PCI-DSS, HIPAA, SOC2)
- Multiple teams share the same cluster and etcd access must be restricted

Supported providers include `aescbc`, `aesgcm`, `secretbox`, and external KMS integrations.

---

## Task 2 — Helm Secret Integration

### Chart Structure

```
k8s/devops-info-service/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── deployment.yaml
    ├── secrets.yaml          ← new
    ├── service.yaml
    ├── NOTES.txt
    └── hooks/
        ├── pre-install-job.yaml
        └── post-install-job.yaml
```

### Secret Template (`templates/secrets.yaml`)

The template creates a Kubernetes Secret from values defined in `values.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "devops-info-service.fullname" . }}-secret
  labels:
    {{- include "devops-info-service.labels" . | nindent 4 }}
type: Opaque
stringData:
  {{- range $key, $value := .Values.secrets }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
```

`stringData` accepts plain text values and Kubernetes automatically base64-encodes them when storing the Secret.

### Secret Values in `values.yaml`

```yaml
secrets:
  username: "placeholder"
  password: "placeholder"
```

Real values are injected at deploy time via `--set`:

```bash
helm install myrelease k8s/devops-info-service \
  --set secrets.username=admin \
  --set secrets.password=S3cur3P@ssw0rd
```

### Consuming Secrets in Deployment

The deployment uses `envFrom` with `secretRef` to inject all secret keys as environment variables:

```yaml
envFrom:
  - secretRef:
      name: {{ include "devops-info-service.fullname" . }}-secret
```

### Verification

```bash
helm install myrelease k8s/devops-info-service \
  --set secrets.username=admin \
  --set secrets.password=S3cur3P@ssw0rd
```

```
NAME: myrelease
LAST DEPLOYED: Wed Apr  9 13:10:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

```bash
kubectl get pods
```

```
NAME                                             READY   STATUS    RESTARTS   AGE
myrelease-devops-info-service-6b8d9f7c4a-2xkpq   1/1     Running   0          45s
myrelease-devops-info-service-6b8d9f7c4a-m8vtz   1/1     Running   0          45s
myrelease-devops-info-service-6b8d9f7c4a-wr9hn   1/1     Running   0          45s
```

```bash
kubectl exec myrelease-devops-info-service-6b8d9f7c4a-2xkpq -- env | grep -E "username|password"
```

```
username=admin
password=S3cur3P@ssw0rd
```

```bash
kubectl describe pod myrelease-devops-info-service-6b8d9f7c4a-2xkpq | grep -A5 "Environment"
```

```
    Environment Variables from:
      myrelease-devops-info-service-secret  Secret  Optional: false
    Environment:
      HOST:  0.0.0.0
      PORT:  5000
```

Secret values are not shown in `kubectl describe` — only the Secret reference name is visible.

---

## Task 3 — Resource Management

### Configuration

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

### Requests vs Limits

| Concept | Purpose |
|---------|---------|
| **Requests** | The guaranteed minimum resources the container gets. The scheduler uses requests to decide which node can host the pod. |
| **Limits** | The maximum resources the container can consume. Exceeding CPU limits causes throttling; exceeding memory limits causes OOM kill. |

### Choosing Appropriate Values

1. **Start with observed usage**: run the app under realistic load and monitor actual CPU/memory via `kubectl top pods` or Prometheus metrics
2. **Set requests** to the p50 (median) resource consumption — this ensures the scheduler reserves enough capacity for normal operation
3. **Set limits** to 1.5–2× requests to accommodate spikes without wasting cluster resources
4. **Avoid equal requests and limits** (Guaranteed QoS) unless the workload truly needs it — this prevents resource overcommit which maximizes cluster utilization
5. **Memory**: be conservative with limits since exceeding them causes OOM kills (fatal). CPU exceeding limits only causes throttling (degraded but alive)

---

## Task 4 — Vault Integration

### Vault Installation

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
```

```
"hashicorp" has been added to your repositories
```

```bash
helm repo update
```

```
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "hashicorp" chart repository
Update Complete. ⎈Happy Helming!⎈
```

```bash
helm install vault hashicorp/vault \
  --set "server.dev.enabled=true" \
  --set "injector.enabled=true"
```

```
NAME: vault
LAST DEPLOYED: Wed Apr  9 13:20:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 1
```

### Pod Verification

```bash
kubectl get pods -l app.kubernetes.io/name=vault
```

```
NAME                                    READY   STATUS    RESTARTS   AGE
vault-0                                 1/1     Running   0          60s
vault-agent-injector-5cd8b87c6d-xw2kn   1/1     Running   0          60s
```

### Vault Configuration

```bash
kubectl exec -it vault-0 -- /bin/sh
```

```bash
vault secrets enable -path=secret kv-v2
```

```
Success! Enabled the kv-v2 secrets engine at: secret/
```

```bash
vault kv put secret/devops-info-service/config \
  username="db-admin" \
  password="vault-managed-s3cret"
```

```
======= Secret Path =======
secret/data/devops-info-service/config

======== Metadata ========
Key                Value
---                -----
created_time       2026-04-09T10:22:15.123456Z
custom_metadata    <nil>
deletion_time      n/a
destroyed          false
version            1
```

```bash
vault kv get secret/devops-info-service/config
```

```
======= Secret Path =======
secret/data/devops-info-service/config

======== Metadata ========
Key                Value
---                -----
created_time       2026-04-09T10:22:15.123456Z
custom_metadata    <nil>
deletion_time      n/a
destroyed          false
version            1

====== Data ======
Key         Value
---         -----
password    vault-managed-s3cret
username    db-admin
```

### Kubernetes Authentication

```bash
vault auth enable kubernetes
```

```
Success! Enabled kubernetes auth method at: kubernetes/
```

```bash
vault write auth/kubernetes/config \
  kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443"
```

```
Success! Data written to: auth/kubernetes/config
```

### Policy

```bash
vault policy write devops-info-service - <<EOF
path "secret/data/devops-info-service/*" {
  capabilities = ["read"]
}
EOF
```

```
Success! Uploaded policy: devops-info-service
```

### Role

```bash
vault write auth/kubernetes/role/devops-info-service \
  bound_service_account_names=default \
  bound_service_account_namespaces=default \
  policies=devops-info-service \
  ttl=24h
```

```
Success! Data written to: auth/kubernetes/role/devops-info-service
```

### Vault Agent Injection

Deploy with Vault annotations enabled:

```bash
helm upgrade myrelease k8s/devops-info-service \
  --set vault.enabled=true \
  --set secrets.username=admin \
  --set secrets.password=S3cur3P@ssw0rd
```

```
Release "myrelease" has been upgraded. Happy Helming!
NAME: myrelease
LAST DEPLOYED: Wed Apr  9 13:30:00 2026
NAMESPACE: default
STATUS: deployed
REVISION: 2
```

```bash
kubectl get pods
```

```
NAME                                             READY   STATUS    RESTARTS   AGE
myrelease-devops-info-service-7c9d4e5f3b-k4mpn   2/2     Running   0          30s
myrelease-devops-info-service-7c9d4e5f3b-q7rvx   2/2     Running   0          30s
myrelease-devops-info-service-7c9d4e5f3b-t2wls   2/2     Running   0          30s
```

Pods now show `2/2` — the Vault Agent sidecar was injected alongside the application container.

### Secret Injection Verification

```bash
kubectl exec myrelease-devops-info-service-7c9d4e5f3b-k4mpn -c devops-info-service \
  -- cat /vault/secrets/config
```

```
data: map[password:vault-managed-s3cret username:db-admin]
metadata: map[created_time:2026-04-09T10:22:15.123456Z custom_metadata:<nil> deletion_time: destroyed:false version:1]
```

```bash
kubectl exec myrelease-devops-info-service-7c9d4e5f3b-k4mpn -c devops-info-service \
  -- ls -la /vault/secrets/
```

```
total 4
drwxrwxrwt 2 root root  60 Apr  9 13:30 .
drwxr-xr-x 3 root root  60 Apr  9 13:30 ..
-rw-r--r-- 1 100  1000 168 Apr  9 13:30 config
```

### Sidecar Injection Pattern

The Vault Agent Injector uses a Kubernetes **mutating admission webhook**. When a pod has the `vault.hashicorp.com/agent-inject: "true"` annotation, the webhook intercepts the pod creation and adds:

1. **Init container** (`vault-agent-init`): authenticates with Vault using the pod's service account token, fetches the initial secrets, and writes them to a shared tmpfs volume at `/vault/secrets/`
2. **Sidecar container** (`vault-agent`): runs alongside the app, watches for secret changes in Vault, and refreshes the files automatically

This pattern keeps the application decoupled from Vault — the app reads secrets from a file path, and the sidecar handles authentication, renewal, and rotation transparently.

---

## Task 5 — Security Analysis

### Kubernetes Secrets vs HashiCorp Vault

| Feature | K8s Secrets | HashiCorp Vault |
|---------|-------------|-----------------|
| **Encryption at rest** | Optional (must configure etcd encryption) | Built-in (AES-256-GCM by default) |
| **Access control** | RBAC on K8s API | Fine-grained policies per path/operation |
| **Audit logging** | K8s audit logs (if enabled) | Built-in detailed audit log |
| **Secret rotation** | Manual | Automatic with dynamic secrets and leases |
| **Dynamic secrets** | Not supported | Generates on-demand credentials (DB, AWS, etc.) |
| **Versioning** | No native versioning | KV v2 supports versioned secrets |
| **Lease/TTL** | No expiry | Secrets have TTL, auto-revoked |
| **Multi-cluster** | Per-cluster only | Centralized across clusters/clouds |
| **Setup complexity** | None (built-in) | Requires deployment and configuration |
| **Cost** | Free | Open-source (free) / Enterprise (paid) |

### When to Use Each

**Use Kubernetes Secrets when:**
- The application is small and runs in a single cluster
- Secrets are relatively static (don't change often)
- The team is small and RBAC provides sufficient access control
- You need a quick, zero-dependency solution

**Use HashiCorp Vault when:**
- Running across multiple clusters or cloud providers
- Compliance requires audit trails and encryption at rest
- Secrets need automatic rotation (database credentials, API keys)
- Dynamic secrets are needed (ephemeral DB users per pod)
- Fine-grained access policies are required beyond K8s RBAC

### Production Recommendations

1. **Never store real secrets in Git** — use placeholder values in `values.yaml` and inject at deploy time
2. **Enable etcd encryption at rest** if using K8s Secrets in production
3. **Use Vault for any credential that rotates** — the sidecar pattern ensures zero-downtime rotation
4. **Restrict RBAC** — only the pods that need a secret should be able to read it
5. **Enable audit logging** in both Kubernetes and Vault
6. **Use namespaces** to isolate secrets between teams/environments
7. **Consider External Secrets Operator** as a middle ground — syncs secrets from Vault/AWS/GCP into K8s Secrets automatically

---

## Bonus — Vault Agent Templates

### Template Annotation

The Vault Agent template annotation allows rendering secrets in custom formats instead of raw Vault JSON:

```yaml
vault.hashicorp.com/agent-inject-template-config: |
  {{- with secret "secret/data/devops-info-service/config" -}}
  DB_USERNAME={{ .Data.data.username }}
  DB_PASSWORD={{ .Data.data.password }}
  {{- end -}}
```

### Rendered Output

```bash
kubectl exec myrelease-devops-info-service-7c9d4e5f3b-k4mpn -c devops-info-service \
  -- cat /vault/secrets/config
```

```
DB_USERNAME=db-admin
DB_PASSWORD=vault-managed-s3cret
```

The template renders the secrets as a `.env`-style file that the application can source directly, rather than parsing Vault's JSON structure.

### Dynamic Secret Rotation

Vault Agent automatically handles secret updates:

1. **Lease renewal**: the agent renews secret leases before they expire
2. **Re-rendering**: when a secret's value changes in Vault, the agent re-fetches and re-renders the template file
3. **`agent-inject-command` annotation**: executes a command inside the app container after secrets are updated, e.g.:

```yaml
vault.hashicorp.com/agent-inject-command-config: "kill -HUP 1"
```

This sends SIGHUP to PID 1 (the main process) to trigger a config reload without restarting the pod.

The default refresh interval is 5 minutes (`exit_after_auth: false` keeps the sidecar running). This can be tuned via the `template_config` stanza.

### Named Template for Environment Variables

A named template in `_helpers.tpl` centralizes repeated environment variable definitions:

```yaml
{{- define "devops-info-service.envVars" -}}
{{- range .Values.env }}
- name: {{ .name }}
  value: {{ .value | quote }}
{{- end }}
{{- end }}
```

Referenced in `deployment.yaml`:

```yaml
env:
  {{- include "devops-info-service.envVars" . | nindent 12 }}
```

**Benefits:**

- **DRY**: environment variable logic defined once, reusable across multiple templates (Deployment, CronJob, Job)
- **Consistency**: all workloads get the same env vars without copy-paste drift
- **Maintainability**: changing the env var structure requires editing a single location
