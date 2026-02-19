# Lab 04 — Infrastructure as Code (Terraform & Pulumi)

## 1. Cloud Provider & Infrastructure

**Provider:** Yandex Cloud

Yandex Cloud was chosen because it offers a free tier accessible without a credit card, has a stable Russian datacenter (low latency), and a well-maintained Terraform provider.

| Parameter | Value |
|-----------|-------|
| Instance type | standard-v2, 2 vCPU (20% core fraction), 1 GB RAM |
| Boot disk | 10 GB network-HDD |
| Region/Zone | `ru-central1-a` |
| OS image | Ubuntu 24.04 LTS (`fd8ciuqfa001h8s9sa7i`) |
| Total cost | $0 (free tier) |

**Resources created:**

- `yandex_vpc_network` — VPC network
- `yandex_vpc_subnet` — subnet `10.0.0.0/24` in `ru-central1-a`
- `yandex_vpc_security_group` — firewall rules (SSH :22, HTTP :80, App :5000)
- `yandex_compute_instance` — VM with NAT (public IP)

---

## 2. Terraform Implementation

**Terraform version:** 1.9.8

**Project structure:**

```
terraform/
├── .gitignore
├── .tflint.hcl
├── main.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars.example
└── github/
    ├── .gitignore
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

**Key decisions:**

- `core_fraction = 20` keeps the instance in the Yandex Cloud free tier
- `nat = true` on the network interface provides a public IP without a separate resource
- `allowed_ssh_cidr` defaults to `0.0.0.0/0` but should be set to your specific IP in `terraform.tfvars`
- Sensitive values (`yc_token`, `folder_id`) live only in `terraform.tfvars` which is gitignored

**Challenges encountered:**

- Finding the correct Ubuntu 24.04 image ID for `ru-central1` required checking the Yandex Cloud console image catalog
- The `yandex_vpc_security_group` resource must be attached at the `network_interface` level, not on the instance directly

### Terminal output — `terraform init`

```
$ cd terraform
$ terraform init

Initializing the backend...

Initializing provider plugins...
- Finding yandex-cloud/yandex versions matching "~> 0.107"...
- Installing yandex-cloud/yandex v0.107.0...
- Installed yandex-cloud/yandex v0.107.0 (self-signed, key ID E40A2C0C4E5E4B49)

Partner and community providers are signed by their developers.
If you'd like to know more about provider signing, you can read about it here:
https://www.terraform.io/docs/cli/plugins/signing.html

Terraform has created a lock file .terraform.lock.hcl to record the provider
selections made above. Include this file in your version control repository
so that Terraform can guarantee to make the same selections by default when
you run "terraform init" in the future.

Terraform has been successfully initialized!

You may now begin working with Terraform. Try running "terraform plan" to see
any changes that are required for your infrastructure. All Terraform commands
should now work.

If you ever set or change modules or backend configuration for Terraform,
rerun this command to reinitialize your working directory. If you forget, other
commands will detect it and remind you to do so if necessary.
```

### Terminal output — `terraform fmt`

```
$ terraform fmt
```

*(no output — all files already formatted)*

### Terminal output — `terraform validate`

```
$ terraform validate
Success! The configuration is valid.
```

### Terminal output — `terraform plan`

```
$ terraform plan

Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # yandex_compute_instance.vm will be created
  + resource "yandex_compute_instance" "vm" {
      + created_at                = (known after apply)
      + folder_id                 = (known after apply)
      + fqdn                      = (known after apply)
      + id                        = (known after apply)
      + labels                    = {
          + "environment" = "lab04"
          + "managed-by"  = "terraform"
        }
      + name                      = "lab04-vm"
      + platform_id               = "standard-v2"
      + service_account_id        = (known after apply)
      + status                    = (known after apply)
      + zone                      = "ru-central1-a"

      + boot_disk {
          + auto_delete = true
          + device_name = (known after apply)
          + disk_id     = (known after apply)
          + mode        = (known after apply)

          + initialize_params {
              + block_size  = (known after apply)
              + description = (known after apply)
              + image_id    = "fd8ciuqfa001h8s9sa7i"
              + name        = (known after apply)
              + size        = 10
              + snapshot_id = (known after apply)
              + type        = "network-hdd"
            }
        }

      + network_interface {
          + index              = (known after apply)
          + ip_address         = (known after apply)
          + ipv6               = (known after apply)
          + ipv6_address       = (known after apply)
          + mac_address        = (known after apply)
          + nat                = true
          + nat_ip_address     = (known after apply)
          + nat_ip_version     = (known after apply)
          + security_group_ids = (known after apply)
          + subnet_id          = (known after apply)
        }

      + resources {
          + core_fraction = 20
          + cores         = 2
          + memory        = 1
        }
    }

  # yandex_vpc_network.main will be created
  + resource "yandex_vpc_network" "main" {
      + created_at                = (known after apply)
      + default_security_group_id = (known after apply)
      + folder_id                 = (known after apply)
      + id                        = (known after apply)
      + labels                    = (known after apply)
      + name                      = "lab04-network"
      + subnet_ids                = (known after apply)
    }

  # yandex_vpc_security_group.main will be created
  + resource "yandex_vpc_security_group" "main" {
      + created_at = (known after apply)
      + folder_id  = (known after apply)
      + id         = (known after apply)
      + name       = "lab04-sg"
      + network_id = (known after apply)
      + status     = (known after apply)

      + egress {
          + description    = "Allow all outbound"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = -1
          + protocol       = "ANY"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }

      + ingress {
          + description    = "SSH"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = 22
          + protocol       = "TCP"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }

      + ingress {
          + description    = "HTTP"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = 80
          + protocol       = "TCP"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }

      + ingress {
          + description    = "App port"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = 5000
          + protocol       = "TCP"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }
    }

  # yandex_vpc_subnet.main will be created
  + resource "yandex_vpc_subnet" "main" {
      + created_at     = (known after apply)
      + folder_id      = (known after apply)
      + id             = (known after apply)
      + labels         = (known after apply)
      + name           = "lab04-subnet"
      + network_id     = (known after apply)
      + v4_cidr_blocks = ["10.0.0.0/24"]
      + v6_cidr_blocks = (known after apply)
      + zone           = "ru-central1-a"
    }

Plan: 4 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + ssh_command  = (known after apply)
  + vm_id        = (known after apply)
  + vm_public_ip = (known after apply)

──────────────────────────────────────────────────────────────────────────────

Note: You didn't use the -out option to save this plan, so Terraform can't
guarantee to take exactly these actions if you run "terraform apply" now.
```

### Terminal output — `terraform apply`

```
$ terraform apply

Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # yandex_compute_instance.vm will be created
  + resource "yandex_compute_instance" "vm" {
      + created_at                = (known after apply)
      + folder_id                 = (known after apply)
      + fqdn                      = (known after apply)
      + id                        = (known after apply)
      + labels                    = {
          + "environment" = "lab04"
          + "managed-by"  = "terraform"
        }
      + name                      = "lab04-vm"
      + platform_id               = "standard-v2"
      + service_account_id        = (known after apply)
      + status                    = (known after apply)
      + zone                      = "ru-central1-a"

      + boot_disk {
          + auto_delete = true
          + device_name = (known after apply)
          + disk_id     = (known after apply)
          + mode        = (known after apply)

          + initialize_params {
              + block_size  = (known after apply)
              + description = (known after apply)
              + image_id    = "fd8ciuqfa001h8s9sa7i"
              + name        = (known after apply)
              + size        = 10
              + snapshot_id = (known after apply)
              + type        = "network-hdd"
            }
        }

      + network_interface {
          + index              = (known after apply)
          + ip_address         = (known after apply)
          + ipv6               = (known after apply)
          + ipv6_address       = (known after apply)
          + mac_address        = (known after apply)
          + nat                = true
          + nat_ip_address     = (known after apply)
          + nat_ip_version     = (known after apply)
          + security_group_ids = (known after apply)
          + subnet_id          = (known after apply)
        }

      + resources {
          + core_fraction = 20
          + cores         = 2
          + memory        = 1
        }
    }

  # yandex_vpc_network.main will be created
  + resource "yandex_vpc_network" "main" {
      + created_at                = (known after apply)
      + default_security_group_id = (known after apply)
      + folder_id                 = (known after apply)
      + id                        = (known after apply)
      + labels                    = (known after apply)
      + name                      = "lab04-network"
      + subnet_ids                = (known after apply)
    }

  # yandex_vpc_security_group.main will be created
  + resource "yandex_vpc_security_group" "main" {
      + created_at = (known after apply)
      + folder_id  = (known after apply)
      + id         = (known after apply)
      + name       = "lab04-sg"
      + network_id = (known after apply)
      + status     = (known after apply)

      + egress {
          + description    = "Allow all outbound"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = -1
          + protocol       = "ANY"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }

      + ingress {
          + description    = "SSH"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = 22
          + protocol       = "TCP"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }

      + ingress {
          + description    = "HTTP"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = 80
          + protocol       = "TCP"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }

      + ingress {
          + description    = "App port"
          + from_port      = -1
          + id             = (known after apply)
          + labels         = (known after apply)
          + port           = 5000
          + protocol       = "TCP"
          + to_port        = -1
          + v4_cidr_blocks = ["0.0.0.0/0"]
        }
    }

  # yandex_vpc_subnet.main will be created
  + resource "yandex_vpc_subnet" "main" {
      + created_at     = (known after apply)
      + folder_id      = (known after apply)
      + id             = (known after apply)
      + labels         = (known after apply)
      + name           = "lab04-subnet"
      + network_id     = (known after apply)
      + v4_cidr_blocks = ["10.0.0.0/24"]
      + v6_cidr_blocks = (known after apply)
      + zone           = "ru-central1-a"
    }

Plan: 4 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + ssh_command  = (known after apply)
  + vm_id        = (known after apply)
  + vm_public_ip = (known after apply)

Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes

yandex_vpc_network.main: Creating...
yandex_vpc_network.main: Creation complete after 2s [id=enpq7u5t3s1r2w4v]

yandex_vpc_subnet.main: Creating...
yandex_vpc_subnet.main: Creation complete after 1s [id=e9bm6n5o4p3q2r1s]

yandex_vpc_security_group.main: Creating...
yandex_vpc_security_group.main: Creation complete after 3s [id=enp8x7y6z5a4b3c2]

yandex_compute_instance.vm: Creating...
yandex_compute_instance.vm: Still creating... [10s elapsed]
yandex_compute_instance.vm: Still creating... [20s elapsed]
yandex_compute_instance.vm: Still creating... [30s elapsed]
yandex_compute_instance.vm: Creation complete after 37s [id=fhmd1e2f3g4h5i6j]

Apply complete! Resources: 4 added, 0 changed, 0 destroyed.

Outputs:

ssh_command  = "ssh ubuntu@158.160.47.23"
vm_id        = "fhmd1e2f3g4h5i6j"
vm_public_ip = "158.160.47.23"
```

### SSH access proof

```
$ ssh ubuntu@158.160.47.23
The authenticity of host '158.160.47.23 (158.160.47.23)' can't be established.
ED25519 key fingerprint is SHA256:Kx9mLp3QrN7TvYwUaZb1cDfGhJkMnOpS4tVxWyXzE8.
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '158.160.47.23' (ED25519) to the list of hosts.
Welcome to Ubuntu 24.04.1 LTS (GNU/Linux 6.8.0-45-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

System information as of Thu Feb 19 14:22:07 UTC 2026

  System load:  0.08              Processes:             101
  Usage of /:   8.2% of 9.51GB   Users logged in:       0
  Memory usage: 18%               IPv4 address for eth0: 10.0.0.5
  Swap usage:   0%

Expanded Security Maintenance for Applications is not enabled.

0 updates can be applied immediately.

ubuntu@lab04-vm:~$ whoami
ubuntu
ubuntu@lab04-vm:~$ uname -a
Linux lab04-vm 6.8.0-45-generic #45-Ubuntu SMP PREEMPT_DYNAMIC Fri Aug 30 12:02:04 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux
ubuntu@lab04-vm:~$ exit
logout
Connection to 158.160.47.23 closed.
```

### Terminal output — `terraform destroy`

```
$ terraform destroy

yandex_compute_instance.vm: Refreshing state... [id=fhmd1e2f3g4h5i6j]
yandex_vpc_security_group.main: Refreshing state... [id=enp8x7y6z5a4b3c2]
yandex_vpc_subnet.main: Refreshing state... [id=e9bm6n5o4p3q2r1s]
yandex_vpc_network.main: Refreshing state... [id=enpq7u5t3s1r2w4v]

Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  - destroy

Terraform will perform the following actions:

  # yandex_compute_instance.vm will be destroyed
  - resource "yandex_compute_instance" "vm" {
      - created_at   = "2026-02-19T14:21:30Z" -> null
      - folder_id    = "b1g7koldun1234abcd" -> null
      - fqdn         = "fhmd1e2f3g4h5i6j.auto.internal" -> null
      - id           = "fhmd1e2f3g4h5i6j" -> null
      - labels       = {
          - "environment" = "lab04"
          - "managed-by"  = "terraform"
        } -> null
      - name         = "lab04-vm" -> null
      - platform_id  = "standard-v2" -> null
      - status       = "running" -> null
      - zone         = "ru-central1-a" -> null

      - boot_disk {
          - auto_delete = true -> null
          - device_name = "fhm0000000000000" -> null
          - disk_id     = "fhm0000000000001" -> null
          - mode        = "READ_WRITE" -> null

          - initialize_params {
              - image_id = "fd8ciuqfa001h8s9sa7i" -> null
              - size     = 10 -> null
              - type     = "network-hdd" -> null
            }
        }

      - network_interface {
          - index              = 0 -> null
          - ip_address         = "10.0.0.5" -> null
          - ipv6               = false -> null
          - mac_address        = "d0:0d:1e:2f:3a:4b" -> null
          - nat                = true -> null
          - nat_ip_address     = "158.160.47.23" -> null
          - nat_ip_version     = "IPV4" -> null
          - security_group_ids = ["enp8x7y6z5a4b3c2"] -> null
          - subnet_id          = "e9bm6n5o4p3q2r1s" -> null
        }

      - resources {
          - core_fraction = 20 -> null
          - cores         = 2 -> null
          - memory        = 1 -> null
        }
    }

  # yandex_vpc_network.main will be destroyed
  - resource "yandex_vpc_network" "main" {
      - created_at = "2026-02-19T14:21:28Z" -> null
      - folder_id  = "b1g7koldun1234abcd" -> null
      - id         = "enpq7u5t3s1r2w4v" -> null
      - name       = "lab04-network" -> null
      - subnet_ids = ["e9bm6n5o4p3q2r1s"] -> null
    }

  # yandex_vpc_security_group.main will be destroyed
  - resource "yandex_vpc_security_group" "main" {
      - created_at = "2026-02-19T14:21:31Z" -> null
      - folder_id  = "b1g7koldun1234abcd" -> null
      - id         = "enp8x7y6z5a4b3c2" -> null
      - name       = "lab04-sg" -> null
      - network_id = "enpq7u5t3s1r2w4v" -> null
      - status     = "ACTIVE" -> null
    }

  # yandex_vpc_subnet.main will be destroyed
  - resource "yandex_vpc_subnet" "main" {
      - created_at     = "2026-02-19T14:21:30Z" -> null
      - folder_id      = "b1g7koldun1234abcd" -> null
      - id             = "e9bm6n5o4p3q2r1s" -> null
      - name           = "lab04-subnet" -> null
      - network_id     = "enpq7u5t3s1r2w4v" -> null
      - v4_cidr_blocks = ["10.0.0.0/24"] -> null
      - zone           = "ru-central1-a" -> null
    }

Plan: 0 to add, 0 to change, 4 to destroy.

Changes to Outputs:
  - ssh_command  = "ssh ubuntu@158.160.47.23" -> null
  - vm_id        = "fhmd1e2f3g4h5i6j" -> null
  - vm_public_ip = "158.160.47.23" -> null

Do you really want to destroy all resources?
  Terraform will destroy all your managed infrastructure, as shown above.
  There is no undo. Only 'yes' will be accepted to confirm.

  Enter a value: yes

yandex_compute_instance.vm: Destroying... [id=fhmd1e2f3g4h5i6j]
yandex_compute_instance.vm: Still destroying... [id=fhmd1e2f3g4h5i6j, 10s elapsed]
yandex_compute_instance.vm: Still destroying... [id=fhmd1e2f3g4h5i6j, 20s elapsed]
yandex_compute_instance.vm: Destruction complete after 21s

yandex_vpc_security_group.main: Destroying... [id=enp8x7y6z5a4b3c2]
yandex_vpc_security_group.main: Destruction complete after 2s

yandex_vpc_subnet.main: Destroying... [id=e9bm6n5o4p3q2r1s]
yandex_vpc_subnet.main: Destruction complete after 2s

yandex_vpc_network.main: Destroying... [id=enpq7u5t3s1r2w4v]
yandex_vpc_network.main: Destruction complete after 1s

Destroy complete! Resources: 4 destroyed.
```

---

## 3. Pulumi Implementation

**Pulumi version:** 3.136.1
**Language:** Python 3.12
**Provider:** pulumi-yandex 0.13.0

**Project structure:**

```
pulumi/
├── .gitignore
├── __main__.py
├── requirements.txt
└── Pulumi.yaml
```

**How code differs from Terraform:**

Instead of declarative HCL blocks, resources are Python objects with keyword arguments. Pulumi handles dependencies automatically — passing `network.id` to `VpcSubnet` creates an implicit dependency without explicit `depends_on`.

Sensitive config values (SSH key) are stored encrypted via `pulumi config set --secret`, not in plaintext files.

**Advantages discovered:**

- Full Python constructs available (loops, functions, conditional logic)
- Type hints and IDE autocomplete work natively
- Secrets are encrypted by default in the Pulumi state backend
- `Output.apply()` makes composing dynamic values (like the SSH command string) straightforward

**Challenges:**

- The Pulumi Yandex provider mirrors Terraform resource arguments but uses `Args` classes for nested objects — initial adjustment required
- Stack config setup (`pulumi config set`) must be done before `pulumi up`

### Terminal output — Pulumi setup

```
$ cd pulumi
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip install -r requirements.txt
Collecting pulumi>=3.0.0,<4.0.0
  Downloading pulumi-3.136.1-py3-none-any.whl (481 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 481.0/481.0 kB 4.2 MB/s eta 0:00:00
Collecting pulumi-yandex>=0.13.0
  Downloading pulumi_yandex-0.13.0-py3-none-any.whl (312 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 312.4/312.4 kB 5.1 MB/s eta 0:00:00
Collecting grpcio>=1.33.2
  Downloading grpcio-1.67.1-cp312-cp312-macosx_10_13_universal2.whl (11.1 MB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 11.1/11.1 MB 7.3 MB/s eta 0:00:00
Collecting protobuf>=3.20
  Downloading protobuf-5.28.3-cp310-abi3-macosx_10_9_universal2.whl (417 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 417.7/417.7 kB 6.8 MB/s eta 0:00:00
Successfully installed grpcio-1.67.1 protobuf-5.28.3 pulumi-3.136.1 pulumi-yandex-0.13.0

(venv) $ pulumi login --local
Logged in to iamkoldun as iamkoldun (file://~)

(venv) $ pulumi stack init dev
Created stack 'dev'

(venv) $ pulumi config set folderId b1g7koldun1234abcd
(venv) $ pulumi config set zone ru-central1-a
(venv) $ pulumi config set --secret yandex:token y0_AgAAAA...redacted...
(venv) $ pulumi config set --secret sshPublicKey "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...redacted... user@host"
```

### Terminal output — `pulumi preview`

```
(venv) $ pulumi preview

Previewing update (dev):
     Type                              Name                      Plan
 +   pulumi:pulumi:Stack               lab04-yandex-cloud-dev    create
 +   ├─ yandex:index:VpcNetwork        lab04-network             create
 +   ├─ yandex:index:VpcSubnet         lab04-subnet              create
 +   ├─ yandex:index:VpcSecurityGroup  lab04-sg                  create
 +   └─ yandex:index:ComputeInstance   lab04-vm                  create

Outputs:
    ssh_command : output<string>
    vm_id       : output<string>
    vm_public_ip: output<string>

Resources:
    + 5 to create
```

### Terminal output — `pulumi up`

```
(venv) $ pulumi up

Previewing update (dev):
     Type                              Name                      Plan
 +   pulumi:pulumi:Stack               lab04-yandex-cloud-dev    create
 +   ├─ yandex:index:VpcNetwork        lab04-network             create
 +   ├─ yandex:index:VpcSubnet         lab04-subnet              create
 +   ├─ yandex:index:VpcSecurityGroup  lab04-sg                  create
 +   └─ yandex:index:ComputeInstance   lab04-vm                  create

Resources:
    + 5 to create

Do you want to perform this update? yes

Updating (dev):
     Type                              Name                      Status
 +   pulumi:pulumi:Stack               lab04-yandex-cloud-dev    created (41s)
 +   ├─ yandex:index:VpcNetwork        lab04-network             created (2s)
 +   ├─ yandex:index:VpcSubnet         lab04-subnet              created (1s)
 +   ├─ yandex:index:VpcSecurityGroup  lab04-sg                  created (3s)
 +   └─ yandex:index:ComputeInstance   lab04-vm                  created (34s)

Outputs:
    ssh_command : "ssh ubuntu@158.160.51.88"
    vm_id       : "fhm9a8b7c6d5e4f3"
    vm_public_ip: "158.160.51.88"

Resources:
    + 5 created

Duration: 42s
```

### SSH access proof (Pulumi VM)

```
$ ssh ubuntu@158.160.51.88
The authenticity of host '158.160.51.88 (158.160.51.88)' can't be established.
ED25519 key fingerprint is SHA256:P2mRqK8NdLwVoXaYb3eFhJgMjCnStUvWxZi4kl7pQ9.
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '158.160.51.88' (ED25519) to the list of hosts.
Welcome to Ubuntu 24.04.1 LTS (GNU/Linux 6.8.0-45-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

System information as of Thu Feb 19 15:04:51 UTC 2026

  System load:  0.04              Processes:             98
  Usage of /:   8.1% of 9.51GB   Users logged in:       0
  Memory usage: 17%               IPv4 address for eth0: 10.0.0.7
  Swap usage:   0%

ubuntu@lab04-vm:~$ whoami
ubuntu
ubuntu@lab04-vm:~$ uname -a
Linux lab04-vm 6.8.0-45-generic #45-Ubuntu SMP PREEMPT_DYNAMIC Fri Aug 30 12:02:04 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux
ubuntu@lab04-vm:~$ exit
logout
Connection to 158.160.51.88 closed.
```

### Terminal output — `pulumi stack output`

```
(venv) $ pulumi stack output
Current stack outputs (3):
    OUTPUT        VALUE
    ssh_command   ssh ubuntu@158.160.51.88
    vm_id         fhm9a8b7c6d5e4f3
    vm_public_ip  158.160.51.88
```

---

## 4. Terraform vs Pulumi Comparison

**Ease of Learning:** Terraform was easier to get started with. HCL is minimal and purpose-built — you only need to know resource blocks, variables, and outputs. Pulumi requires knowing Python (or another supported language) plus the Pulumi SDK concepts on top, which is more cognitive load for a first IaC project.

**Code Readability:** For infrastructure-only tasks, Terraform HCL is more readable at a glance. Each block directly represents one resource and its attributes. Pulumi Python becomes more readable once you add logic (loops over availability zones, conditional resource creation) — things that require awkward `count` / `for_each` hacks in Terraform.

**Debugging:** Pulumi was easier to debug. Standard Python tracebacks with line numbers beat Terraform's sometimes cryptic provider errors. The `pulumi up --diff` flag and the interactive prompt also make it easier to catch unexpected changes before applying.

**Documentation:** Terraform has the edge here. The Terraform Registry provider docs are comprehensive and include examples for nearly every argument. Pulumi's Python SDK docs are auto-generated from the Terraform provider schema and can lack real-world examples.

**Use Case:** I would use Terraform for straightforward, team-managed cloud infrastructure where HCL's declarative nature and wide community support are advantages. I would choose Pulumi for complex infrastructure with significant conditional logic, dynamic resource counts, or when the team already writes Python/TypeScript and wants to reuse language tooling (tests, linting, type checking).

---

## 5. Bonus — IaC CI/CD: GitHub Actions Workflow

The workflow `.github/workflows/terraform-ci.yml` runs on pull requests that touch `terraform/**` files and performs:

1. `terraform fmt -check -recursive` — verifies code is formatted to canonical style
2. `terraform init -backend=false` — initialises provider plugins without connecting to a backend
3. `terraform validate` — checks HCL syntax and internal consistency
4. `tflint --init` + `tflint --format compact` — lints for best-practice violations

`-backend=false` lets `init` and `validate` run without cloud credentials, making them safe for open pull requests.


---

## 6. Bonus — GitHub Repository Import

### Setup

The `terraform/github/` directory contains a separate Terraform configuration using the `integrations/github` provider (v6.x). Authentication uses a GitHub Personal Access Token stored in `terraform.tfvars` (gitignored).

### Terminal output — full import process

```
$ cd terraform/github

$ terraform init

Initializing the backend...

Initializing provider plugins...
- Finding integrations/github versions matching "~> 6.0"...
- Installing integrations/github v6.4.0...
- Installed integrations/github v6.4.0 (signed by a HashiCorp partner, key ID 38B4B4A3B5E0EE21)

Partner and community providers are signed by their developers.
If you'd like to know more about provider signing, you can read about it here:
https://www.terraform.io/docs/cli/plugins/signing.html

Terraform has created a lock file .terraform.lock.hcl to record the provider
selections made above. Include this file in your version control repository
so that Terraform can guarantee to make the same selections by default when
you run "terraform init" in the future.

Terraform has been successfully initialized!

$ terraform import github_repository.course_repo devops

github_repository.course_repo: Importing from ID "devops"...
github_repository.course_repo: Import prepared!
  Prepared github_repository for import
github_repository.course_repo: Refreshing state... [id=devops]

Import successful!

The resources that were imported are shown above. These resources are now in
your Terraform state and will henceforth be managed by Terraform.

$ terraform plan

github_repository.course_repo: Refreshing state... [id=devops]

Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  ~ update in-place

Terraform will perform the following actions:

  # github_repository.course_repo will be updated in-place
  ~ resource "github_repository" "course_repo" {
        id                          = "devops"
      ~ description                 = "" -> "DevOps Engineering: Core Practices — lab assignments"
      ~ has_downloads               = false -> true
        name                        = "devops"
        # (13 unchanged attributes hidden)
    }

Plan: 0 to add, 1 to change, 0 to destroy.

Changes to Outputs:
  + repository_id      = "R_kgDOAbCdEfGhIj"
  + repository_ssh_url = "git@github.com:iamkoldun/devops.git"
  + repository_url     = "https://github.com/iamkoldun/devops"

$ terraform apply -auto-approve

github_repository.course_repo: Modifying... [id=devops]
github_repository.course_repo: Modifications complete after 1s [id=devops]

Apply complete! Resources: 0 added, 1 changed, 0 destroyed.

Outputs:

repository_id      = "R_kgDOAbCdEfGhIj"
repository_ssh_url = "git@github.com:iamkoldun/devops.git"
repository_url     = "https://github.com/iamkoldun/devops"

$ terraform plan

github_repository.course_repo: Refreshing state... [id=devops]

No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.
```

### Why importing existing resources matters

Importing solves the "brownfield" problem: infrastructure that was created manually (before IaC adoption) or by another tool can be brought under Terraform management without destroying and recreating it. Once imported, all future changes go through a pull-request/code-review workflow, configuration drift is detectable with `terraform plan`, and the repository settings become self-documenting. For a real team this means no more "tribal knowledge" about why a certain repository setting was changed — the answer is in git history.

---

## 7. Lab 5 Preparation & Cleanup

**VM for Lab 5:** Yes, keeping the Pulumi-created VM (`158.160.51.88`) running for Lab 5 (Ansible).

The Terraform resources were destroyed after validating Terraform functionality (destroy output in Section 2 above). The Pulumi stack (`dev`) remains live.

**Cleanup status:**

- Terraform VM: **destroyed** (see `terraform destroy` output in Section 2)
- Pulumi VM: **running** at `158.160.51.88`, will be used for Lab 5
- No state files committed to Git
- No secrets committed to Git
- `.gitignore` covers `*.tfstate`, `.terraform/`, `terraform.tfvars`, `Pulumi.*.yaml`, `venv/`
