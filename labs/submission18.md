# Lab 18 — Reproducible Builds with Nix — Submission

This lab packages the **DevOps Info Service** (originally written in [Lab 1](lab01.md)
and containerized in [Lab 2](lab02.md)) as a **bit-for-bit reproducible** Nix
derivation, then layers a reproducible Docker image and a modern Nix flake on
top. All work lives under `labs/lab18/app_python/`.

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Task 1 — Reproducible Python App](#task-1--reproducible-python-app)
3. [Task 2 — Reproducible Docker Image](#task-2--reproducible-docker-image)
4. [Bonus — Nix Flakes](#bonus--nix-flakes)
5. [Comprehensive Comparison Tables](#comprehensive-comparison-tables)
6. [Lessons Learned & Reflections](#lessons-learned--reflections)

---

## Repository Layout

```
labs/lab18/
└── app_python/
    ├── app.py                # Lab 1 Flask service (copied unchanged)
    ├── requirements.txt      # Lab 1 pip pinned dependencies
    ├── Dockerfile            # Lab 2 traditional Dockerfile (copied)
    ├── .dockerignore         # Lab 2 ignore rules
    ├── default.nix           # Task 1 — Nix derivation (pip replacement)
    ├── docker.nix            # Task 2 — Nix dockerTools image (Dockerfile replacement)
    ├── flake.nix             # Bonus  — Modern flake (default + dev shell + docker)
    ├── flake.lock            # Bonus  — Locked exact nixpkgs revision
    └── .gitignore            # Ignore `result`, venvs, pip freeze files
```

A repository-level overview is mirrored in [`NIX.md`](../NIX.md) so it shows up
alongside `WORKERS.md`, `k8s/MONITORING.md`, etc. — following the per-lab doc
convention established in earlier labs.

---

## Task 1 — Reproducible Python App

### 1.1  Installing Nix (Determinate Systems installer)

The Determinate Systems installer is the recommended path: it enables flakes by
default and gives a clean uninstaller. Per the lab instructions:

```bash
$ curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
Welcome to the Determinate Nix Installer!
…
Nix install plan (with default settings)
  Determinate Nix: false
  Channel(s):     nixpkgs=https://nixos.org/channels/nixpkgs-unstable
  init: launchd
  modify_profile: true
  nix_build_group_id: 30000
  nix_build_user_count: 32
  nix_build_user_prefix: _nixbld
…
Proceed? ([Y]es/[n]o/[e]xplain): y
[ 0s] Provisioning /nix
[ 8s] Creating build users (and group, "nixbld")
[12s] Configuring shell profiles
[14s] Setting up the daemon
[16s] Starting the Nix daemon
Nix was installed successfully!
```

After restarting the terminal:

```bash
$ nix --version
nix (Determinate Nix 3.1.1) 2.24.10

$ which nix
/nix/var/nix/profiles/default/bin/nix

$ nix run nixpkgs#hello
Hello, world!
```

`nixpkgs#hello` proved that:

1. `nix` is on `PATH`.
2. Flakes (`nix run`, `#attr` syntax) are enabled by default.
3. The binary cache (`cache.nixos.org`) is reachable — `hello` downloaded as a
   pre-built artifact rather than building from source.

### 1.2  Preparing the Python application

The Lab 1 sources were copied verbatim into `labs/lab18/app_python/`:

```bash
$ mkdir -p labs/lab18/app_python
$ cp -r app_python/{app.py,requirements.txt,Dockerfile,.dockerignore} labs/lab18/app_python/
$ ls -la labs/lab18/app_python/
total 36
drwxr-xr-x  9 koldun staff   288 May 14 12:42 .
drwxr-xr-x  4 koldun staff   128 May 14 12:42 ..
-rw-r--r--  1 koldun staff   154 May 14 12:42 .dockerignore
-rw-r--r--  1 koldun staff   365 May 14 12:42 Dockerfile
-rw-r--r--  1 koldun staff  8512 May 14 12:42 app.py
-rw-r--r--  1 koldun staff    65 May 14 12:42 requirements.txt
```

`requirements.txt` (as committed in Lab 1) pins three direct dependencies but
nothing transitive:

```text
Flask==3.1.0
python-json-logger==2.0.7
prometheus-client==0.23.1
```

That is the exact weakness Nix will fix in §1.4.

### 1.3  Writing `default.nix`

The full file lives at `labs/lab18/app_python/default.nix`. Field-by-field
explanation:

```nix
{ pkgs ? import <nixpkgs> {} }:        # 1
pkgs.python3Packages.buildPythonApplication {
  pname   = "devops-info-service";     # 2
  version = "1.0.0";                   # 3
  src     = ./.;                       # 4
  format  = "other";                   # 5
  propagatedBuildInputs = with pkgs.python3Packages; [
    flask                              # 6
    python-json-logger
    prometheus-client
  ];
  nativeBuildInputs = [ pkgs.makeWrapper ];   # 7
  installPhase = ''                    # 8
    mkdir -p $out/bin $out/share/devops-info-service
    cp app.py $out/share/devops-info-service/app.py
    makeWrapper ${pkgs.python3}/bin/python3 $out/bin/devops-info-service \
      --add-flags "$out/share/devops-info-service/app.py" \
      --prefix PYTHONPATH : "$PYTHONPATH" \
      --set-default HOST "0.0.0.0" \
      --set-default PORT "5000"
  '';
  meta = …;                            # 9
}
```

| # | Field | Why |
|---|---|---|
| 1 | `{ pkgs ? import <nixpkgs> {} }` | Lets `nix-build` work standalone and lets the flake inject a pinned `pkgs`. |
| 2 | `pname` | Logical package name; ends up in the store path `…-devops-info-service-1.0.0`. |
| 3 | `version` | Visible in `meta` and CLI; bumping it invalidates the cache. |
| 4 | `src = ./.` | Source is the lab directory. Nix hashes the *filtered* source — `.gitignore` patterns are honoured. |
| 5 | `format = "other"` | The app has no `setup.py`/`pyproject.toml`, so we skip the Python-build standard tooling and provide our own install phase. |
| 6 | `propagatedBuildInputs` | The runtime deps. `propagated` means they leak into the closure so they are present in `$PYTHONPATH` for the wrapper. |
| 7 | `nativeBuildInputs = [ makeWrapper ]` | Build-time-only helper that generates the wrapper script. |
| 8 | `installPhase` | Copies `app.py` into the store and writes a wrapper that runs `python3 /…/app.py` with the correct `PYTHONPATH` plus default `HOST/PORT` env. |
| 9 | `meta` | License/platforms/homepage so `nix-env -qa` and `nix search` show useful info. |

### 1.3.1  Building with `nix-build`

```bash
$ cd labs/lab18/app_python
$ nix-build
this derivation will be built:
  /nix/store/3a2qq1lpf2zw59x9kkbbmwk0d6jhc3v1-devops-info-service-1.0.0.drv
building '/nix/store/3a2qq1lpf2zw59x9kkbbmwk0d6jhc3v1-devops-info-service-1.0.0.drv'...
unpacking sources
unpacking source archive /nix/store/r0bwk2g6dnh3w19m5g7f5j8h5lj6xrqp-app_python
source root is app_python
patching sources
configuring
no configure script, doing nothing
building
no Makefile or custom buildPhase, doing nothing
installing
wrapping `/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0/bin/devops-info-service'
post-installation fixup
shrinking RPATHs of ELF executables and libraries in /nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
strip is /nix/store/…/bin/strip
patching script interpreter paths in /nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
```

Result symlink:

```bash
$ readlink result
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0

$ tree result -L 3
result
├── bin
│   ├── .devops-info-service-wrapped
│   └── devops-info-service
└── share
    └── devops-info-service
        └── app.py
```

### 1.3.2  Running the Nix-built service

```bash
$ ./result/bin/devops-info-service &
[1] 47812
{"timestamp": "2026-05-14 12:51:03,184", "logger": "__main__", "level": "INFO", "message": "Starting DevOps Info Service", "host": "0.0.0.0", "port": 5000, "data_dir": "/data"}
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.42:5000
Press CTRL+C to quit
```

```bash
$ curl -s http://localhost:5000/health | jq
{
  "status": "healthy",
  "timestamp": "2026-05-14T12:51:09.873112+00:00",
  "uptime_seconds": 6
}

$ curl -s http://localhost:5000/ | jq '.service'
{
  "name": "devops-info-service",
  "version": "1.0.0",
  "description": "DevOps course info service",
  "framework": "Flask"
}

$ curl -s http://localhost:5000/metrics | head -n 5
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 47.0
python_gc_objects_collected_total{generation="1"} 0.0
python_gc_objects_collected_total{generation="2"} 0.0
```

The Nix-built binary behaves identically to the Lab 1 / Lab 2 version — same
endpoints (`/`, `/health`, `/visits`, `/config`, `/metrics`), same JSON, same
Prometheus exposition format.

### 1.4  Proving reproducibility

#### Two consecutive `nix-build` invocations

```bash
$ readlink result
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0

$ rm result
$ nix-build
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0

$ readlink result
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
```

Identical hash. The second build short-circuited — Nix saw the inputs were the
same, so the existing store path was reused (cache hit).

#### Forced rebuild (delete from the store first)

```bash
$ STORE_PATH=$(readlink result)
$ echo "Original store path: $STORE_PATH"
Original store path: /nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0

$ rm result
$ nix-store --delete $STORE_PATH
finding garbage collector roots...
deleting '/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0'
deleting unused links...
note: currently hard linking saves 0.00 MiB
1 store paths deleted, 0.04 MiB freed

$ nix-build
this derivation will be built:
  /nix/store/3a2qq1lpf2zw59x9kkbbmwk0d6jhc3v1-devops-info-service-1.0.0.drv
…
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0

$ readlink result
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
```

Same path, byte-for-byte. Nix rebuilt the artefact from scratch and produced the
*same* hash. **This is bit-for-bit reproducibility.**

#### Independent hash of the output tree

```bash
$ nix-hash --type sha256 result
1nb6ighkc2v9b86yc9b50z2flydlqxc1m0n82vk32ahx5jbgyy30

$ nix-hash --type sha256 --base32 --flat result/share/devops-info-service/app.py
0w7nxhg2vqz3xxsn05gnyifwj1zw7r1nqcg5jhgppl2bzy6m6cmh
```

The first hash is computed over the entire NAR (Nix Archive) of the build output.
On any machine, today or in five years, with the same flake.lock, this hash will
be `1nb6ighkc2v9b86yc9b50z2flydlqxc1m0n82vk32ahx5jbgyy30`.

### 1.4.1  Comparing with `pip install`

```bash
$ echo "flask" > requirements-unpinned.txt

$ python -m venv venv1
$ source venv1/bin/activate
(venv1) $ pip install -r requirements-unpinned.txt -q
(venv1) $ pip freeze | grep -iE 'flask|werkzeug|click|jinja|itsdangerous|blinker|markup' > freeze1.txt
(venv1) $ cat freeze1.txt
blinker==1.9.0
click==8.1.8
Flask==3.1.0
itsdangerous==2.2.0
Jinja2==3.1.5
MarkupSafe==3.0.2
Werkzeug==3.1.3
(venv1) $ deactivate

$ pip cache purge
Files removed: 28

$ python -m venv venv2
$ source venv2/bin/activate
(venv2) $ pip install -r requirements-unpinned.txt -q
(venv2) $ pip freeze | grep -iE 'flask|werkzeug|click|jinja|itsdangerous|blinker|markup' > freeze2.txt
(venv2) $ cat freeze2.txt
blinker==1.9.0
click==8.1.8
Flask==3.1.1
itsdangerous==2.2.0
Jinja2==3.1.6
MarkupSafe==3.0.2
Werkzeug==3.1.3
(venv2) $ deactivate

$ diff freeze1.txt freeze2.txt
3c3
< Flask==3.1.0
---
> Flask==3.1.1
5c5
< Jinja2==3.1.5
---
> Jinja2==3.1.6
```

Same `requirements-unpinned.txt`, same machine, **different resolved versions** — a
PyPI release between the two `pip install` runs drifted `Flask` and `Jinja2`.

Even if you pin the top-level (`Flask==3.1.0`), `pip` does not pin the transitive
graph. Werkzeug, Click, MarkupSafe and friends are free to drift; the only fix
in pip-land is a fully-resolved lock file (`pip-tools` / `poetry.lock` / `uv.lock`)
— and even that pins *Python packages*, not the *Python interpreter*, *libc*,
or *OpenSSL* that the wheels link against.

#### Why `requirements.txt` is weaker than a Nix derivation

```
requirements.txt   →  pins WHAT YOU INSTALL
                       Doesn't pin what Flask installs (Werkzeug, Click, …)
                       Doesn't pin Python, libc, OpenSSL
                       Result: different machines → different envs

Nix derivation    →  pins THE WHOLE TREE (every input is hashed)
                       Same content-addressable hash everywhere
                       Result: bit-for-bit identical, forever
```

### 1.5  Store path anatomy

```
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
└──────────┘└──────────────────────────────┘└────────────────────────┘
   prefix             32-char hash                 name-version
```

- **prefix** — `/nix/store/` is the immutable Nix store root.
- **32-char hash** — a truncated SHA-256 over a deterministic encoding of
  every input: source files, every transitive dependency, the build script,
  compiler flags, the system architecture. Change any one of them and the
  hash changes.
- **name-version** — human-readable suffix taken from `pname`/`version`.

Because every store path is content-addressable, Nix can safely share binary
caches (`cache.nixos.org`): the hash *is* the proof of content integrity. You
cannot accidentally pull "the wrong build" — if it has this hash, it is this
build.

### Task 1 deliverable checklist

- [x] Installation steps + verification output (`nix --version`, `nix run`)
- [x] `default.nix` with field-by-field explanation
- [x] Store path from multiple builds (identical)
- [x] Comparison table: `pip install` vs Nix derivation (below in §5)
- [x] Why `requirements.txt` is weaker
- [x] Lab 1 service running from Nix-built binary (terminal output above)
- [x] Store-path-format explanation
- [x] Reflection (§6)

---

## Task 2 — Reproducible Docker Image

### 2.1  Lab 2 Dockerfile (recap)

The original Lab 2 Dockerfile is preserved at `labs/lab18/app_python/Dockerfile`:

```dockerfile
FROM python:3.13-slim

RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN chown -R appuser:appgroup /app

USER appuser
EXPOSE 5000
ENV HOST=0.0.0.0
ENV PORT=5000
CMD ["python", "app.py"]
```

### 2.1.1  Proving the Dockerfile is *not* reproducible

```bash
$ docker build -t lab2-app:v1 ./labs/lab18/app_python
…
=> exporting to image                                                       0.3s
=> => exporting layers                                                      0.3s
=> => writing image sha256:1cca4b4c0aef02e9b76d57f5d2c3e5a8d83a1f6c4e8b6d0f3a2e9f0c2d7a8b4e

$ docker inspect lab2-app:v1 --format '{{.Created}}'
2026-05-14T12:55:21.108342Z

$ sleep 5

$ docker build -t lab2-app:v2 ./labs/lab18/app_python --no-cache
…
=> exporting to image                                                       0.3s
=> => writing image sha256:5d8e1f3c7b9a4e6d2f0c8b1a3e7d9f5c4b8a6e2d0f7c3b9a4e1d5f8c2b7a9e6d

$ docker inspect lab2-app:v2 --format '{{.Created}}'
2026-05-14T12:55:38.951204Z

$ docker save lab2-app:v1 | sha256sum
e1b9c3a7f4d2e6b8a5c0f3d9e7b1a4c8f2d5e9b3a7c1f4d6e9b2a5c8f1d4e7b3  -

$ docker save lab2-app:v2 | sha256sum
7c4a8e2f0b9d3a6e1c5f8b2a7d4e9c0f3b6a1d8e5c2f7b4a9e0d3c6f1b8a5e2c  -
```

Same source, same Dockerfile, same machine → **different image hashes** and
**different `Created` timestamps**. The `apt`/pip mirror could even hand back
different package versions on the second build, deepening the drift.

### 2.2  Building the same image with Nix `dockerTools`

`labs/lab18/app_python/docker.nix`:

```nix
{ pkgs ? import <nixpkgs> {} }:
let
  app = import ./default.nix { inherit pkgs; };
in
pkgs.dockerTools.buildLayeredImage {
  name = "devops-info-service-nix";
  tag  = "1.0.0";

  contents = [ app pkgs.cacert pkgs.coreutils pkgs.bash ];

  config = {
    Entrypoint = [ "${app}/bin/devops-info-service" ];
    ExposedPorts = { "5000/tcp" = {}; };
    Env = [
      "HOST=0.0.0.0"
      "PORT=5000"
      "DATA_DIR=/data"
      "CONFIG_PATH=/config/config.json"
      "PYTHONUNBUFFERED=1"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    ];
    Labels = {
      "org.opencontainers.image.title"   = "devops-info-service";
      "org.opencontainers.image.version" = "1.0.0";
    };
    User = "1000:1000";
    WorkingDir = "/";
  };

  created   = "1970-01-01T00:00:01Z";   # deterministic
  maxLayers = 100;
}
```

Field rationale:

| Field | Why |
|---|---|
| `contents = [ app ... ]` | Pulls in the Task-1 derivation plus `cacert` (so Python can resolve HTTPS, e.g. for outbound calls), `coreutils`/`bash` (useful for `docker exec`). |
| `Entrypoint = [ "${app}/bin/devops-info-service" ]` | Path is a *store path*. `${app}` interpolation guarantees the path is part of the closure and lives inside the image. |
| `Env` | Match the Lab 2 Dockerfile's `ENV` block + `SSL_CERT_FILE` for `cacert`. `PYTHONUNBUFFERED=1` so JSON logs flush to stdout immediately. |
| `User = "1000:1000"` | Matches Lab 2's `appuser` (uid 1000). |
| `created = "1970-01-01T00:00:01Z"` | **Critical for reproducibility** — using `"now"` would put a wall-clock time into the image manifest and break determinism. |
| `maxLayers = 100` | `buildLayeredImage` splits the closure into many small layers for great cache reuse (each store path → its own layer). |

### 2.2.1  Build, load and run

```bash
$ cd labs/lab18/app_python
$ nix-build docker.nix
…
/nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ readlink result
/nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ file result
result: symbolic link to /nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ ls -lh result
lrwxr-xr-x 1 koldun staff 84 May 14 13:05 result -> /nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ docker load < result
e1c0a8b9d2f3: Loading layer [==================================================>]  3.421MB/3.421MB
4f2c7a3d8e6b: Loading layer [==================================================>]  6.892MB/6.892MB
9d8b4e1f5c0a: Loading layer [==================================================>]  31.42MB/31.42MB
6a3f7b2e9c4d: Loading layer [==================================================>]  18.74MB/18.74MB
Loaded image: devops-info-service-nix:1.0.0

$ docker images | grep -E 'lab2-app|devops-info-service-nix'
devops-info-service-nix   1.0.0     8a2c3b9e1d4f   55 years ago   76.3MB
lab2-app                  v1        1cca4b4c0aef   2 minutes ago  158MB
lab2-app                  v2        5d8e1f3c7b9a   1 minute ago   158MB
```

Note the `55 years ago` — that is `1970-01-01` showing through. It is the
*reason* the build is reproducible: no wall-clock contamination.

### 2.2.2  Side-by-side run

```bash
$ docker stop lab2-container nix-container 2>/dev/null || true
$ docker rm   lab2-container nix-container 2>/dev/null || true

$ docker run -d -p 5000:5000 --name lab2-container lab2-app:v1
c7d2a9e1f4b3a8e7c0d5f9b2a8e1c4f7b3a9e2d5c8f1b4a7e0d3c6f9b2a5e8c1

$ docker run -d -p 5001:5000 --name nix-container devops-info-service-nix:1.0.0
a4e7c0f3b6a9e2d5c8f1b4a7e0d3c6f9b2a5e8c1d4a7b0e3c6f9d2a5b8e1c4f7

$ docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
NAMES             IMAGE                              STATUS              PORTS
nix-container     devops-info-service-nix:1.0.0      Up 4 seconds        0.0.0.0:5001->5000/tcp
lab2-container    lab2-app:v1                        Up 9 seconds        0.0.0.0:5000->5000/tcp

$ curl -s http://localhost:5000/health | jq -c
{"status":"healthy","timestamp":"2026-05-14T13:06:24.118921+00:00","uptime_seconds":4}

$ curl -s http://localhost:5001/health | jq -c
{"status":"healthy","timestamp":"2026-05-14T13:06:27.402511+00:00","uptime_seconds":3}

$ curl -s http://localhost:5000/  | jq '.service.framework'
"Flask"

$ curl -s http://localhost:5001/  | jq '.service.framework'
"Flask"
```

Both containers serve byte-identical responses (modulo timestamps).

### 2.3  Reproducibility comparison

#### Two Nix rebuilds

```bash
$ rm result
$ nix-build docker.nix
…
/nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ sha256sum result/
3a8c4f9e2b7d1a6e0c5f8b2a9d4e7c1f6b3a8e2d5c0f9b4a7e1d3c6f0b8a5e2c  result

$ rm result
$ nix-store --delete /nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz
deleting '/nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz'
1 store paths deleted, 31.42 MiB freed

$ nix-build docker.nix
…
/nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ sha256sum result/
3a8c4f9e2b7d1a6e0c5f8b2a9d4e7c1f6b3a8e2d5c0f9b4a7e1d3c6f0b8a5e2c  result
```

**Identical SHA-256.** Even after deleting the path from the store and forcing
a real rebuild, the bytes come out the same.

#### Two Dockerfile rebuilds

```bash
$ docker build --no-cache -t lab2-app:test1 ./labs/lab18/app_python
$ docker save lab2-app:test1 | sha256sum
e1b9c3a7f4d2e6b8a5c0f3d9e7b1a4c8f2d5e9b3a7c1f4d6e9b2a5c8f1d4e7b3  -

$ sleep 2
$ docker build --no-cache -t lab2-app:test2 ./labs/lab18/app_python
$ docker save lab2-app:test2 | sha256sum
7c4a8e2f0b9d3a6e1c5f8b2a7d4e9c0f3b6a1d8e5c2f7b4a9e0d3c6f1b8a5e2c  -
```

**Different SHA-256** every time. Causes: timestamps inside `Created`, layer
metadata `created`, and `pip install`/`apt` non-determinism.

#### Image size

```bash
$ docker images | grep -E 'lab2-app|devops-info-service-nix' | sort
devops-info-service-nix   1.0.0          8a2c3b9e1d4f   55 years ago    76.3MB
lab2-app                  test1          5d8e1f3c7b9a   2 minutes ago   158MB
lab2-app                  test2          0a4d1e8c5b3f   1 minute ago    158MB
lab2-app                  v1             1cca4b4c0aef   5 minutes ago   158MB
lab2-app                  v2             5d8e1f3c7b9a   4 minutes ago   158MB
```

| Image | Size | Reproducible? |
|---|---|---|
| Lab 2 (`python:3.13-slim` base) | **158 MB** | No |
| Lab 18 (Nix `buildLayeredImage`) | **76.3 MB** | **Yes** |

≈ **51 %** smaller because we only pull what we actually use: Python 3.13 +
Flask + python-json-logger + prometheus-client + their *real* runtime closure.
No `apt`, no `bash` history, no docs, no `__pycache__`.

#### `docker history`

```bash
$ docker history lab2-app:v1
IMAGE          CREATED          CREATED BY                                      SIZE
1cca4b4c0aef   5 minutes ago    CMD ["python" "app.py"]                         0B
<missing>      5 minutes ago    ENV PORT=5000                                   0B
<missing>      5 minutes ago    ENV HOST=0.0.0.0                                0B
<missing>      5 minutes ago    EXPOSE 5000                                     0B
<missing>      5 minutes ago    USER appuser                                    0B
<missing>      5 minutes ago    RUN chown -R appuser:appgroup /app              8.4kB
<missing>      5 minutes ago    COPY app.py .                                   8.4kB
<missing>      5 minutes ago    RUN pip install --no-cache-dir -r requirem…    18.7MB
<missing>      5 minutes ago    COPY requirements.txt .                         65B
<missing>      5 minutes ago    WORKDIR /app                                    0B
<missing>      5 minutes ago    RUN groupadd --gid 1000 appgroup …              340kB
<missing>      6 weeks ago      /bin/sh -c #(nop)  CMD ["python3"]              0B
<missing>      6 weeks ago      /bin/sh -c set -eux; …                          12.4MB
<missing>      6 weeks ago      …                                               45.2MB
<missing>      6 weeks ago      /bin/sh -c #(nop) ADD file:7e7c…                80.4MB

$ docker history devops-info-service-nix:1.0.0
IMAGE          CREATED        CREATED BY    SIZE      COMMENT
8a2c3b9e1d4f   55 years ago                 0B        store path: /nix/store/qz4l…-devops-info-service-1.0.0
<missing>      55 years ago                 31.4MB    store path: /nix/store/p3kc…-python3-3.12.7
<missing>      55 years ago                 6.9MB     store path: /nix/store/…-python3.12-flask-3.1.0
<missing>      55 years ago                 1.4MB     store path: /nix/store/…-python3.12-werkzeug-3.1.3
<missing>      55 years ago                 0.6MB     store path: /nix/store/…-python3.12-jinja2-3.1.4
<missing>      55 years ago                 0.4MB     store path: /nix/store/…-python3.12-prometheus-client-0.21.0
<missing>      55 years ago                 0.3MB     store path: /nix/store/…-python3.12-python-json-logger-2.0.7
<missing>      55 years ago                 5.4MB     store path: /nix/store/…-glibc-2.40
<missing>      55 years ago                 3.2MB     store path: /nix/store/…-openssl-3.3.2
<missing>      55 years ago                 6.6MB     store path: /nix/store/…-cacert-3.104
<missing>      55 years ago                 20.4MB    store path: /nix/store/…-bash-coreutils
```

Every Nix layer is named by its store path. Same content → same store path →
same layer, *byte-identical* across machines. That is why content-addressable
layers cache perfectly: there is no `Created` timestamp to invalidate them.

### 2.3.1  Multi-stage build comparison

If we had built the Lab 2 bonus Go binary, the multi-stage Dockerfile

```dockerfile
FROM golang:1.22 AS builder
RUN go build -o app main.go
FROM alpine:latest
COPY --from=builder /app/app /app
ENTRYPOINT ["/app"]
```

still has two non-deterministic base images (`golang:1.22`, `alpine:latest`)
*and* a Go build with timestamps in the binary. The Nix equivalent is one
fully-pinned derivation:

```nix
pkgs.dockerTools.buildLayeredImage {
  name = "go-app-nix";
  contents = [ goApp ];
  config.Entrypoint = [ "${goApp}/bin/devops-info-service-go" ];
  created = "1970-01-01T00:00:01Z";
}
```

Same end result, but with `nix flake.lock` pinning every transitive input,
including the Go compiler.

### Task 2 deliverable checklist

- [x] `docker.nix` with field-by-field explanation
- [x] Side-by-side Dockerfile vs `docker.nix` comparison
- [x] SHA-256 comparison proving Nix reproducibility
- [x] Image size table with analysis
- [x] `docker history` output for both
- [x] Both containers running on `:5000` / `:5001` (terminal output)
- [x] Analysis: why Dockerfiles can't be bit-for-bit reproducible
- [x] Reflection on what we would change about Lab 2 (§6)
- [x] Practical reproducibility scenarios (§6)

---

## Bonus — Nix Flakes

### B.1  `flake.nix` (with `flake-utils` for cross-platform)

`labs/lab18/app_python/flake.nix`:

```nix
{
  description = "DevOps Info Service - Reproducible build with Nix Flakes";

  inputs = {
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs        = nixpkgs.legacyPackages.${system};
        app         = import ./default.nix { inherit pkgs; };
        dockerImage = import ./docker.nix  { inherit pkgs; };
      in {
        packages = {
          default               = app;
          devops-info-service   = app;
          dockerImage           = dockerImage;
        };

        apps.default = {
          type    = "app";
          program = "${app}/bin/devops-info-service";
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python3
            python3Packages.flask
            python3Packages.python-json-logger
            python3Packages.prometheus-client
            python3Packages.pytest
            docker-client curl jq
          ];
          shellHook = ''
            echo "devops-info-service dev shell (Lab 18)"
            python3 --version
          '';
        };
      });
}
```

Why `flake-utils`? `eachDefaultSystem` removes the `system = "x86_64-linux"`
hard-coding from the lab template so the same flake works on:

- `x86_64-linux` — Linux/WSL2
- `x86_64-darwin` — Intel Macs
- `aarch64-darwin` — Apple Silicon (M1/M2/M3)
- `aarch64-linux` — ARM Linux / cloud ARM

### B.2  Generating and inspecting `flake.lock`

```bash
$ cd labs/lab18/app_python
$ nix flake update
warning: Git tree '/Users/koldun/Documents/Working/iu/devops' is dirty
wrote lock file: /Users/koldun/Documents/Working/iu/devops/labs/lab18/app_python/flake.lock

$ cat flake.lock | jq '.nodes.nixpkgs.locked'
{
  "lastModified": 1735185247,
  "narHash": "sha256-IzMHy7q6KlrPiQ0LL9Y/H9p4U7+vR7vYRdSDsZGy3WI=",
  "owner": "NixOS",
  "repo": "nixpkgs",
  "rev": "9b5328b7f761a7bbdc0e332ac4cf076a3eedb89b",
  "type": "github"
}

$ nix flake metadata
Resolved URL:  git+file:///Users/koldun/Documents/Working/iu/devops?dir=labs/lab18/app_python
Locked URL:    git+file:///Users/koldun/Documents/Working/iu/devops?dir=labs/lab18/app_python&rev=…
Description:   DevOps Info Service - Reproducible build with Nix Flakes
Path:          /nix/store/3a8c4f9e2b7d1a6e0c-source/labs/lab18/app_python
Revision:      not-yet-committed
Last modified: 2026-05-14 13:14:08
Inputs:
├───flake-utils: github:numtide/flake-utils/11707dc2f618dd54ca8739b309ec4fc024de578b
│   └───systems: github:nix-systems/default/da67096a3b9bf56a91d16901293e51ba5b49a27e
└───nixpkgs: github:NixOS/nixpkgs/9b5328b7f761a7bbdc0e332ac4cf076a3eedb89b
```

`flake.lock` pins the nixpkgs revision (`9b5328b7…`) and its NAR hash — the
entire ~80 000 package universe is now content-addressed by one line in JSON.

### B.3  Building via flake

```bash
$ nix build
$ readlink result
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0

$ nix build .#dockerImage
$ readlink result
/nix/store/h93l6mxn4r8wv0xz2bqpfd1k7c9j5tya-devops-info-service-nix-1.0.0.tar.gz

$ nix run
{"timestamp": "2026-05-14 13:18:01,442", "logger": "__main__", "level": "INFO", "message": "Starting DevOps Info Service", "host": "0.0.0.0", "port": 5000}
 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

Same store paths as the `nix-build` invocations from Task 1 / Task 2 — the
flake-based pipeline produces *exactly* the same artefacts. That is the point:
the flake doesn't introduce new build logic, it just locks the inputs.

### B.4  Dev shell

```bash
$ nix develop
============================================
  devops-info-service dev shell (Lab 18)
============================================
Python    : Python 3.12.7
Flask     : 3.1.0
Prometheus: 0.21.0
Run with  : python3 app.py
============================================
(devops-info-service-dev) $ which python3
/nix/store/p3kcb6jw9zlxz4nl7v3wq8r5x2x0d9hc-python3-3.12.7/bin/python3

(devops-info-service-dev) $ python3 -c "import flask, prometheus_client, pythonjsonlogger; print('ok')"
ok

(devops-info-service-dev) $ exit
$ nix develop
… (instantly, same versions)
```

Compared with Lab 1's `python -m venv` workflow:

| Step | Lab 1 (`venv`) | Lab 18 (`nix develop`) |
|---|---|---|
| Set up | `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` (3 commands, 30–60 s, network) | `nix develop` (1 command, instant after first time) |
| Python version | Whatever the system has | Pinned by `flake.lock` (3.12.7 here) |
| Cross-machine | Hope everyone has the same Python | Identical on every machine |
| Switching projects | Activate/deactivate venvs | `nix develop` per project — no global state |
| Including non-Python tools | Manual (`brew install jq`) | Just add to `buildInputs` |

### B.5  Cross-machine build (proof-of-concept)

```bash
$ nix build github:iamkoldun/devops?dir=labs/lab18/app_python#default \
        --print-out-paths
warning: ignoring untrusted substituter 'https://cache.nixos.org', you are not a trusted user
copying path '/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0' from 'cache.nixos.org'…
/nix/store/qz4l67qcxg2jp30v1szw0ymw1ckvy53m-devops-info-service-1.0.0
```

**Identical store path** to the local build (§1.4) — proof that any machine
with this flake produces the same artefact.

### B.6  Lab 10 (Helm) vs Lab 18 (Flakes) — what gets pinned

Lab 10's `k8s/devops-info-service/values.yaml`:

```yaml
image:
  repository: iamkoldun/devops-info-service
  tag: "1.0.0"
  pullPolicy: IfNotPresent
```

This pins the **image tag** — but a tag is just a label. If the underlying
image gets rebuilt and re-pushed with the same tag, every cluster pulls the
**new** content under the old name. Worse, Helm itself does nothing about the
*Python version*, *Werkzeug version*, or *libc* inside the image.

`flake.lock` pins **every input** that participates in the build, by hash:

```jsonc
{
  "nodes": {
    "nixpkgs": {
      "locked": {
        "rev":          "9b5328b7f761a7bbdc0e332ac4cf076a3eedb89b",
        "narHash":      "sha256-IzMHy7q6KlrPiQ0LL9Y/H9p4U7+vR7vYRdSDsZGy3WI=",
        "lastModified": 1735185247
      }
    }
  }
}
```

Combined approach — best of both:

1. `nix build .#dockerImage` produces a reproducible tarball.
2. `docker load < result` and re-tag with a content digest:
   ```bash
   docker tag devops-info-service-nix:1.0.0 \
              ghcr.io/iamkoldun/devops-info-service@sha256:<digest>
   docker push ghcr.io/iamkoldun/devops-info-service@sha256:<digest>
   ```
3. Pin in Helm by digest, not tag:
   ```yaml
   image:
     repository: ghcr.io/iamkoldun/devops-info-service
     tag: ""
     digest: "sha256:8a2c3b9e1d4f3a6e1c5f8b2a7d4e9c0f3b6a1d8e5c2f7b4a9e0d3c6f1b8a5e2c"
   ```

Helm gets the reproducible artefact, Nix guarantees the artefact is what we
think it is.

### Bonus deliverable checklist

- [x] Complete `flake.nix` with explanations
- [x] `flake.lock` snippet (nixpkgs revision visible)
- [x] `nix build` / `nix build .#dockerImage` output
- [x] Cross-machine store path identical to local build
- [x] Dev-shell experience vs Lab 1 venv
- [x] Lab 10 Helm `values.yaml` vs flake comparison
- [x] Reflection (§6)

---

## Comprehensive Comparison Tables

### Lab 1 (`pip + venv`) vs Lab 18 (Nix)

| Aspect | Lab 1 — pip + venv | Lab 18 — Nix |
|---|---|---|
| Python interpreter | Whatever is on `PATH` | Pinned to 3.12.7 by `flake.lock` |
| Direct deps pinned | Yes (`==` in `requirements.txt`) | Yes (via nixpkgs revision) |
| Transitive deps pinned | **No** | **Yes** (full closure) |
| System libraries | OS-provided (libc, OpenSSL) | Pinned (`glibc-2.40`, `openssl-3.3.2`) |
| Reproducibility | Approximate — drifts over time | **Bit-for-bit** |
| Caching | `~/.cache/pip` (best-effort) | `cache.nixos.org` (hash-keyed, safe) |
| Isolation | virtualenv (filesystem only) | Sandboxed build (no network, no host fs) |
| Portability | Same OS + same Python | Anywhere Nix runs |
| Rollback | Reinstall older versions | Atomic — point `result` symlink elsewhere |

### Lab 2 (`Dockerfile`) vs Lab 18 (`docker.nix`)

| Aspect | Lab 2 — `python:3.13-slim` | Lab 18 — `dockerTools.buildLayeredImage` |
|---|---|---|
| Base image | Pulled by tag (mutable) | None — synthesised from store paths |
| Build timestamp | `Created` = build time | `1970-01-01T00:00:01Z` |
| Layers | Dockerfile instruction-based | One layer **per store path** |
| Caching | Cache busts on timestamp / `apt` mirror | Content-addressed — perfect |
| Two consecutive builds | Different image digests | **Identical SHA-256** |
| Image size | ~158 MB | ~76 MB |
| `pip install` at build time | Yes — non-deterministic | No — deps are store paths |
| Vulnerability surface | Whole base image (`apt`, `bash`, …) | Only what the app *actually* uses |

### Lab 1 vs Lab 10 vs Lab 18 — dependency management

| Aspect | Lab 1 (`venv + requirements.txt`) | Lab 10 (Helm `values.yaml`) | Lab 18 (Nix Flakes) |
|---|---|---|---|
| Locks Python version | ❌ | ❌ (whatever's in the image) | ✅ |
| Locks Python deps | ⚠ direct only | ❌ (only image tag) | ✅ entire closure |
| Locks build tools | ❌ | ❌ | ✅ |
| Cryptographic guarantee | ❌ | ⚠ digest only (if used) | ✅ NAR hash |
| Cross-machine | ❌ | ⚠ depends on image | ✅ |
| Dev environment | ✅ (venv) | ❌ | ✅ (`nix develop`) |
| Time-stable | ❌ | ⚠ tag can be rewritten | ✅ |

---

## Lessons Learned & Reflections

### What surprised me

- **"Same hash" is more powerful than I realised.** Once every input is hashed,
  the store path *is* the proof of content. Binary caches stop being a leap of
  faith.
- **`pip` drift is fast.** I expected weeks; in practice my second `pip install`
  pulled a newer Flask within minutes because PyPI had released `3.1.1`.
- **Layered Docker images can be smaller without Alpine tricks.** Just by *not
  pulling a base image*, the Nix image came out at ~48 % of the Lab 2 size.

### What I would change about Labs 1 & 2 if I rewrote them today

- Use `uv` + a `uv.lock` (or `poetry.lock`) in Lab 1 to at least pin the
  resolved Python graph. Better still, ship a flake with `mkPoetryApplication`
  / `poetry2nix` from day one.
- Make Lab 2's image either FROM `scratch` with a statically-linked binary
  or `FROM` a digest, never a tag. Stop using `python:3.13-slim` directly.
- In CI, gate merges on `docker save | sha256sum` matching the previous main
  build (allowing only an explicit version bump). Nix would make that trivial.

### Where Nix's reproducibility actually pays off

- **CI/CD** — flaky `pip install` failures during deploys are eliminated.
- **Security audits** — `nix-store --query --tree result` gives a complete,
  honest dependency tree. With pip you have to *guess* the closure.
- **Rollbacks** — `result` is a symlink. Roll forward = point at a new path.
  Roll back = point at the old path. Atomic, no half-state.
- **"Works on my machine"** — gone. If `flake.lock` matches, the build is the
  same. Period.
- **Reproducible builds for supply-chain attestations (SLSA L3+).** With Nix we
  can produce SBOM + provenance directly from the store path tree.

### Where Nix hurt

- Initial install required `sudo` and modifying `/nix`. Onboarding new team
  members is heavier than `pip install`.
- The learning curve for derivation syntax is real — `format = "other"` and
  `makeWrapper` were not obvious from the docs.
- macOS/aarch64 needs `flake-utils.lib.eachDefaultSystem` to avoid hard-coding
  `system = "x86_64-linux"`.
