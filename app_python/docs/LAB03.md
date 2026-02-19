# Lab 3: Continuous Integration (CI/CD)

## 1. Overview

**Testing framework:** pytest. Chosen for simple syntax, strong fixture support, and wide adoption in Python projects. Dev dependencies (pytest, pytest-cov, ruff) are in `requirements-dev.txt`.

**Endpoints covered by tests:** `GET /` (JSON structure, service/system/runtime/request/endpoints fields, types), `GET /health` (status, timestamp, uptime_seconds), and error case `GET /nonexistent` (404 with error message).

**CI trigger configuration:** Workflow runs on push and pull_request to branches `master`, `main`, and `lab03`. Path filter: only when files under `app_python/` or `.github/workflows/python-ci.yml` change.

**Versioning strategy:** CalVer (calendar versioning) in format `YYYY.MM` (e.g. `2025.02`). Chosen for a continuously deployed service where release cadence is time-based and explicit breaking-change versioning is not required.

---

## 2. Workflow Evidence

- **Successful workflow run:** GitHub Actions → [Actions tab](https://github.com/iamkoldun/DevOps-Core-Course/actions) → workflow "Python CI".
- **Tests passing locally:** Run from `app_python/`: `pip install -r requirements-dev.txt && pytest tests/ -v`.
- **Docker image on Docker Hub:** `https://hub.docker.com/r/iamkoldun/devops-info-service` (tags: `latest`, `YYYY.MM`).
- **Status badge:** In `app_python/README.md`; badge reflects current workflow status.

---

## 3. Best Practices Implemented

- **Concurrency cancel-in-progress:** One run per branch at a time; newer runs cancel previous ones to save resources.
- **Job dependency (build needs test):** Docker build/push runs only after tests pass, so failing tests block publishing.
- **Conditional Docker push:** Build job runs only on push to main/master/lab03, not on pull_request.
- **Caching:** `actions/setup-python` with `cache: 'pip'` and `cache-dependency-path` for `requirements*.txt` to speed up dependency installs. On cache hit, dependency install is typically 30–60 seconds faster.
- **Snyk:** Python Snyk action runs after install; `--severity-threshold=high`; `continue-on-error: true` so the build does not fail on existing advisories while results are visible in logs.

---

## 4. Key Decisions

- **Versioning strategy:** CalVer (`YYYY.MM`) was chosen because the app is a service with time-based releases; no need for SemVer breaking-change signalling.
- **Docker tags:** CI produces `username/devops-info-service:YYYY.MM` and `username/devops-info-service:latest`.
- **Workflow triggers:** Push and pull_request on main/master/lab03 with path filters so only Python app (and its workflow file) changes trigger this workflow.
- **Test coverage:** Endpoints `/` and `/health` and 404 are covered; coverage threshold in CI is 70% (`--cov-fail-under=70`).

---

## 5. Bonus: Multi-App CI and Coverage

- **Go CI:** `.github/workflows/go-ci.yml` runs on changes under `app_go/` and the workflow file; runs golangci-lint, `go test`, then Docker build/push with the same CalVer tagging.
- **Path filters:** Python workflow runs only for `app_python/**` and `python-ci.yml`; Go workflow only for `app_go/**` and `go-ci.yml`, so each app’s CI runs independently.
- **Coverage:** pytest-cov generates `coverage.xml`; Codecov upload step runs in CI (optional token). Coverage badge and threshold (70%) are configured; current coverage reflects endpoint tests above.
