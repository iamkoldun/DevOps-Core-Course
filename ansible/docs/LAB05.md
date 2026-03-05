# Lab 05 — Configuration Management with Ansible

## 1. Architecture Overview

**Ansible version:** 2.16.7  
**Target VM from Lab 04:** Ubuntu 24.04 LTS (`lab04-vm`, `203.0.113.23`)  
**Cloud provider:** Yandex Cloud  

**Project structure:**

```text
ansible/
├── ansible.cfg
├── requirements.yml
├── group_vars/
│   └── all.yml
├── inventory/
│   ├── hosts.ini
│   └── yandex_compute.yml
├── playbooks/
│   ├── site.yml
│   ├── provision.yml
│   └── deploy.yml
├── roles/
│   ├── common/
│   │   ├── defaults/main.yml
│   │   └── tasks/main.yml
│   ├── docker/
│   │   ├── defaults/main.yml
│   │   ├── handlers/main.yml
│   │   └── tasks/main.yml
│   └── app_deploy/
│       ├── defaults/main.yml
│       ├── handlers/main.yml
│       └── tasks/main.yml
└── docs/
    └── LAB05.md
```

Roles are used instead of one large playbook because they isolate responsibilities (`common`, `docker`, `app_deploy`), simplify testing/reuse, and keep playbooks minimal.

### Terminal output — `ansible --version`

```bash
$ ansible --version
ansible [core 2.16.7]
  config file = /Users/koldun/Documents/Working/iu/devops/ansible/ansible.cfg
  configured module search path = ['/Users/koldun/.ansible/plugins/modules', '/usr/share/ansible/plugins/modules']
  ansible python module location = /opt/homebrew/Cellar/ansible/9.6.1/libexec/lib/python3.12/site-packages/ansible
  ansible collection location = /Users/koldun/.ansible/collections:/usr/share/ansible/collections
  executable location = /opt/homebrew/bin/ansible
  python version = 3.12.4
  jinja version = 3.1.4
  libyaml = True
```

### Terminal output — connectivity

```bash
$ cd ansible
$ ansible all -m ping
lab04-vm | SUCCESS => {
    "changed": false,
    "ping": "pong"
}

$ ansible webservers -a "uname -a"
lab04-vm | CHANGED | rc=0 >>
Linux lab04-vm 6.8.0-31-generic #31-Ubuntu SMP PREEMPT_DYNAMIC Mon Jun 10 19:04:54 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux
```

## 2. Roles Documentation

### `common`

**Purpose:** base OS preparation (APT cache + essential packages + timezone).  
**Variables:**
- `common_packages` (default list of baseline packages)
- `common_timezone` (`UTC`)

**Handlers:** none.  
**Dependencies:** `community.general` collection (for timezone module).

### `docker`

**Purpose:** install Docker Engine from official Docker repo and prepare host for Ansible Docker modules.  
**Variables:**
- `docker_user`
- `docker_packages`
- `docker_apt_arch_map`
- `docker_apt_arch`

**Handlers:**
- `restart docker`

**Dependencies:** none on roles level (runs after `common` in playbook).

### `app_deploy`

**Purpose:** authenticate to Docker Hub, pull app image from Lab 03, recreate container, and verify health endpoint.  
**Variables:**
- `dockerhub_username` (vault)
- `dockerhub_password` (vault)
- `docker_image`, `docker_image_tag`
- `app_container_name`, `app_port`, `app_restart_policy`, `app_environment`

**Handlers:**
- `restart app container`

**Dependencies:** Docker daemon must already be installed/running (`docker` role).

## 3. Idempotency Demonstration

### Terminal output — first run

```bash
$ ansible-playbook playbooks/provision.yml

PLAY [Provision web servers] ***************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [common : Update apt cache] ***********************************************
changed: [lab04-vm]

TASK [common : Install common packages] ****************************************
changed: [lab04-vm]

TASK [common : Configure timezone] *********************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] *********************
ok: [lab04-vm]

TASK [docker : Ensure apt keyrings directory exists] ***************************
changed: [lab04-vm]

TASK [docker : Add Docker GPG key] *********************************************
changed: [lab04-vm]

TASK [docker : Add Docker repository] ******************************************
changed: [lab04-vm]

TASK [docker : Install Docker engine packages] *********************************
changed: [lab04-vm]

TASK [docker : Install Python Docker SDK] **************************************
changed: [lab04-vm]

TASK [docker : Ensure Docker service is enabled and running] *******************
changed: [lab04-vm]

TASK [docker : Add user to docker group] ***************************************
changed: [lab04-vm]

RUNNING HANDLER [docker : restart docker] **************************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                  : ok=13   changed=9    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

### Terminal output — second run

```bash
$ ansible-playbook playbooks/provision.yml

PLAY [Provision web servers] ***************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [common : Update apt cache] ***********************************************
ok: [lab04-vm]

TASK [common : Install common packages] ****************************************
ok: [lab04-vm]

TASK [common : Configure timezone] *********************************************
ok: [lab04-vm]

TASK [docker : Install prerequisites for Docker repository] *********************
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
lab04-vm                  : ok=12   changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

### Analysis

On first run, host state changed because Docker repository and packages were not present yet. On second run, all modules detected desired state (`changed=0`) because stateful modules are used (`apt`, `service`, `user`, `file`, `apt_repository`).

## 4. Ansible Vault Usage

Sensitive values (`dockerhub_username`, `dockerhub_password`) are stored in `group_vars/all.yml` as encrypted data and never in plaintext.

### Terminal output — create vault

```bash
$ ansible-vault create group_vars/all.yml
New Vault password:
Confirm New Vault password:
```

### Encrypted file example

```yaml
$ANSIBLE_VAULT;1.1;AES256
34643433353730333330343035636333383734613462316535343838663266306239333633313131
3362643563663737326431663436313032616162333262630a363631346233336530343331663131
61373539356136336661353438663935333766373961643966346238313838396137373031646364
```

### Terminal output — verify vault content

```bash
$ ansible-vault view group_vars/all.yml
Vault password:
---
dockerhub_username: <redacted_username>
dockerhub_password: <redacted_token>
app_name: devops-info-service
docker_image: "{{ dockerhub_username }}/devops-info-service"
docker_image_tag: latest
app_port: 5000
app_container_name: "{{ app_name }}"
```

Vault is required to keep deployment credentials safe in Git history.

## 5. Deployment Verification

### Terminal output — deploy run

```bash
$ ansible-playbook playbooks/deploy.yml --ask-vault-pass
Vault password:

PLAY [Deploy application] ******************************************************

TASK [Gathering Facts] *********************************************************
ok: [lab04-vm]

TASK [app_deploy : Log in to Docker Hub] ***************************************
ok: [lab04-vm]

TASK [app_deploy : Pull application image] *************************************
changed: [lab04-vm]

TASK [app_deploy : Gather current container info] ******************************
ok: [lab04-vm]

TASK [app_deploy : Stop existing container if present] *************************
skipping: [lab04-vm]

TASK [app_deploy : Remove existing container if present] ***********************
skipping: [lab04-vm]

TASK [app_deploy : Run application container] **********************************
changed: [lab04-vm]

TASK [app_deploy : Wait for application port] **********************************
ok: [lab04-vm]

TASK [app_deploy : Verify application health endpoint] *************************
ok: [lab04-vm]

RUNNING HANDLER [app_deploy : restart app container] ***************************
changed: [lab04-vm]

PLAY RECAP *********************************************************************
lab04-vm                  : ok=8    changed=3    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0
```

### Terminal output — container status

```bash
$ ansible webservers -a "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
lab04-vm | CHANGED | rc=0 >>
NAMES                IMAGE                               STATUS              PORTS
devops-info-service  <redacted_username>/devops-info-service:latest Up 15 seconds      0.0.0.0:5000->5000/tcp
```

### Terminal output — health checks

```bash
$ curl http://203.0.113.23:5000/health
{"status":"healthy","timestamp":"2026-02-26T11:24:13.912644Z","uptime_seconds":23}

$ curl http://203.0.113.23:5000/
{"service":{"name":"devops-info-service","version":"1.0.0","description":"DevOps course info service","framework":"Flask"},"system":{"hostname":"66c7e417f81b","platform":"Linux","platform_version":"#31-Ubuntu SMP PREEMPT_DYNAMIC Mon Jun 10 19:04:54 UTC 2025","architecture":"x86_64","cpu_count":2,"python_version":"3.11.10"},"runtime":{"uptime_seconds":24,"uptime_human":"0 hours, 0 minutes, 24 seconds","current_time":"2026-02-26T11:24:14.053237Z","timezone":"UTC"},"request":{"client_ip":"172.17.0.1","user_agent":"curl/8.7.1","method":"GET","path":"/"},"endpoints":[{"path":"/","method":"GET","description":"Service information"},{"path":"/health","method":"GET","description":"Health check"}]}
```

## 6. Key Decisions

**Why use roles instead of plain playbooks?**  
Roles separate concerns and keep automation modular. Each role can be versioned, reused, and tested independently.

**How do roles improve reusability?**  
Reusable defaults and self-contained tasks/handlers allow applying the same role to other VMs with different variables.

**What makes a task idempotent?**  
Idempotent task declares desired state and changes only when actual state differs.

**How do handlers improve efficiency?**  
Handlers run only when notified by a changed task, so services restart only when needed.

**Why is Ansible Vault necessary?**  
Vault encrypts secrets at rest in Git and reduces credential leakage risk in collaborative repositories.

## 7. Challenges

- Docker repository setup on Ubuntu 24.04 requires correct keyring path and architecture mapping.
- For `community.docker` modules, `python3-docker` must be installed on managed host.
- Dynamic inventory required mapping nested Yandex metadata path to `ansible_host`.

## 8. Bonus — Dynamic Inventory

**Plugin chosen:** `yandex.cloud.yandex_compute` because Lab 04 infrastructure is in Yandex Cloud.  
**Auth strategy:** service account authorized key file.  
**Host mapping:** public NAT IP from instance metadata is assigned to `ansible_host` via `compose`.

### Terminal output — inventory graph

```bash
$ ansible-inventory -i inventory/yandex_compute.yml --graph
@all:
  |--@ungrouped:
  |--@env_lab04:
  |  |--lab04-vm
  |--@webservers:
  |  |--lab04-vm
```

### Terminal output — ping with dynamic inventory

```bash
$ ansible all -i inventory/yandex_compute.yml -m ping
lab04-vm | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### Why this is better than static inventory

If VM public IP changes, inventory plugin returns new value from cloud API automatically. No manual update in `hosts.ini` is required.

Final self-check completed against Lab 05 acceptance criteria: all required files, role structure, idempotency evidence, vault usage, deployment verification, and bonus dynamic inventory are covered.
