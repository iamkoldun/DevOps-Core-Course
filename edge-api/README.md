# edge-api — Cloudflare Worker (Lab 17)

A small HTTP API deployed on Cloudflare's global edge network using Cloudflare
Workers. Built for **Lab 17 — Cloudflare Workers Edge Deployment** of the
DevOps Core course.

> This Worker is the *edge* counterpart to the Kubernetes-hosted
> `devops-info-service` (Python Flask app from labs 1–16). It is not a
> redeployment of the same container — Cloudflare Workers is a serverless
> runtime, not a Docker host — but it preserves the same operational concerns:
> routes, health checks, configuration, secrets, persistent state, logs and
> deployments.

## Endpoints

| Path        | Method  | Description                                                       |
|-------------|---------|-------------------------------------------------------------------|
| `/`         | GET     | App metadata and the list of available endpoints                  |
| `/health`   | GET     | Liveness probe — returns `{ status: "ok" }`                       |
| `/edge`     | GET     | Cloudflare-provided request metadata (`colo`, `country`, `asn`…)  |
| `/info`     | GET     | Deployment information, runtime, and configured bindings          |
| `/counter`  | GET     | KV-backed visit counter — persists across redeploys               |
| `/settings` | GET/PUT | Admin endpoint — requires `Authorization: Bearer <API_TOKEN>`     |

## Bindings

- **vars** (`wrangler.jsonc`): `APP_NAME`, `COURSE_NAME`, `OWNER`,
  `RELATED_K8S_SERVICE` — plaintext, visible in the dashboard, fine for
  non-sensitive configuration.
- **secrets** (`wrangler secret put`): `API_TOKEN`, `ADMIN_EMAIL` — encrypted
  at rest, never returned by the API, not visible in the dashboard once set.
- **KV** (`SETTINGS`): a Workers KV namespace bound to the Worker; backs the
  `/counter` and `/settings` endpoints.

## Local development

```bash
cp .dev.vars.example .dev.vars   # fill in dev-only secret values
npm install
npx wrangler dev
```

`wrangler dev` runs the Worker on `http://localhost:8787` against the
Cloudflare runtime (miniflare). Local KV state lives under `.wrangler/`.

## Deploying

```bash
npx wrangler login              # one-time, opens browser
npx wrangler kv namespace create SETTINGS
# copy the printed id into wrangler.jsonc -> kv_namespaces[0].id

npx wrangler secret put API_TOKEN
npx wrangler secret put ADMIN_EMAIL

npx wrangler deploy
```

The public URL is `https://edge-api.<your-subdomain>.workers.dev`.

## Observability

```bash
npx wrangler tail                 # live log stream
npx wrangler deployments list     # version history
npx wrangler rollback             # roll back to the previous version
```

Full lab write-up: [`../WORKERS.md`](../WORKERS.md).
