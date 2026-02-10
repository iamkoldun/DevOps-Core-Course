# Lab 2 Submission: Docker Containerization

## 1. Docker Best Practices Applied

### Non-root user (mandatory)

**What:** The container runs as a dedicated user `appuser` (UID 1000) in group `appgroup`, not as root.

**Why:** Running as root inside the container increases risk: if the app or a dependency is compromised, the attacker has root inside the container. Even though the host is partly isolated, running as non-root follows principle of least privilege and limits impact. Many security policies and Kubernetes runtimes expect or enforce non-root.

**Snippet:**
```dockerfile
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
...
RUN chown -R appuser:appgroup /app
USER appuser
```

### Specific base image version

**What:** Base image is `python:3.13-slim` (explicit version and variant).

**Why:** Using a fixed version (e.g. `3.13-slim`) makes builds reproducible and avoids surprise breakages when the `latest` tag changes. The `slim` variant keeps the image smaller than the full Python image while still being Debian-based and easy to work with.

**Snippet:**
```dockerfile
FROM python:3.13-slim
```

### Layer ordering and dependency caching

**What:** `requirements.txt` is copied first and `pip install` runs in a separate layer; only then `app.py` is copied.

**Why:** Dependencies change less often than application code. By copying and installing dependencies before the app code, Docker can cache the dependency layer. When only `app.py` changes, rebuilds reuse the cached dependency layer and are much faster.

**Snippet:**
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
```

### Only copy necessary files

**What:** The Dockerfile copies only `requirements.txt` and `app.py`. No `docs/`, `tests/`, `venv/`, or other unneeded files.

**Why:** Smaller build context and fewer files in the image reduce build time, image size, and attack surface. Unnecessary files (e.g. tests, docs) are not needed at runtime.

### .dockerignore

**What:** A `.dockerignore` file excludes development artifacts, version control, IDE configs, venvs, docs, and tests from the build context.

**Why:** The build context is sent to the Docker daemon. Excluding unneeded files speeds up `docker build` and avoids accidentally copying secrets or large directories. It also keeps the image free of dev-only content.

---

## 2. Image Information & Decisions

### Base image

- **Chosen:** `python:3.13-slim`
- **Justification:** Matches the Python 3.11+ requirement from Lab 1; 3.13-slim is a clear, modern choice. Slim is smaller than the full image and more predictable than Alpine for Python (no musl/glibc issues). Alpine could be used for even smaller size but adds compatibility and debugging trade-offs.

### Final image size

- **Actual size:** 156 MB (`docker images devops-info-service`).
- **Assessment:** Acceptable for a small web service. Further reduction would require Alpine or distroless and possibly multi-stage builds; for this lab, slim is a good balance of size and simplicity.

### Layer structure

1. `FROM python:3.13-slim` — base layer  
2. `RUN groupadd/useradd` — create non-root user (cached)  
3. `WORKDIR /app` — set working directory  
4. `COPY requirements.txt` + `RUN pip install` — dependencies (cached when requirements unchanged)  
5. `COPY app.py` — application code (changes most often)  
6. `RUN chown` — set ownership for appuser  
7. `USER appuser` — switch to non-root  
8. `EXPOSE` / `ENV` / `CMD` — runtime configuration  

### Optimization choices

- `pip install --no-cache-dir`: avoids storing pip cache in the image.  
- Single `RUN` for group/user creation: fewer layers.  
- No extra system packages: kept only what’s needed to run the app.

---

## 3. Build & Run Process

### Build

Run from the directory containing the Dockerfile (e.g. `app_python/`):

```bash
docker build -t devops-info-service .
```

**Your terminal output:** Build output: FROM python:3.13-slim, RUN groupadd/useradd, COPY requirements + pip install (Flask-3.1.0), COPY app.py, chown, then image written and tagged devops-info-service. (including “Successfully built” and “Successfully tagged”).

### Run

```bash
docker run -p 5000:5000 devops-info-service
```

**Your terminal output:** `Starting DevOps Info Service on 0.0.0.0:5000` and ` * Running on http://0.0.0.0:5000` (e.g. “Starting DevOps Info Service on 0.0.0.0:5000”).

### Test endpoints

In another terminal:

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
```

**Terminal output (curl responses):**

```json
# GET /
{"endpoints":[{"description":"Service information","method":"GET","path":"/"},{"description":"Health check","method":"GET","path":"/health"}],"request":{"client_ip":"172.17.0.1","method":"GET","path":"/","user_agent":"curl/8.7.1"},"runtime":{"current_time":"2026-02-04T19:20:36.370651+00:00","timezone":"UTC","uptime_human":"0 hours, 0 minutes","uptime_seconds":2},"service":{"description":"DevOps course info service","framework":"Flask","name":"devops-info-service","version":"1.0.0"},"system":{"architecture":"aarch64","cpu_count":4,"hostname":"3a879967df80","platform":"Linux","platform_version":"Linux-5.15.49-linuxkit-pr-aarch64-with-glibc2.41","python_version":"3.13.11"}}

# GET /health
{"status":"healthy","timestamp":"2026-02-04T19:20:36.387298+00:00","uptime_seconds":2}
```

**Non-root check:** `docker run --rm devops-info-service id` → `uid=1000(appuser) gid=1000(appgroup) groups=1000(appgroup)`.

### Docker Hub

- **Repository URL:** `https://hub.docker.com/r/iamkoldun/devops-info-service`
- **Terminal output (docker push):**

```
docker tag devops-info-service iamkoldun/devops-info-service:latest
docker push iamkoldun/devops-info-service:latest
The push refers to repository [docker.io/iamkoldun/devops-info-service]
249617ca4d1a: Pushed
63fe78e3eb81: Pushed
7891518430b0: Pushed
87358288cd67: Pushed
bfd34eb7fc51: Pushed
c46ac81e8348: Pushed
083605e5ab90: Mounted from library/python
675d3200abe3: Mounted from library/python
e6060824c6b0: Mounted from library/python
a0e71ab2b234: Mounted from library/python
latest: digest: sha256:1e2b16b03702d2c6e8057f8055e46fed7b999166cd01a40c42b0948b63250c95 size: 2407
```
- **Tagging strategy:** Use at least `username/devops-info-service:latest` for the lab. Optionally add tags like `:1.0.0` or `:lab02` for versioning. Same image can have multiple tags.

---

## 4. Technical Analysis

### Why the Dockerfile works this way

- Dependencies are installed in a layer that is cached when only app code changes.  
- Non-root user is created before any app files and ownership is set so the app can read them.  
- `EXPOSE 5000` documents the port; actual mapping is done by `docker run -p`.  
- `ENV HOST=0.0.0.0` ensures the app listens on all interfaces inside the container so it can be reached from the host.

### What happens if layer order changes

- If we copied `app.py` (or the whole project) before `RUN pip install`, then any change to the app would invalidate the cache for the install step. Every code change would trigger a full `pip install` again and slow down builds.

### Security considerations

- **Non-root user:** Limits damage if the process is compromised.  
- **Minimal contents:** Only app and runtime dependencies; no dev tools, shells, or extra packages beyond what’s needed.  
- **No secrets in image:** No credentials or env files baked in; configuration via env at runtime is expected.

### How .dockerignore improves the build

- Reduces the amount of data sent to the daemon as build context.  
- Avoids including `.git`, `venv/`, `__pycache__/`, docs, tests, etc., so they never appear in the image or slow the build.

---

## 5. Challenges & Solutions

Build/run verified; non-root confirmed (`docker run --rm devops-info-service id` → uid=1000). Initially forgot to set `HOST=0.0.0.0` and the app only listened on localhost inside the container; requests from the host failed until I added the ENV.”
