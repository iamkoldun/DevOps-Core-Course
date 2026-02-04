# Lab 2 Bonus: Multi-Stage Docker Build (Go)

## Multi-Stage Build Strategy

Two stages are used:

1. **Builder stage** (`golang:1.21-alpine`): Download dependencies, compile the Go binary. The image includes the Go toolchain and all build dependencies.
2. **Runtime stage** (`alpine:3.19`): Copy only the compiled binary from the builder. No Go compiler, no source code, no build tools. A non-root user runs the binary.

**Why multi-stage:** The compiled binary is self-contained. The final image does not need the Go SDK (hundreds of MB). Only the binary and a minimal runtime (Alpine) are shipped, so the image is much smaller and has a smaller attack surface.

## Dockerfile Stages

### Stage 1 — Builder

- **Base:** `golang:1.21-alpine` (smaller than full golang image, enough to build).
- **Steps:** Set `WORKDIR`, copy `go.mod` and `go.sum`, run `go mod download` (cached when deps unchanged), copy `main.go`, build with `CGO_ENABLED=0` for a static binary.
- **Output:** Single binary `devops-info-service` in `/build/`.

**Snippet:**
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o devops-info-service main.go
```

`-ldflags="-s -w"` strips debug info and reduces binary size.

### Stage 2 — Runtime

- **Base:** `alpine:3.19` (minimal Linux, no compiler or dev tools).
- **Steps:** Create non-root user `appuser`/`appgroup`, copy only the binary with `COPY --from=builder`, set ownership, switch to `appuser`, set `EXPOSE` and `ENV`, run the binary with `CMD`.
- **Result:** Image contains only Alpine + binary + user setup.

**Snippet:**
```dockerfile
FROM alpine:3.19
RUN addgroup -g 1000 -S appgroup && adduser -u 1000 -S appuser -G appgroup
WORKDIR /app
COPY --from=builder /build/devops-info-service .
RUN chown appuser:appgroup devops-info-service
USER appuser
EXPOSE 8080
ENV HOST=0.0.0.0 PORT=8080
CMD ["./devops-info-service"]
```

## Size Comparison

| Image / stage | Typical size | Notes |
|---------------|--------------|--------|
| Builder (golang:1.21-alpine + deps + binary) | ~350–400 MB | Not published; used only during build. |
| Final (alpine:3.19 + binary) | 18.1 MB | Published and run in production. (`docker images devops-info-service-go`). |

**Analysis:** Most of the builder size is the Go toolchain and dependencies. The final image drops all of that and keeps only the binary and Alpine base. Multi-stage achieves a large size reduction (often 90%+ compared to a single-stage image that keeps the compiler).

## Why Multi-Stage Matters for Compiled Languages

- **Size:** Final image is orders of magnitude smaller than a full SDK image.
- **Security:** No compiler, no source, fewer packages → smaller attack surface and fewer CVEs.
- **Deploy:** Faster pull and startup; better fit for resource limits and scaling.

## Build and Run

**Build:**
```bash
docker build -t devops-info-service-go .
```

**Run:**
```bash
docker run -p 8080:8080 devops-info-service-go
```

**Test:**
```bash
curl http://localhost:8080/
curl http://localhost:8080/health
```

## Terminal Output

**Build output:** Multi-stage build completes (builder then final stage), then image written and tagged devops-info-service-go, including “Successfully built” and “Successfully tagged”.

**Image size:** `docker images devops-info-service-go` → REPOSITORY devops-info-service-go, TAG latest, **SIZE 18.1MB**.

**Run and test:** `docker run -p 8080:8080 devops-info-service-go`; then `curl http://localhost:8080/` and `curl http://localhost:8080/health` return the same JSON as the Go app.

## Security Benefits

- **Non-root:** Process runs as `appuser`, not root.
- **Minimal runtime:** Alpine has no compiler or dev tools; only what’s needed to run the binary.
- **No source in image:** Only the binary is copied; no Go source or modules in the final image.

## Trade-offs and Decisions

- **Alpine vs scratch:** Alpine was chosen over `FROM scratch` so we keep a minimal shell and package manager for debugging if needed. For even smaller images, a static binary + `FROM scratch` is possible (no shell, no CA certs unless added manually).
- **Static binary:** `CGO_ENABLED=0` produces a static binary so the app runs on Alpine without extra libraries and could be moved to `scratch` later if desired.
