import pulumi
import pulumi_yandex as yandex

config = pulumi.Config()
folder_id = config.require("folderId")
zone = config.get("zone") or "ru-central1-a"
prefix = config.get("prefix") or "lab04"
ssh_user = config.get("sshUser") or "ubuntu"
ssh_public_key = config.require_secret("sshPublicKey")
allowed_ip = config.get("allowedIp") or "0.0.0.0/0"

UBUNTU_2404_IMAGE_ID = "fd8ciuqfa001h8s9sa7i"

network = yandex.VpcNetwork(
    f"{prefix}-network",
    name=f"{prefix}-network",
)

subnet = yandex.VpcSubnet(
    f"{prefix}-subnet",
    name=f"{prefix}-subnet",
    zone=zone,
    network_id=network.id,
    v4_cidr_blocks=["10.0.0.0/24"],
)

security_group = yandex.VpcSecurityGroup(
    f"{prefix}-sg",
    name=f"{prefix}-sg",
    network_id=network.id,
    ingresses=[
        yandex.VpcSecurityGroupIngressArgs(
            protocol="TCP",
            port=22,
            v4_cidr_blocks=[allowed_ip],
            description="SSH",
        ),
        yandex.VpcSecurityGroupIngressArgs(
            protocol="TCP",
            port=80,
            v4_cidr_blocks=["0.0.0.0/0"],
            description="HTTP",
        ),
        yandex.VpcSecurityGroupIngressArgs(
            protocol="TCP",
            port=5000,
            v4_cidr_blocks=["0.0.0.0/0"],
            description="App port",
        ),
    ],
    egresses=[
        yandex.VpcSecurityGroupEgressArgs(
            protocol="ANY",
            v4_cidr_blocks=["0.0.0.0/0"],
            description="Allow all outbound",
        ),
    ],
)

vm = yandex.ComputeInstance(
    f"{prefix}-vm",
    name=f"{prefix}-vm",
    platform_id="standard-v2",
    zone=zone,
    resources=yandex.ComputeInstanceResourcesArgs(
        cores=2,
        memory=1,
        core_fraction=20,
    ),
    boot_disk=yandex.ComputeInstanceBootDiskArgs(
        initialize_params=yandex.ComputeInstanceBootDiskInitializeParamsArgs(
            image_id=UBUNTU_2404_IMAGE_ID,
            size=10,
            type="network-hdd",
        ),
    ),
    network_interfaces=[
        yandex.ComputeInstanceNetworkInterfaceArgs(
            subnet_id=subnet.id,
            security_group_ids=[security_group.id],
            nat=True,
        ),
    ],
    metadata={
        "ssh-keys": ssh_public_key.apply(lambda key: f"{ssh_user}:{key}"),
    },
    labels={
        "environment": "lab04",
        "managed-by": "pulumi",
    },
)

public_ip = vm.network_interfaces[0].nat_ip_address

pulumi.export("vm_public_ip", public_ip)
pulumi.export("ssh_command", public_ip.apply(lambda ip: f"ssh {ssh_user}@{ip}"))
pulumi.export("vm_id", vm.id)
