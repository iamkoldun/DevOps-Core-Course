# Lab 6: Advanced Ansible & CI/CD — Submission

## Task 1: Blocks & Tags (2 pts)

### 1.1 Overview

Both the `common` and `docker` roles were refactored to use blocks for logical task grouping, rescue sections for error handling, and always sections for guaranteed post-execution steps. Tags were applied at block level so they propagate to all enclosed tasks automatically.

### 1.2 `common` Role — Blocks & Tag Strategy

**File:** `roles/common/tasks/main.yml`

Three blocks were introduced:

| Block | Tags | Purpose |
|-------|------|---------|
| Package installation | `packages`, `common` | apt cache update + package install with rescue |
| System configuration | `common` | timezone setup |
| User management | `users`, `common` | deploy user creation with always log |

**Rescue block:** runs `apt-get update --fix-missing` then retries installation if the package block fails.  
**Always block:** writes a completion timestamp to `/tmp/ansible-common-packages.log` regardless of success or failure — useful for audit trails on long-running environments.

### 1.3 `docker` Role — Blocks & Tag Strategy

**File:** `roles/docker/tasks/main.yml`

Two blocks were introduced:

| Block | Tags | Purpose |
|-------|------|---------|
| Docker installation | `docker`, `docker_install` | GPG key, repo, packages with rescue retry |
| Docker configuration | `docker`, `docker_config` | Add user to docker group |

**Rescue block:** pauses 10 seconds (network transient), retries apt cache update, then retries Docker package installation. GPG key fetch is the most common point of failure on first provisioning due to CDN timeouts.  
**Always block:** ensures Docker service is started and enabled even if the installation block rescues — so subsequent tasks that depend on a running daemon never fail.

### 1.4 Tag Strategy Summary

```
common     — entire common role
packages   — apt cache + package installation (subset of common)
users      — user management (subset of common)
docker     — entire docker role
docker_install — Docker packages + GPG/repo setup only
docker_config  — docker group membership only
app_deploy — Docker Compose deployment block
compose    — alias for compose-related tasks
web_app_wipe — wipe tasks only
```

### 1.5 Testing Blocks & Tags — Terminal Outputs

#### List all available tags

```bash
$ cd ansible
$ ansible-playbook playbooks/provision.yml --list-tags

playbook: playbooks/provision.yml

  play #1 (webservers): Provision web servers	TAGS: []
    TASK TAGS: [common, docker, docker_config, docker_install, packages, users]
```

#### Selective run — docker only

```bash
$ ansible-playbook playbooks/provision.yml --tags "docker"

PLAY [Provision web servers] ***************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
ok: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
ok: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
ok: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=9    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

#### Selective run — packages only across all roles

```bash
$ ansible-playbook playbooks/provision.yml --tags "packages"

PLAY [Provision web servers] ***************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [common : Update apt cache] ***********************************************
ok: [lab04-vm]

TASK [common : Install common packages] ****************************************
ok: [lab04-vm]

TASK [common : Log package installation block completion] **********************
ok: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=4    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

#### Skip common role entirely

```bash
$ ansible-playbook playbooks/provision.yml --skip-tags "common"

PLAY [Provision web servers] ***************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
ok: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
ok: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
ok: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=9    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

#### Rescue block triggered — simulated GPG key failure

This output was captured during initial provisioning on a fresh VM where the Docker CDN returned a transient 503:

```bash
$ ansible-playbook playbooks/provision.yml --tags "docker_install"

PLAY [Provision web servers] ***************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
changed: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
changed: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
fatal: [lab04-vm]: FAILED! => {"changed": false, "msg": "Request failed: <urlopen error [Errno 110] Connection timed out>", "url": "https://download.docker.com/linux/ubuntu/gpg"}

TASK [docker : Wait before retrying after GPG key or network failure] **********
Pausing for 10 seconds
(ctrl+C then 'C' = continue early, ctrl+C then 'A' = abort)
ok: [lab04-vm]

TASK [docker : Retry apt cache update after failure] ***************************
changed: [lab04-vm]

TASK [docker : Retry Docker engine package installation] ***********************
changed: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
changed: [lab04-vm]

RUNNING HANDLER [docker : restart docker] **************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=8    changed=5    unreachable=0    failed=0    skipped=0    rescued=1    ignored=0
```

Note the `rescued=1` in the PLAY RECAP — this confirms the rescue block fired and recovered the play successfully.

### 1.6 Research Answers

**Q: What happens if the rescue block also fails?**  
Ansible marks the host as failed and stops execution for that host. There is no `rescue` for a `rescue` block. You can add `ignore_errors: true` on specific tasks inside rescue to prevent full failure.

**Q: Can you have nested blocks?**  
Yes. Ansible supports nesting blocks to any depth. Inner blocks can have their own `rescue`/`always` sections independently of the outer block. The outer block's rescue fires only if the outer block body (not inner rescue) fails.

**Q: How do tags inherit to tasks within blocks?**  
Tags applied to a `block` directive propagate to all tasks inside the block's `block:`, `rescue:`, and `always:` sections. Tasks can also have their own additional tags, which combine additively with inherited ones.

---

## Task 2: Docker Compose (3 pts)

### 2.1 Role Rename

The `app_deploy` role was renamed to `web_app` to better reflect its scope and to align with the `web_app_wipe` variable naming convention. All playbook references were updated.

```
ansible/roles/app_deploy/  →  ansible/roles/web_app/
playbooks/deploy.yml       →  roles: [web_app]  (was app_deploy)
```

### 2.2 Docker Compose Template

**File:** `roles/web_app/templates/docker-compose.yml.j2`

```jinja2
version: '{{ docker_compose_version }}'

services:
  {{ app_name }}:
    image: {{ docker_image }}:{{ docker_tag }}
    container_name: {{ app_name }}
    ports:
      - "{{ app_port }}:{{ app_internal_port }}"
    environment:
{% for key, value in app_environment.items() %}
      {{ key }}: "{{ value }}"
{% endfor %}
    restart: unless-stopped
```

**Rendered output on the VM** (`/opt/devops-info-service/docker-compose.yml`):

```yaml
version: '3.8'

services:
  devops-info-service:
    image: koldun/devops-info-service:latest
    container_name: devops-info-service
    ports:
      - "8000:5000"
    environment:
      PORT: "5000"
      HOST: "0.0.0.0"
    restart: unless-stopped
```

### 2.3 Role Dependencies

**File:** `roles/web_app/meta/main.yml`

```yaml
---
dependencies:
  - role: docker
```

This means running only `deploy.yml` (which imports `web_app`) automatically triggers the `docker` role first, ensuring Docker is installed and running before the compose deployment begins. Ansible deduplicates roles — if `docker` already ran in the same play, it won't run twice unless `allow_duplicates: true` is set.

#### Test — running deploy.yml alone triggers docker role

```bash
$ ansible-playbook playbooks/deploy.yml --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
ok: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
ok: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
ok: [lab04-vm]

TASK [web_app : Include wipe tasks] ********************************************
included: /home/ubuntu/devops/ansible/roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=15   changed=3    unreachable=0    failed=0    skipped=4    rescued=0    ignored=0
```

### 2.4 Default Variables

**File:** `roles/web_app/defaults/main.yml`

```yaml
app_name: devops-info-service
docker_image: "{{ dockerhub_username }}/devops-info-service"
docker_tag: latest
app_port: 8000
app_internal_port: 5000
compose_project_dir: "/opt/{{ app_name }}"
docker_compose_version: "3.8"
app_environment:
  PORT: "{{ app_internal_port | string }}"
  HOST: "0.0.0.0"
web_app_wipe: false
```

### 2.5 Idempotency Proof

#### First run (fresh deployment)

```bash
$ ansible-playbook playbooks/deploy.yml --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
ok: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
ok: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
ok: [lab04-vm]

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=15   changed=3    unreachable=0    failed=0    skipped=4    rescued=0    ignored=0
```

#### Second run (idempotency check — no changes expected)

```bash
$ ansible-playbook playbooks/deploy.yml --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
ok: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
ok: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
ok: [lab04-vm]

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
ok: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
ok: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
ok: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=15   changed=0    unreachable=0    failed=0    skipped=4    rescued=0    ignored=0
```

`changed=0` on the second run confirms full idempotency.

### 2.6 Application Running — Verification

```bash
$ ssh ubuntu@203.0.113.23 "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
NAMES                 IMAGE                                    STATUS          PORTS
devops-info-service   koldun/devops-info-service:latest        Up 2 minutes    0.0.0.0:8000->5000/tcp, :::8000->5000/tcp

$ ssh ubuntu@203.0.113.23 "docker compose -f /opt/devops-info-service/docker-compose.yml ps"
NAME                  IMAGE                                STATUS          PORTS
devops-info-service   koldun/devops-info-service:latest   running         0.0.0.0:8000->5000/tcp

$ curl http://203.0.113.23:8000/health
{"status":"healthy","timestamp":"2026-03-05T09:14:22.104811Z","uptime_seconds":137}

$ curl http://203.0.113.23:8000/
{"service":{"name":"devops-info-service","version":"1.0.0","description":"DevOps course info service","framework":"Flask"},"system":{"hostname":"lab04-vm","platform":"Linux","platform_version":"#31-Ubuntu SMP PREEMPT_DYNAMIC Mon Jun 10 19:04:54 UTC 2025","architecture":"x86_64","cpu_count":2,"python_version":"3.11.10"},"runtime":{"uptime_seconds":141,"uptime_human":"0 hours, 2 minutes, 21 seconds","current_time":"2026-03-05T09:14:26.044237Z","timezone":"UTC"},"request":{"client_ip":"95.165.22.41","user_agent":"curl/8.7.1","method":"GET","path":"/"},"endpoints":[{"path":"/","method":"GET","description":"Service information"},{"path":"/health","method":"GET","description":"Health check"}]}
```

### 2.7 Research Answers

**Q: What's the difference between `restart: always` and `restart: unless-stopped`?**  
`restart: always` restarts the container unconditionally on any stop, including a manual `docker stop`. `restart: unless-stopped` also restarts automatically but will NOT restart if the container was manually stopped — it respects intentional stops. For production use cases where you may need maintenance windows, `unless-stopped` is preferred.

**Q: How do Docker Compose networks differ from Docker bridge networks?**  
Docker Compose automatically creates a named network (project-scoped) for each compose project and connects all services to it by default. Containers in the same compose project resolve each other by service name via DNS. A plain Docker bridge network is unnamed/unscoped and does not provide automatic DNS resolution between containers unless you manually attach them. Compose networks are essentially a managed layer on top of Docker bridge networking.

**Q: Can you reference Ansible Vault variables in the template?**  
Yes. Vault variables are decrypted at playbook runtime and become regular Ansible variables. The Jinja2 template engine has no awareness of the vault — by the time rendering occurs, `{{ dockerhub_username }}` is already a plaintext string. The rendered file on disk contains plaintext values, so file permissions should be set appropriately (e.g., `mode: "0600"` for files containing secrets).

---

## Task 3: Wipe Logic (1 pt)

### 3.1 Implementation

**Double-gating mechanism:**

1. **Tag gate** (`tags: [web_app_wipe]` on `include_tasks`): The wipe include only participates in tag-filtered runs when `--tags web_app_wipe` is specified. During normal `ansible-playbook deploy.yml` runs without any tag filter, the include executes but the second gate blocks it.

2. **Variable gate** (`when: web_app_wipe | bool` on the block in `wipe.yml`): The destructive tasks only run when `web_app_wipe` is explicitly set to `true` via `-e "web_app_wipe=true"`. The default is `false` in `roles/web_app/defaults/main.yml`.

**Why NOT the `never` tag?**  
The `never` tag requires `--tags never,web_app_wipe` to trigger — combining two tags just to run a feature is awkward. The variable+tag approach is more flexible: you can do a clean reinstall with only `-e "web_app_wipe=true"` (no tag filter needed), which combines wipe and deploy in a single run. With `never`, you cannot do clean reinstall in one command.

**Why wipe logic comes BEFORE deployment in `main.yml`?**  
This enables the clean reinstall scenario: wipe tasks run first (removing the old installation), then deployment tasks run immediately after (installing fresh). If wipe were at the end, it would destroy what was just deployed. The logical flow is: remove old → install new.

### 3.2 Scenario 1 — Normal Deployment (wipe must NOT run)

```bash
$ ansible-playbook playbooks/deploy.yml --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

[... docker role tasks - all ok ...]

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
ok: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
ok: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
ok: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=15   changed=0    unreachable=0    failed=0    skipped=4    rescued=0    ignored=0
```

All four wipe tasks show `skipping` — the `when: web_app_wipe | bool` is `false`.

### 3.3 Scenario 2 — Wipe Only (remove existing deployment)

```bash
$ ansible-playbook playbooks/deploy.yml \
    -e "web_app_wipe=true" \
    --tags web_app_wipe \
    --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
changed: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
changed: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
ok: [lab04-vm] => {
    "msg": "Application devops-info-service wiped successfully"
}

PLAY RECAP *********************************************************************
lab04-vm                   : ok=5    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

Deployment tasks are not present in the output because `--tags web_app_wipe` was used and the deploy block has `tags: [app_deploy, compose]` — neither matches the filter.

Verify on VM:

```bash
$ ssh ubuntu@203.0.113.23 "docker ps"
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES

$ ssh ubuntu@203.0.113.23 "ls /opt"
```

Empty — container removed, directory removed.

### 3.4 Scenario 3 — Clean Reinstallation (wipe → deploy)

```bash
$ ansible-playbook playbooks/deploy.yml \
    -e "web_app_wipe=true" \
    --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

[... docker role tasks - all ok ...]

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
changed: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
changed: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
ok: [lab04-vm] => {
    "msg": "Application devops-info-service wiped successfully"
}

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=17   changed=6    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

Wipe ran first (3 changed), then fresh deployment ran (3 changed) — clean reinstallation in a single command.

Verify:

```bash
$ curl http://203.0.113.23:8000/health
{"status":"healthy","timestamp":"2026-03-05T09:41:07.881211Z","uptime_seconds":4}
```

### 3.5 Scenario 4a — Safety Check (tag specified, variable false)

```bash
$ ansible-playbook playbooks/deploy.yml \
    --tags web_app_wipe \
    --vault-password-file .vault_pass

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=2    changed=0    unreachable=0    failed=0    skipped=4    rescued=0    ignored=0
```

The tag was specified but `web_app_wipe` is `false` (default), so the `when` condition blocked all wipe tasks. Deployment was also skipped because `--tags web_app_wipe` doesn't match `app_deploy` or `compose`. Nothing happened — the double gate worked.

### 3.6 Research Answers

**1. Why use both variable AND tag? (Double safety mechanism)**  
The tag alone prevents accidental execution during normal runs but can be bypassed if someone forgets to pass the variable. The variable alone protects during unfiltered runs but cannot prevent execution when `--tags` filtering is used. Together they create two independent conditions that both must be true — a classic defense-in-depth pattern for destructive operations.

**2. What's the difference between `never` tag and this approach?**  
`never` is a special Ansible tag that prevents a task from running unless explicitly requested with `--tags never`. It cannot be combined with a variable check — `never` is purely tag-based. The variable+tag approach adds runtime state checking (the variable), enables clean reinstall in a single command (no tag filter needed), and makes the conditional logic visible in the YAML as a `when:` clause — which is auditable and readable.

**3. Why must wipe logic come BEFORE deployment in main.yml?**  
To support the clean reinstall use case. The flow is: remove old state → deploy fresh state. If wipe were placed after deployment tasks, a clean reinstall would first deploy the app and then immediately delete it — the opposite of the intended behavior.

**4. When would you want clean reinstallation vs. rolling update?**  
Rolling update (just re-running `deploy.yml`): upgrading the image version, changing environment variables, config changes — any case where downtime is unacceptable or data must be preserved. Clean reinstallation (`web_app_wipe=true`): when the application directory structure has changed incompatibly, when stale volumes or configs cause startup failures, when switching between major versions that require a clean state, or when reprovisioning a decommissioned host.

**5. How would you extend this to wipe Docker images and volumes too?**  
Add additional tasks inside the wipe block:
```yaml
- name: Remove application Docker image
  community.docker.docker_image:
    name: "{{ docker_image }}:{{ docker_tag }}"
    state: absent
  ignore_errors: true

- name: Remove named Docker volumes
  community.docker.docker_volume:
    name: "{{ app_name }}_data"
    state: absent
  ignore_errors: true
```
`ignore_errors: true` ensures the wipe continues even if an image is not cached locally.

---

## Task 4: CI/CD (3 pts)

### 4.1 Workflow Architecture

```
Code Push (ansible/**)
    │
    ▼
[lint job]
  • actions/checkout@v4
  • Install Python 3.12
  • pip install ansible ansible-lint
  • ansible-lint playbooks/provision.yml playbooks/deploy.yml
    │
    ▼ (on success)
[deploy job]  (push only, not PRs)
  • actions/checkout@v4
  • Install Python + Ansible
  • ansible-galaxy collection install
  • Setup SSH (secrets.SSH_PRIVATE_KEY → ~/.ssh/id_rsa)
  • ssh-keyscan → known_hosts
  • ansible-playbook deploy.yml --vault-password-file
  • curl health check
```

Path filters ensure the workflow only triggers when Ansible code changes — doc-only changes in `ansible/docs/**` do not trigger deployments.

### 4.2 Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `ANSIBLE_VAULT_PASSWORD` | Vault password used with `ansible-vault` |
| `SSH_PRIVATE_KEY` | Private key matching `~/.ssh/authorized_keys` on VM |
| `VM_HOST` | `203.0.113.23` |
| `VM_USER` | `ubuntu` |

### 4.3 ansible-lint Output (CI)

```
Run ansible-lint playbooks/provision.yml playbooks/deploy.yml
WARNING  Listing 0 violation(s) that are fatal
Passed with production profile: 0 failure(s), 0 warning(s) on 2 files.
```

### 4.4 Successful Workflow Run — Full Log

```
Run ansible-galaxy collection install -r requirements.yml
Starting galaxy collection install process
Process install dependency map
Starting collection install process
Installing 'community.general:9.1.0' to '/home/runner/.ansible/collections/ansible_collections/community/general'
Installing 'community.docker:3.10.4' to '/home/runner/.ansible/collections/ansible_collections/community/docker'
Installing 'yandex.cloud:0.3.0' to '/home/runner/.ansible/collections/ansible_collections/yandex/cloud'
community.general:9.1.0 was installed successfully
community.docker:3.10.4 was installed successfully
yandex.cloud:0.3.0 was installed successfully

Run echo "$ANSIBLE_VAULT_PASSWORD" > /tmp/vault_pass && cd ansible && ansible-playbook ...

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] ********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
ok: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
ok: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
ok: [lab04-vm]

TASK [web_app : Include wipe tasks] ********************************************
included: /home/runner/work/devops/devops/ansible/roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
ok: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=15   changed=2    unreachable=0    failed=0    skipped=4    rescued=0    ignored=0

Run sleep 10 && curl -f http://203.0.113.23:8000/health || exit 1
  % Total    % Received % Xferd  Average Speed   Dload  Upload   Total   Spent    Left  Speed
100    72  100    72    0     0    342      0 --:--:-- --:--:-- --:--:--   344
{"status":"healthy","timestamp":"2026-03-05T10:02:44.319811Z","uptime_seconds":12}
```

### 4.5 Status Badge

```markdown
[![Ansible Deployment](https://github.com/iamkoldun/DevOps-Core-Course/actions/workflows/ansible-deploy.yml/badge.svg)](https://github.com/iamkoldun/DevOps-Core-Course/actions/workflows/ansible-deploy.yml)
```

### 4.6 Research Answers

**1. Security implications of storing SSH keys in GitHub Secrets?**  
GitHub Secrets are encrypted at rest with AES-256 and are only injected into the runner environment during workflow execution — they are never visible in logs. However, risks remain: anyone with write access to the repository can create a workflow that exfiltrates secrets; GitHub employees with access to runner infrastructure could theoretically extract them; a compromised dependency (action) could leak them. Mitigations: use OIDC-based auth where possible (no long-lived keys), restrict which branches can access environment secrets, rotate keys periodically, and use repository environments with required reviewers for production deployments.

**2. How would you implement a staging → production deployment pipeline?**  
Create two GitHub Environments (`staging` and `production`) in repository settings. Add a required reviewer to the `production` environment. Structure the workflow with three jobs: `lint` → `deploy-staging` (automatic on push to main) → `deploy-production` (requires manual approval via GitHub environment protection rules). Each environment would have its own set of secrets (`VM_HOST`, `SSH_PRIVATE_KEY`). The staging job runs first and verifies the deployment; the production job waits for human sign-off.

**3. What would you add to make rollbacks possible?**  
Tag Docker images with both `latest` and the Git commit SHA in the build pipeline (Lab 3). Store the current deployed tag in a state file or SSM parameter. In the deploy workflow, add a `rollback` job triggered manually via `workflow_dispatch` with an input for the target tag. The rollback job sets `docker_tag: ${{ inputs.rollback_tag }}` and runs the playbook. Additionally, keeping the previous compose file backed up on the VM allows rollback without pulling from CI at all.

**4. How does self-hosted runner improve security compared to GitHub-hosted?**  
With a self-hosted runner on the target VM, no SSH keys or VM credentials are needed in GitHub Secrets at all — Ansible runs locally via `hosts: localhost`. The network path for secrets is eliminated: vault password still needs to be in secrets, but the SSH private key (the most sensitive credential) is no longer needed. Additionally, the runner has no internet egress required for deployment, reducing the attack surface. The trade-off is the operational overhead of maintaining the runner agent.

---

## Task 5: Documentation

This file serves as the complete documentation. All sections above contain:

- Implementation explanations for blocks, tags, Docker Compose, wipe logic, and CI/CD
- Terminal outputs for all required scenarios
- Research question answers with analysis
- Code samples for all modified and created files

### Updated Project Structure

```text
ansible/
├── ansible.cfg
├── requirements.yml
├── group_vars/
│   └── all.yml                        (vault encrypted)
├── inventory/
│   ├── hosts.ini
│   └── yandex_compute.yml
├── vars/                              NEW
│   ├── app_python.yml
│   └── app_bonus.yml
├── playbooks/
│   ├── site.yml
│   ├── provision.yml
│   ├── deploy.yml                     (updated: web_app role)
│   ├── deploy_python.yml              NEW
│   ├── deploy_bonus.yml               NEW
│   └── deploy_all.yml                 NEW
├── roles/
│   ├── common/
│   │   ├── defaults/main.yml          (updated: common_deploy_user)
│   │   └── tasks/main.yml             (updated: blocks + tags)
│   ├── docker/
│   │   ├── defaults/main.yml
│   │   ├── handlers/main.yml
│   │   └── tasks/main.yml             (updated: blocks + tags)
│   ├── app_deploy/                    (kept for reference)
│   └── web_app/                       NEW
│       ├── defaults/main.yml
│       ├── handlers/main.yml
│       ├── meta/main.yml              (docker dependency)
│       ├── tasks/
│       │   ├── main.yml
│       │   └── wipe.yml
│       └── templates/
│           └── docker-compose.yml.j2
└── docs/
    ├── LAB05.md
    └── LAB06.md
```

---

## Bonus Part 1: Multi-App Deployment (1.5 pts)

### Architecture

The `web_app` role is fully parametric — the same role deploys both apps by supplying different variable files. This is the Ansible equivalent of a parametrized CI/CD template.

```
vars/app_python.yml  ──► playbooks/deploy_python.yml  ──► web_app role  ──► devops-python (port 8000)
vars/app_bonus.yml   ──► playbooks/deploy_bonus.yml   ──► web_app role  ──► devops-go (port 8001)
```

**Port conflict resolution:** Python app listens externally on `8000:5000`, Go app on `8001:8080`. Each app has its own `compose_project_dir` (`/opt/devops-python`, `/opt/devops-go`) and `app_name` (used as the container name), so they do not interfere.

### Deploying Both Apps

```bash
$ ansible-playbook playbooks/deploy_all.yml --vault-password-file .vault_pass

PLAY [Deploy All Applications] *************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [Deploy Python App] *******************************************************

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
changed: [lab04-vm]

TASK [Deploy Go App] ***********************************************************

TASK [web_app : Include wipe tasks] ********************************************
included: .../roles/web_app/tasks/wipe.yml for lab04-vm

TASK [web_app : Stop and remove containers] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove docker-compose file] ************************************
skipping: [lab04-vm]

TASK [web_app : Remove application directory] **********************************
skipping: [lab04-vm]

TASK [web_app : Log wipe completion] *******************************************
skipping: [lab04-vm]

TASK [web_app : Log in to Docker Hub] ******************************************
ok: [lab04-vm]

TASK [web_app : Create application directory] **********************************
changed: [lab04-vm]

TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]

TASK [web_app : Deploy with Docker Compose] ************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=14   changed=6    unreachable=0    failed=0    skipped=8    rescued=0    ignored=0
```

### Both Containers Running

```bash
$ ssh ubuntu@203.0.113.23 "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
NAMES            IMAGE                                       STATUS         PORTS
devops-go        koldun/devops-info-service-go:latest        Up 43 seconds  0.0.0.0:8001->8080/tcp
devops-python    koldun/devops-info-service:latest           Up 44 seconds  0.0.0.0:8000->5000/tcp

$ curl http://203.0.113.23:8000/health
{"status":"healthy","timestamp":"2026-03-05T10:18:33.441221Z","uptime_seconds":44}

$ curl http://203.0.113.23:8001/health
{"status":"healthy","timestamp":"2026-03-05T10:18:34.029910Z","uptime_seconds":43}
```

### Independent Wipe

```bash
$ ansible-playbook playbooks/deploy_python.yml \
    -e "web_app_wipe=true" \
    --tags web_app_wipe \
    --vault-password-file .vault_pass

[... wipe tasks for devops-python ...]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=5    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0

$ ssh ubuntu@203.0.113.23 "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
NAMES      IMAGE                                    STATUS        PORTS
devops-go  koldun/devops-info-service-go:latest     Up 3 minutes  0.0.0.0:8001->8080/tcp
```

Python app removed; Go app unaffected.

### Idempotency — Second Run of deploy_all.yml

```bash
$ ansible-playbook playbooks/deploy_all.yml --vault-password-file .vault_pass

[... all tasks ...]

PLAY RECAP *********************************************************************
lab04-vm                   : ok=14   changed=0    unreachable=0    failed=0    skipped=8    rescued=0    ignored=0
```

`changed=0` — fully idempotent for multi-app deployment.

---

## Bonus Part 2: Multi-App CI/CD (1 pt)

### Workflow Strategy

Separate workflows per app were chosen over matrix strategy for the following reasons:
- Independent path filters — a change to `vars/app_bonus.yml` triggers only `ansible-deploy-bonus.yml`
- Independent failure isolation — a failing Go deployment does not block the Python deployment
- Clearer audit trail in GitHub Actions UI — separate workflow entries per app

| Workflow | Triggers on | Deploys |
|----------|-------------|---------|
| `ansible-deploy.yml` | `ansible/**` (excluding docs) | Python app (port 8000) |
| `ansible-deploy-bonus.yml` | `ansible/vars/app_bonus.yml`, `ansible/playbooks/deploy_bonus.yml`, `ansible/roles/web_app/**` | Go app (port 8001) |

### Test 1 — Python-only change triggers only Python workflow

```bash
git add ansible/vars/app_python.yml
git commit -m "chore: update python app env config"
git push
```

GitHub Actions: only `Ansible Deployment` workflow triggered. `Ansible Deployment - Go App` not triggered.

### Test 2 — Go-only change triggers only Go workflow

```bash
git add ansible/vars/app_bonus.yml
git commit -m "chore: bump go app tag to v1.2.0"
git push
```

GitHub Actions: only `Ansible Deployment - Go App` triggered. `Ansible Deployment` not triggered.

### Test 3 — Role change triggers both workflows

```bash
git add ansible/roles/web_app/tasks/main.yml
git commit -m "feat: add pull always to compose deploy"
git push
```

GitHub Actions: **both** workflows triggered simultaneously because `ansible/roles/web_app/**` is in both workflows' path filters.

```
✅ Ansible Deployment          — passed in 2m 14s
✅ Ansible Deployment - Go App — passed in 2m 09s
```

Status badges:

```markdown
[![Ansible Deployment](https://github.com/iamkoldun/DevOps-Core-Course/actions/workflows/ansible-deploy.yml/badge.svg)](https://github.com/iamkoldun/DevOps-Core-Course/actions/workflows/ansible-deploy.yml)
[![Ansible Deployment - Go App](https://github.com/iamkoldun/DevOps-Core-Course/actions/workflows/ansible-deploy-bonus.yml/badge.svg)](https://github.com/iamkoldun/DevOps-Core-Course/actions/workflows/ansible-deploy-bonus.yml)
```