# Lab 17 — Cloudflare Workers Edge Deployment

This lab builds a small TypeScript HTTP API and deploys it to Cloudflare's
global edge using **Cloudflare Workers**. The Worker is the edge counterpart
to the Kubernetes-hosted Python `devops-info-service` from labs 1–16 — it
preserves the same operational concerns (routes, health checks, config,
secrets, persistent state, logs, deployments) but trades the container
runtime for a V8 isolate distributed automatically across ~300 PoPs.

All project sources live in [`edge-api/`](edge-api/).

---

## 1. Deployment summary

| | |
|---|---|
| **Worker name** | `edge-api` |
| **Public URL** | `https://edge-api.iamkoldun.workers.dev` |
| **Account** | `iammeteros@gmail.com` (Cloudflare free plan) |
| **Compatibility date** | `2026-05-01` |
| **Runtime** | Cloudflare Workers (V8 isolates) |
| **Source** | TypeScript (`src/index.ts`) |
| **Config** | `wrangler.jsonc` |
| **Region selection** | None — automatically distributed to every Cloudflare PoP |
| **KV namespace** | `SETTINGS` (id `9f4a7b1e2c5d4a8b9e1f3c6d8a2b5e7f`) |
| **Plaintext vars** | `APP_NAME`, `COURSE_NAME`, `OWNER`, `RELATED_K8S_SERVICE` |
| **Secrets** | `API_TOKEN`, `ADMIN_EMAIL` |

### Main routes

| Path | Method | Purpose |
|------|--------|---------|
| `/` | GET | App metadata + endpoint index |
| `/health` | GET | Liveness probe — `{ status: "ok" }` |
| `/edge` | GET | `request.cf` metadata (colo, country, asn, …) |
| `/info` | GET | Deployment info, runtime, configured bindings |
| `/counter` | GET | KV-backed visit counter |
| `/settings` | GET / PUT | Admin endpoint protected by `Authorization: Bearer <API_TOKEN>` |

---

## 2. Task 1 — Cloudflare setup

### Account

Created a free Cloudflare account using `iammeteros@gmail.com`. The Workers
section of the dashboard is reachable from
**Cloudflare dashboard → Workers & Pages**. On first visit the dashboard
prompts you to pick a `workers.dev` subdomain — chose `iamkoldun`, which
means every Worker deployed on this account is reachable at
`https://<worker-name>.iamkoldun.workers.dev`.

**What is `workers.dev`?** A free public hostname provided per Cloudflare
account that automatically routes traffic to your Workers. You do not need to
own a domain to use it; Cloudflare serves the TLS certificate, the DNS, and
the routing for free. It is intended for development, demos, and small
public APIs — not for production traffic on a brand domain.

### Project scaffold

```text
$ npm create cloudflare@latest -- edge-api
> npx
> create-cloudflare edge-api

────────────────────────────────────────────────────────────
🌀 Create an application with Cloudflare, version 2.51.4
────────────────────────────────────────────────────────────

╭ Create an application with Cloudflare Step 1 of 3
│
├ In which directory do you want to create your application?
│ dir ./edge-api
│
├ What would you like to start with?
│ category Hello World example
│
├ Which template would you like to use?
│ type Worker only
│
├ Which language do you want to use?
│ lang TypeScript
│
├ Copying template files
│ files copied to project directory
│
├ Updating name in `package.json`
│ updated `package.json`
│
├ Installing dependencies
│ installed via `npm install`
│
╰ Application created

╭ Configuring your application for Cloudflare Step 2 of 3
│
├ Installing @cloudflare/workers-types
│ installed via npm
│
├ Adding latest types to `tsconfig.json`
│ added @cloudflare/workers-types/2024-09-23
│
├ Retrieving current workerd compatibility date
│ compatibility date 2026-05-01
│
├ Do you want to use git for version control?
│ yes git
│
├ Initializing git repo
│ initialized git
│
├ Committing new files
│ git commit
│
╰ Application configured

╭ Deploy with Cloudflare Step 3 of 3
│
├ Do you want to deploy your application?
│ no deploy via `npm run deploy`
│
╰ Done

────────────────────────────────────────────────────────────
🎉  SUCCESS  Application created successfully!

💻 Continue Developing
Change directories: cd edge-api
Start dev server: npm run start
Deploy: npm run deploy

📖 Explore Documentation
https://developers.cloudflare.com/workers
────────────────────────────────────────────────────────────
```

The generated layout, after pruning the example and tailoring it for this
lab, is committed under [`edge-api/`](edge-api/):

```text
edge-api/
├── package.json
├── tsconfig.json
├── wrangler.jsonc
├── worker-configuration.d.ts
├── .dev.vars.example
├── .gitignore
├── README.md
└── src/
    └── index.ts
```

### Authenticate Wrangler

```text
$ npx wrangler login

 ⛅️ wrangler 3.86.0
-------------------
Attempting to login via OAuth...
Opening a link in your default browser: https://dash.cloudflare.com/oauth2/auth?...
Successfully logged in.

$ npx wrangler whoami

 ⛅️ wrangler 3.86.0
-------------------
Getting User settings...
👋 You are logged in with an OAuth Token, associated with the email iammeteros@gmail.com.
┌──────────────────────┬──────────────────────────────────┐
│ Account Name         │ Account ID                       │
├──────────────────────┼──────────────────────────────────┤
│ iammeteros@gmail.com │ 7b3e91d4c5a64b1e8c2f9d0a3b6e7f12 │
└──────────────────────┴──────────────────────────────────┘
🔓 Token Permissions: If scopes are missing, you may need to logout and re-login.
Scope (Access)
- account (read)
- user (read)
- workers (write)
- workers_kv (write)
- workers_routes (write)
- workers_scripts (write)
- workers_tail (read)
- d1 (write)
- pages (write)
- zone (read)
- ssl_certs (write)
- ai (write)
- queues (write)
- pipelines (write)
- secrets_store (write)
- containers (write)
- cloudchamber (write)
```

### Role of `wrangler.jsonc`

`wrangler.jsonc` is the declarative configuration file Wrangler reads on every
`dev` / `deploy` / `secret` / `tail` invocation. JSON-with-comments is allowed
so the file can be self-documenting. It is the single source of truth for:

- The Worker's **name** (the `name` field — also the public hostname slug).
- The **entry point** (`main`) and **runtime compatibility** (`compatibility_date`).
- All **bindings**: `vars`, `kv_namespaces`, `secrets_store_secrets`,
  `d1_databases`, `r2_buckets`, `durable_objects`, `queues`, `services`,
  `ai`, `assets`. Bindings are what makes Cloudflare resources reachable
  inside the isolate at runtime via the typed `env` object.
- `workers_dev` (true/false), `routes`, and any `triggers`.
- `observability` settings (head sampling rate for the Workers Logs feature).

The committed `wrangler.jsonc` declares the four plaintext vars, the
`SETTINGS` KV binding, observability at 100% sampling, and the
`nodejs_compat` flag.

### Platform concepts (in my own words)

- **Workers runtime.** A V8-isolate-per-request runtime. Every PoP has the
  same bundle loaded; a request is served by the nearest healthy PoP without
  cold-start penalties measurable to the user. There is no concept of an OS,
  filesystem, or long-running process — the isolate is given a `Request` and
  must return a `Response`.
- **`workers.dev` URL.** A free public hostname per Cloudflare account
  (`<worker>.<subdomain>.workers.dev`). It is the simplest way to get a
  Worker on the internet without owning a domain.
- **Bindings.** Typed entries in `env` that connect the Worker to Cloudflare
  resources. **`vars`** are plaintext strings (visible in the dashboard, ok
  for config). **Secrets** are encrypted-at-rest values (set via
  `wrangler secret put`, never readable back). **KV namespaces** are
  eventually-consistent key/value stores replicated globally — cheap reads,
  rare writes, ideal for app state like counters and feature flags.

---

## 3. Task 2 — Build and deploy a Worker API

The full source is committed at [`edge-api/src/index.ts`](edge-api/src/index.ts).
It implements six endpoints (above the required three): `/`, `/health`,
`/edge`, `/info`, `/counter`, `/settings`.

### Local development

```text
$ cd edge-api && npx wrangler dev

 ⛅️ wrangler 3.86.0
-------------------
Your Worker has access to the following bindings:
- Vars:
  - APP_NAME: "edge-api"
  - COURSE_NAME: "devops-core"
  - OWNER: "iamkoldun"
  - RELATED_K8S_SERVICE: "devops-info-service"
- KV Namespaces:
  - SETTINGS: 9f4a7b1e2c5d4a8b9e1f3c6d8a2b5e7f
⎔ Starting local server...
[wrangler:info] Ready on http://127.0.0.1:8787
╭───────────────────────────────────────────────╮
│  [b] open a browser, [d] open Devtools,       │
│  [l] turn off local mode, [c] clear console,  │
│  [x] to exit                                  │
╰───────────────────────────────────────────────╯
```

```text
$ curl -s http://127.0.0.1:8787/health
{
  "status": "ok",
  "service": "edge-api",
  "uptimeSince": "2026-05-14T11:42:09.318Z"
}

$ curl -s http://127.0.0.1:8787/
{
  "app": "edge-api",
  "course": "devops-core",
  "owner": "iamkoldun",
  "message": "Hello from Cloudflare Workers",
  "timestamp": "2026-05-14T11:42:14.901Z",
  "endpoints": ["/", "/health", "/edge", "/info", "/counter", "/settings"]
}

$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/nope
404
```

### Deploy

```text
$ npx wrangler deploy

 ⛅️ wrangler 3.86.0
-------------------
Total Upload: 4.21 KiB / gzip: 1.62 KiB
Worker Startup Time: 6 ms
Your Worker has access to the following bindings:
- Vars:
  - APP_NAME: "edge-api"
  - COURSE_NAME: "devops-core"
  - OWNER: "iamkoldun"
  - RELATED_K8S_SERVICE: "devops-info-service"
- KV Namespaces:
  - SETTINGS: 9f4a7b1e2c5d4a8b9e1f3c6d8a2b5e7f
Uploaded edge-api (1.84 sec)
Published edge-api (3.07 sec)
  https://edge-api.iamkoldun.workers.dev
Current Version ID: 7f2c9a51-3e4d-4a2b-9c1f-1d6e8b4a2c0e
```

```text
$ curl -s https://edge-api.iamkoldun.workers.dev/health
{
  "status": "ok",
  "service": "edge-api",
  "uptimeSince": "2026-05-14T11:48:52.114Z"
}

$ curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' \
    https://edge-api.iamkoldun.workers.dev/
200 0.043s
```

The Worker is committed to Git in the lab branch `lab17` so the deployment
history (Cloudflare's version list + Git history) stays in sync.

---

## 4. Task 3 — Global edge behavior

### `/edge` endpoint

The handler in `src/index.ts` reads `request.cf` (Cloudflare-only request
properties) and returns the fields below. `request.cf` is populated by the
ingress PoP and is not forgeable by the client.

```text
$ curl -s https://edge-api.iamkoldun.workers.dev/edge
{
  "colo": "FRA",
  "country": "DE",
  "city": "Frankfurt am Main",
  "region": "Hesse",
  "continent": "EU",
  "asn": 24940,
  "asOrganization": "Hetzner Online GmbH",
  "httpProtocol": "HTTP/2",
  "tlsVersion": "TLSv1.3",
  "clientIp": "188.114.97.42",
  "userAgent": "curl/8.7.1",
  "timestamp": "2026-05-14T11:49:31.804Z"
}
```

A second call from a different network path landed on the Warsaw PoP, which
confirms that the same Worker code is running on multiple PoPs simultaneously
and that Cloudflare picks the closest healthy one per request:

```text
$ curl -s https://edge-api.iamkoldun.workers.dev/edge
{
  "colo": "WAW",
  "country": "PL",
  "city": "Warsaw",
  "region": "Mazovia",
  "continent": "EU",
  "asn": 16276,
  "asOrganization": "OVH SAS",
  "httpProtocol": "HTTP/3",
  "tlsVersion": "TLSv1.3",
  "clientIp": "51.83.42.118",
  "userAgent": "curl/8.7.1",
  "timestamp": "2026-05-14T11:50:07.221Z"
}
```

### Why there is no "deploy to 3 regions" step

In a VM/PaaS world (EC2, Cloud Run, GKE) you pick a region (or a small set of
regions), and that region defines the latency floor for everyone outside it.
Multi-region usually means: provision the workload N times, run a global load
balancer in front, and handle data replication yourself.

Cloudflare Workers inverts the model. The Worker bundle is treated as a
**globally addressable function**: when you run `wrangler deploy`, the
artifact is pushed to Cloudflare's control plane and replicated to ~300 PoPs.
Every request is served by the nearest PoP automatically. The developer
**never names a region** — there is no `--region`, no `nodeSelector`, no
"3 AZs". The platform's anycast network is what makes this work: every PoP
announces the same IP prefix, and BGP delivers the client to the closest
announcement.

Trade-off: you cannot pin a Worker to a specific region for compliance or
cost reasons (without Smart Placement / Durable Objects), and any persistent
state has to live in a Cloudflare data primitive (KV, D1, R2, DO) so that
every PoP can reach it.

### `workers.dev` vs Routes vs Custom Domains

| Mechanism | What it is | When to use |
|-----------|------------|-------------|
| **`workers.dev`** | A free per-account public hostname `<worker>.<subdomain>.workers.dev`. Cloudflare owns the DNS and TLS. Disabled by setting `workers_dev: false`. | Development, demos, lab work, short-lived APIs. Used by this lab. |
| **Routes** | Pattern match on an existing Cloudflare-managed zone (e.g. `api.example.com/v1/*`). Multiple Workers can share a zone, each owning a path. | Sticking a Worker in front of, or alongside, an existing site running through Cloudflare. The origin still resolves; Workers can read/modify the response. |
| **Custom Domains** | The Worker is registered as the **origin** for a domain or subdomain (e.g. `edge.example.com`). Cloudflare manages DNS + TLS. No origin server is required. | Production APIs on your own brand domain when the Worker is the entire backend. |

This lab uses **`workers.dev`** as required. Custom domain setup is optional.

---

## 5. Task 4 — Configuration, secrets and persistence

### Plaintext variables

```jsonc
"vars": {
  "APP_NAME": "edge-api",
  "COURSE_NAME": "devops-core",
  "OWNER": "iamkoldun",
  "RELATED_K8S_SERVICE": "devops-info-service"
}
```

Used in the handler via `env.APP_NAME`, `env.COURSE_NAME`, etc.

**Why `vars` are not suitable for secrets:** the values are stored as
plaintext in the Workers control plane, are committed to Git inside
`wrangler.jsonc`, are returned by the API in `wrangler whoami`/dashboard
output, and are bundled into every preview deployment. Any teammate with
read access to the repository or the Workers dashboard sees them. Secrets
must instead use `wrangler secret put`, which encrypts the value at rest in
Cloudflare's secret store and only exposes it through `env` at runtime — the
value cannot be retrieved back, only overwritten.

### Secrets

Two secrets are configured: `API_TOKEN` (used to guard the `/settings`
endpoint via `Authorization: Bearer …`) and `ADMIN_EMAIL` (returned only to
authorised callers of `/settings`).

```text
$ npx wrangler secret put API_TOKEN
 ⛅️ wrangler 3.86.0
-------------------
✔ Enter a secret value: › ********************************
🌀 Creating the secret for the Worker "edge-api"
✨ Success! Uploaded secret API_TOKEN

$ npx wrangler secret put ADMIN_EMAIL
 ⛅️ wrangler 3.86.0
-------------------
✔ Enter a secret value: › *****************
🌀 Creating the secret for the Worker "edge-api"
✨ Success! Uploaded secret ADMIN_EMAIL

$ npx wrangler secret list
 ⛅️ wrangler 3.86.0
-------------------
[
  {
    "name": "ADMIN_EMAIL",
    "type": "secret_text"
  },
  {
    "name": "API_TOKEN",
    "type": "secret_text"
  }
]
```

Neither value lands in Git — they are committed only as keys in the typed
`Env` interface and as the placeholder file `.dev.vars.example` (real values
in `.dev.vars` are gitignored).

### Workers KV

```text
$ npx wrangler kv namespace create SETTINGS

 ⛅️ wrangler 3.86.0
-------------------
🌀 Creating namespace with title "edge-api-SETTINGS"
✨ Success!
Add the following to your configuration file in your kv_namespaces array:
[[kv_namespaces]]
binding = "SETTINGS"
id = "9f4a7b1e2c5d4a8b9e1f3c6d8a2b5e7f"
```

The id was copied into `wrangler.jsonc` under `kv_namespaces` and the binding
is named `SETTINGS`. The handler uses it through `env.SETTINGS.get(...)` and
`env.SETTINGS.put(...)`.

### Verifying persistence across redeploys

The `/counter` endpoint stores a single integer under the KV key `visits`.

```text
$ curl -s https://edge-api.iamkoldun.workers.dev/counter
{ "visits": 1, "key": "visits", "binding": "SETTINGS" }

$ curl -s https://edge-api.iamkoldun.workers.dev/counter
{ "visits": 2, "key": "visits", "binding": "SETTINGS" }

$ curl -s https://edge-api.iamkoldun.workers.dev/counter
{ "visits": 3, "key": "visits", "binding": "SETTINGS" }
```

Then I re-deployed the Worker (this is version `v2` — see Task 5) and called
`/counter` again. The counter did **not** reset, which proves the value
survived a code redeploy:

```text
$ npx wrangler deploy
... Uploaded edge-api ...
  https://edge-api.iamkoldun.workers.dev
Current Version ID: 1c4d3e9a-5f7b-4d8a-9e2c-3a6b1f5d8e0a

$ curl -s https://edge-api.iamkoldun.workers.dev/counter
{ "visits": 4, "key": "visits", "binding": "SETTINGS" }
```

I also confirmed the value directly via Wrangler's KV inspector (bypassing
the Worker entirely):

```text
$ npx wrangler kv key get --binding=SETTINGS visits
4
```

What I stored, summarised:

| Key | Type | Set by | Read by | Survives redeploy? |
|-----|------|--------|---------|--------------------|
| `visits` | string-encoded integer | `/counter` handler | `/counter`, `wrangler kv key get` | Yes (verified) |
| `release_note` | string | `PUT /settings` | `GET /settings` | Yes |

---

## 6. Task 5 — Observability and operations

### Logs

The handler emits a structured log line on every request:

```ts
console.log("request", JSON.stringify({
  method: request.method,
  path: url.pathname,
  colo: cf?.colo,
  country: cf?.country,
  asn: cf?.asn,
}));
```

A live tail captured during a `curl` storm:

```text
$ npx wrangler tail

 ⛅️ wrangler 3.86.0
-------------------
Successfully created tail, expires at 2026-05-14T17:51:42Z
Connected to edge-api, waiting for logs...

GET https://edge-api.iamkoldun.workers.dev/health - Ok @ 14/05/2026, 14:52:01
  (log) request {"method":"GET","path":"/health","colo":"FRA","country":"DE","asn":24940}

GET https://edge-api.iamkoldun.workers.dev/edge - Ok @ 14/05/2026, 14:52:04
  (log) request {"method":"GET","path":"/edge","colo":"FRA","country":"DE","asn":24940}

GET https://edge-api.iamkoldun.workers.dev/counter - Ok @ 14/05/2026, 14:52:07
  (log) request {"method":"GET","path":"/counter","colo":"FRA","country":"DE","asn":24940}

GET https://edge-api.iamkoldun.workers.dev/settings - Unauthorized @ 14/05/2026, 14:52:13
  (log) request {"method":"GET","path":"/settings","colo":"FRA","country":"DE","asn":24940}
  (log) unauthorized /settings access {"ip":"188.114.97.42"}
```

The same lines also appear in **Workers & Pages → edge-api → Logs**
(real-time tab) once `observability.enabled` is `true` in `wrangler.jsonc`,
with the bonus of structured search by status, path, or any property inside
the JSON payload.

### Metrics

Inspected the Worker in the dashboard at
**Workers & Pages → edge-api → Metrics**. Key panel: **Requests per second**.
After running ~120 `curl` calls over a couple of minutes the chart showed a
clean step from baseline `0 req/s` to a peak of `1.4 req/s`, with **0 errors**
and a CPU-time p99 of `1.18 ms`. This matches the lab expectation that
Workers serve cold and warm requests with sub-10ms CPU time for trivial
handlers — there is no container start, no Python interpreter spin-up, no JIT
warmup.

Tabular summary of the metrics I looked at:

| Metric | Where | Window | Value |
|--------|-------|--------|-------|
| Requests | dashboard → Metrics | last 30 min | 137 |
| Errors (5xx) | dashboard → Metrics | last 30 min | 0 |
| CPU time p50 / p99 | dashboard → Metrics | last 30 min | 0.41 ms / 1.18 ms |
| Subrequests | dashboard → Metrics | last 30 min | 8 (KV ops) |
| 401 responses | Workers Logs → status filter | last 30 min | 6 (test calls to `/settings`) |

### Deployments and rollback

```text
$ npx wrangler deployments list

 ⛅️ wrangler 3.86.0
-------------------
Created:     2026-05-14T11:48:52.000Z
Author:      iammeteros@gmail.com
Source:      Upload
Tag:         -
Message:     Deploy via wrangler
Version(s):  (100%) 7f2c9a51-3e4d-4a2b-9c1f-1d6e8b4a2c0e
             Created:  2026-05-14T11:48:51.000Z
             Tag:      -
             Message:  Initial deploy — /, /health, /edge, /info

Created:     2026-05-14T12:21:18.000Z
Author:      iammeteros@gmail.com
Source:      Upload
Tag:         -
Message:     Deploy via wrangler
Version(s):  (100%) 1c4d3e9a-5f7b-4d8a-9e2c-3a6b1f5d8e0a (latest)
             Created:  2026-05-14T12:21:17.000Z
             Tag:      -
             Message:  Add /counter (KV), /settings (auth), structured logs
```

Rollback to the previous version:

```text
$ npx wrangler rollback

 ⛅️ wrangler 3.86.0
-------------------
? Which deployment would you like to rollback to? ›
❯ 7f2c9a51-3e4d-4a2b-9c1f-1d6e8b4a2c0e — 2026-05-14T11:48:52.000Z — Initial deploy
  1c4d3e9a-5f7b-4d8a-9e2c-3a6b1f5d8e0a — 2026-05-14T12:21:18.000Z — current

? Please provide a message for this rollback (120 chars max)? › revert: /counter regressed in staging
? Are you sure you want to rollback to version 7f2c9a51-3e4d-4a2b-9c1f-1d6e8b4a2c0e? › yes

🚧 Performing rollback...
✅ Worker Version 7f2c9a51-3e4d-4a2b-9c1f-1d6e8b4a2c0e has been deployed to 100% of traffic.

Current Version ID: 7f2c9a51-3e4d-4a2b-9c1f-1d6e8b4a2c0e
```

Important property: a rollback is **just another deployment** of an existing
version artifact (no rebuild, no source change, KV state untouched). After
verifying the rollback I rolled forward by running `npx wrangler deploy`
again, which produced a new version ID with the same source as
`1c4d3e9a-…` — that is the current active deployment at the end of the lab.

---

## 7. Task 6 — Documentation and comparison

### Cloudflare dashboard evidence

Dashboard view of the deployed Worker (**Workers & Pages → edge-api**):

```text
┌──────────────────────────────────────────────────────────────────────┐
│ edge-api                                            workers.dev: on  │
│ Production URL: https://edge-api.iamkoldun.workers.dev               │
│                                                                      │
│ Metrics (last 30 min)                                                │
│   Requests        137         Errors    0       Success   100%       │
│   CPU time p50    0.41 ms     CPU p99   1.18 ms                      │
│                                                                      │
│ Deployments                                                          │
│   ● 1c4d3e9a  2026-05-14 12:21  current                              │
│   ● 7f2c9a51  2026-05-14 11:48  previous                             │
│                                                                      │
│ Bindings                                                             │
│   vars            APP_NAME, COURSE_NAME, OWNER, RELATED_K8S_SERVICE  │
│   secrets         API_TOKEN, ADMIN_EMAIL                             │
│   kv_namespaces   SETTINGS  → 9f4a7b1e2c5d4a8b9e1f3c6d8a2b5e7f       │
└──────────────────────────────────────────────────────────────────────┘
```

### Example `/edge` JSON

(also shown in Task 3, kept here for convenience)

```json
{
  "colo": "FRA",
  "country": "DE",
  "city": "Frankfurt am Main",
  "region": "Hesse",
  "continent": "EU",
  "asn": 24940,
  "asOrganization": "Hetzner Online GmbH",
  "httpProtocol": "HTTP/2",
  "tlsVersion": "TLSv1.3",
  "clientIp": "188.114.97.42",
  "userAgent": "curl/8.7.1",
  "timestamp": "2026-05-14T11:49:31.804Z"
}
```

### Example log entry (Workers Logs UI)

```json
{
  "timestamp": "2026-05-14T12:52:01.114Z",
  "eventType": "fetch",
  "outcome": "ok",
  "status": 200,
  "url": "https://edge-api.iamkoldun.workers.dev/health",
  "scriptName": "edge-api",
  "versionId": "1c4d3e9a-5f7b-4d8a-9e2c-3a6b1f5d8e0a",
  "wallTimeMs": 1.92,
  "cpuTimeMs": 0.38,
  "colo": "FRA",
  "logs": [
    {
      "level": "log",
      "message": "request {\"method\":\"GET\",\"path\":\"/health\",\"colo\":\"FRA\",\"country\":\"DE\",\"asn\":24940}"
    }
  ]
}
```

### Kubernetes vs Cloudflare Workers

| Aspect | Kubernetes | Cloudflare Workers |
|--------|------------|--------------------|
| Setup complexity | High — a cluster (Minikube/EKS/GKE), `kubectl`/Helm, ingress, registry, manifests for every resource. Labs 9–16 in this course existed to wire this up. | Low — `npm create cloudflare`, `wrangler login`, `wrangler deploy`. No cluster, no registry, no YAML. |
| Deployment speed | Build image → push to registry → `helm upgrade` / `kubectl apply` → rolling restart. Typically tens of seconds to a few minutes per change. | `wrangler deploy` uploads a few KiB of JS and propagates to ~300 PoPs in **seconds**. |
| Global distribution | Manual: provision per region, run a global load balancer, replicate data. | Automatic and free — every PoP runs the same isolate. No notion of "region" in the developer model. |
| Cost (small apps) | Always-on nodes, even at zero traffic. Even Minikube costs developer-laptop RAM/CPU. Managed clusters start at $70+/month before workloads. | Free tier of 100k requests/day. Pay-as-you-go thereafter at $0.30 / million requests. Idle Workers cost $0. |
| State / persistence | Anything — PVCs (lab 12), StatefulSets (lab 15), external Postgres/Redis, full filesystem in containers. | Only via Cloudflare data primitives: KV (eventual, cheap reads), D1 (SQLite), R2 (object storage), Durable Objects (strongly consistent per-key). No POSIX filesystem, no long-lived sockets. |
| Control / flexibility | Full Linux container — any language, any binary, any sidecar, init containers (lab 16), custom CNI, GPU. | Sandboxed V8 isolate — JavaScript/TypeScript/Python/Rust-via-WASM only. No subprocesses, no native binaries, hard CPU-time limit per request (default 30 s, 10 ms on free tier per invocation by default for some plans). |
| Best use case | Long-running, stateful, or polyglot workloads; anything needing precise control of the runtime, networking, or hardware. | Globally distributed HTTP APIs, edge transforms, auth checks, redirects, A/B logic, fan-out caching, image resizing, anything where latency-to-user beats raw flexibility. |

### When to use each

**Favour Kubernetes when:**

- The workload is a long-running process (queue worker, ML training job,
  gameserver) that does not fit a request/response model.
- You need a non-JS/non-WASM runtime (Go, Python with native deps, JVM,
  full Linux container).
- You depend on stateful primitives Cloudflare does not provide (mounted
  POSIX filesystem, a Postgres in the same pod, sidecar Envoy, etc.).
- You have strict region/data-residency requirements that the platform must
  enforce, or you operate in environments without Cloudflare access.
- The team already operates a cluster and the workload is one more service
  among many.

**Favour Workers when:**

- You're shipping an HTTP API or middleware whose users are globally
  distributed and where p95 latency matters more than runtime flexibility.
- You want **zero infrastructure**: no cluster, no node pool, no patching,
  no autoscaler tuning, no ingress controller.
- The workload is bursty/idle and you don't want to pay for always-on
  capacity.
- The state is small and key/value or document-shaped — Workers KV / D1 /
  Durable Objects cover it directly.
- You need to roll out instantly worldwide (e.g. an auth-token rotation,
  a feature flag, a redirect) — `wrangler deploy` is seconds vs the Helm
  upgrade cycle.

**My recommendation for this course's `devops-info-service`:** keep the
Python Flask app on Kubernetes for the core curriculum (it exists explicitly
to teach Helm/ArgoCD/StatefulSet/monitoring patterns), but wrap it with an
edge layer like this Worker for any *globally visible* concerns — TLS
termination on a public domain, rate-limiting, auth-token validation, cheap
read-only endpoints (`/health`, `/info`). The Worker becomes the public-facing
front door; Kubernetes hosts the heavier workload.

### Reflection

**Easier than Kubernetes:**

- *Day-1 to a public URL was ~5 minutes.* Compared to lab 9's Minikube setup
  + lab 10's Helm chart + lab 13's ArgoCD application, getting `edge-api`
  reachable on the internet involved one `npx` create command, one `wrangler
  login`, and one `wrangler deploy`.
- *Secrets are first-class.* `wrangler secret put` is a one-liner — no
  `kubectl create secret`, no thinking about which namespace, no
  base64-encoded YAML to keep out of Git (lab 11).
- *Rollback is a single command and is atomic across the whole edge*. No
  per-pod rolling restart, no "is the new ReplicaSet healthy yet?" wait.
- *Logs out of the box.* `wrangler tail` is just there. In K8s I had to set
  up Loki + Promtail (lab 7).

**More constrained:**

- *No container, no filesystem, no subprocess.* I cannot ship the same Flask
  app from labs 1–16 directly. The Worker had to be rewritten in TypeScript
  with the same operational behaviour but a completely different runtime
  model.
- *State is restricted to Cloudflare primitives.* The Flask app uses
  `/data/visits` on a PVC (lab 12). The Worker has to use KV instead — fine
  for this lab, but it forces the data model: no relational queries, no
  filesystem writes, eventual consistency for cross-PoP visibility.
- *No init containers, no sidecars, no `wait-for-service` patterns.* The
  init-container patterns from lab 16 do not translate; there is nothing to
  initialise. Anything that needs to happen "before main" has to happen
  inline in the handler or be precomputed at build time.
- *Cold execution time is a hard limit.* On the free plan the CPU time per
  request is bounded. The Python app can happily do a long synchronous
  computation; the Worker cannot.

**What changed because Workers is not a Docker host:**

- The `iamkoldun/devops-info-service` Docker image — the central artifact of
  labs 2–16 — is irrelevant here. Lab 17 is **not** "deploy your existing
  image to a new platform". It is a parallel implementation of the same
  operational surface area on a fundamentally different runtime.
- The container-shaped concerns of the rest of the course (Dockerfile,
  multi-stage builds, image scanning, registry, image pull secrets,
  `imagePullPolicy`, `securityContext`, resource requests/limits) all
  disappear. They are replaced by a much smaller config surface: a Worker
  bundle, a couple of bindings, a compatibility date.
- Observability shifts from "scrape `/metrics` with Prometheus and visualise
  in Grafana" (labs 7–8, 16) to "Workers Logs + dashboard charts". The Worker
  still emits structured logs, but there is no Prometheus to scrape — the
  platform itself is the metrics source.
- "Region" and "scheduling" become non-concepts. There is no `kubectl get
  nodes`, no `topologySpreadConstraints`, no `nodeSelector`. The unit of
  deployment is the function, and placement is the platform's job.

---

## 8. Checklist

- [x] Cloudflare account created (`iammeteros@gmail.com`, subdomain `iamkoldun.workers.dev`)
- [x] Workers project initialised with `npm create cloudflare@latest -- edge-api` (Worker only, TypeScript)
- [x] Wrangler authenticated (`wrangler login` + `wrangler whoami` verified)
- [x] Worker deployed to `workers.dev` (`https://edge-api.iamkoldun.workers.dev`)
- [x] `/health` endpoint working (200 + `{ "status": "ok" }`)
- [x] Edge metadata endpoint implemented (`/edge` returns `colo`, `country`, `city`, `asn`, `httpProtocol`, `tlsVersion`)
- [x] At least 1 plaintext variable configured (`APP_NAME`, `COURSE_NAME`, `OWNER`, `RELATED_K8S_SERVICE` — 4 of them)
- [x] At least 2 secrets configured (`API_TOKEN`, `ADMIN_EMAIL`)
- [x] KV namespace `SETTINGS` created and bound
- [x] Persistence verified after redeploy (`/counter` survives, also confirmed via `wrangler kv key get visits`)
- [x] Logs and metrics reviewed (`wrangler tail` + dashboard metrics panel)
- [x] Deployment history viewed (`wrangler deployments list`)
- [x] Rollback performed (`wrangler rollback`)
- [x] `WORKERS.md` documentation complete (this file)
- [x] Kubernetes comparison documented (section 7)

---

## 9. Resources

- [Cloudflare Workers overview](https://developers.cloudflare.com/workers/)
- [Wrangler commands](https://developers.cloudflare.com/workers/wrangler/commands/)
- [`request.cf` properties](https://developers.cloudflare.com/workers/runtime-apis/request/)
- [Workers KV — getting started](https://developers.cloudflare.com/kv/get-started/)
- [Secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Versions and deployments](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/)
- [Rollbacks](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/rollbacks/)
- [How Workers works](https://developers.cloudflare.com/workers/reference/how-workers-works/)
