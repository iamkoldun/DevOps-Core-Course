# NIX.md — Reproducible Builds (Lab 18)

This document describes the Nix-based reproducible build setup added in
[Lab 18](labs/lab18.md) for the **DevOps Info Service**. It complements the
Lab 1 (`app_python/`) and Lab 2 (`app_python/Dockerfile`) artefacts by making
their outputs *bit-for-bit reproducible*.

All Nix expressions live under [`labs/lab18/app_python/`](labs/lab18/app_python).

## Files

| File | Purpose |
|---|---|
| `default.nix` | Builds the Flask app as a Nix derivation (Lab 1 replacement). |
| `docker.nix`  | Wraps the derivation as a reproducible OCI image (Lab 2 replacement). |
| `flake.nix`   | Modern flake — exposes `default`, `dockerImage`, `apps.default`, `devShells.default`. |
| `flake.lock`  | Pins exact `nixpkgs` and `flake-utils` revisions. |

## Quick start

```bash
cd labs/lab18/app_python

# Build the Python app (Lab 1 equivalent)
nix-build              # or:  nix build

# Run it
./result/bin/devops-info-service

# Build a reproducible Docker image (Lab 2 equivalent)
nix-build docker.nix   # or:  nix build .#dockerImage
docker load < result
docker run -d -p 5001:5000 --name nix-container devops-info-service-nix:1.0.0

# Enter a fully-pinned dev shell (Lab 1 venv replacement)
nix develop
```

## Reproducibility guarantee

`nix-build` and `nix build` both honour `flake.lock`. The same lock file on any
machine produces the same `/nix/store/<hash>-…` path. The output tarball from
`docker.nix` is byte-identical across machines and time — verifiable with
`sha256sum result`.

## Related labs

- [Lab 1](labs/lab01.md) — original Flask app and `requirements.txt`.
- [Lab 2](labs/lab02.md) — original `Dockerfile`.
- [Lab 10](labs/lab10.md) — Helm `values.yaml`; see the flake↔Helm comparison
  in [`labs/submission18.md`](labs/submission18.md).
- [Lab 18](labs/lab18.md) — full lab brief.
- [`labs/submission18.md`](labs/submission18.md) — full submission with command
  outputs, hash comparisons, and reflections.
