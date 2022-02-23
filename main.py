#!/usr/bin/env python
from email.policy import default
from constructs import Construct
from cdktf import (
  App, TerraformStack, RemoteBackend, NamedRemoteWorkspace, TerraformVariable, TerraformOutput, Fn,
  Token
)
from imports.google import (
  ComputeInstanceBootDisk, ComputeInstanceBootDiskInitializeParams, ComputeInstanceNetworkInterface,
  ComputeInstanceNetworkInterfaceAccessConfig, GoogleProvider, ComputeInstance,
  ComputeFirewall, ComputeFirewallAllow
)

STACK_NAME='cdktf_gcp_vm_unifi'
USE_REMOTE_BACKEND = False

# # Variables to set if using remote backend
# TF_ORG_NAME = 'orgname'
# TF_WORKSPACE_NAME = 'python'
# TF_BACKEND_HOSTNAME='app.terraform.io'

class MyStack(TerraformStack):
    def __init__(self, scope: Construct, ns: str):
        super().__init__(scope, ns)

        # Variables
        project_name = TerraformVariable(self, 'project_name',
          type='string',
          description='project to deploy to',
          default='unifi-236602'
        )
        region_name = TerraformVariable(self, 'region_name',
          type='string',
          description='region to deploy to',
          default='us-central1'
        )
        zone_name = TerraformVariable(self, 'zone_name',
          type='string',
          description='zone to deploy to',
          default='us-central1-c'
        )
        instance_name = TerraformVariable(self, 'instance_name',
          type='string',
          description='name for vm instance',
          default='debian-unifi'
        )
        ssh_username = TerraformVariable(self, 'ssh_username',
          type='string',
          description='username for VM access',
          default='user1'
        )
        ssh_key_path = TerraformVariable(self, 'ssh_key_path',
          type='string',
          description='path to ssh key for VM access',
          default='~/.ssh/id_rsa.pub'
        )
        instance_machine_type = TerraformVariable(self, 'instance_machine_type',
          type='string',
          description='type of machine for VM instance',
          default='e2-micro'
        )
        instance_vm_image = TerraformVariable(self, 'instance_vm_image',
          type='string',
          description='image to use for vm',
          default='debian-cloud/debian-10'
        )
        firewall_allow_ip_ranges = TerraformVariable(self, 'firewall_allow_ip_ranges',
          type='list(string)',
          default=['76.185.13.10/32']
        )
        firewall_allow_port_list_tcp = TerraformVariable(self, 'firewall_allow_port_list_tcp',
          type='list(string)',
          default=['22', '443', '80', '8843', '8880', '6789']
        )
        firewall_allow_port_list_udp = TerraformVariable(self, 'firewall_allow_port_list_udp',
          type='list(string)',
          default=['3478', '10001', '1900', '5514']
        )
        network_tier = TerraformVariable(self, 'network_tier',
          type='string',
          default='STANDARD'
        )
        startup_script = TerraformVariable(self, 'startup_script',
          type='string',
          description='commands for machine to run on startup',
          default='sudo apt update && apt install -yq docker.io; \
            sudo docker run -d --name=unifi -e PUID=1000 -e PGID=1000 -e MEM_LIMIT=900 \
            -e MEM_STARTUP=1024 -p 3478:3478/udp -p 10001:10001/udp -p 80:8080 \
            -p 443:8443 -p 1900:1900/udp -p 8843:8843 -p 8880:8880 -p 6789:6789 \
            -p 5514:5514/udp -v /config:/config --restart unless-stopped \
            lscr.io/linuxserver/unifi-controller'
        )
        
        # Providers
        GoogleProvider(
          self, 'GoogleProvider',
          project = project_name.string_value,
          region  = region_name.string_value,
          zone    = zone_name.string_value
        )

        # Resources
        vm_instance = ComputeInstance(self, 'vm_instance',
          name=instance_name.string_value,
          machine_type=instance_machine_type.string_value,
          boot_disk=ComputeInstanceBootDisk(
            auto_delete=True,
            initialize_params=ComputeInstanceBootDiskInitializeParams(
              image = instance_vm_image.string_value
            )
          ),
          metadata_startup_script=startup_script.string_value,
          # typing was confusing formatting these in cdk
          # did not want to break direct TF usage, so referencing in TF
          metadata = {
            'ssh-keys': '${format("%s:%s", var.ssh_username, file(var.ssh_key_path))}'
          },
          network_interface=[
            ComputeInstanceNetworkInterface(
              network='default',
              access_config=[
                ComputeInstanceNetworkInterfaceAccessConfig(
                  network_tier=network_tier.string_value
                )
              ],
              
            )
          ]
        )

        unifi_firewall = ComputeFirewall(self, 'unifi_firewall',
          name='unifi-firewall',
          network='default',
          allow=[
            ComputeFirewallAllow(
              protocol='tcp',
              ports=Fn.tolist(firewall_allow_port_list_tcp.list_value)
            ),
            ComputeFirewallAllow(
              protocol='udp',
              ports=Fn.tolist(firewall_allow_port_list_tcp.list_value)
            )
          ],
          source_ranges=firewall_allow_ip_ranges.list_value
        )

        # Outputs
        ip = TerraformOutput(self, 'ip',
          # Wasn't sure about typing, so referencing directly in TF
          value='${google_compute_instance.vm_instance.network_interface.0.access_config.0.nat_ip}'
        )
        ssh_pub_keys = TerraformOutput(self, 'ssh_pub_keys',
          value=vm_instance.metadata
        )
        admin_interface_url = TerraformOutput(self, 'admin_interface_url',
          value='https://${google_compute_instance.vm_instance.network_interface.0.access_config.0.nat_ip}/setup/'
        )

app = App()
stack = MyStack(app, STACK_NAME)
if USE_REMOTE_BACKEND:
  RemoteBackend(stack,
    hostname=TF_BACKEND_HOSTNAME,
    organization=TF_ORG_NAME,
    workspaces=NamedRemoteWorkspace(TF_WORKSPACE_NAME)
  )

app.synth()
