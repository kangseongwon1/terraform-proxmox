
terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint
  username = var.proxmox_username
  password = var.proxmox_password
  insecure = true
}

resource "proxmox_virtual_environment_vm" "server" {
  count = 1
  name  = "${var.project_name}-lb-${count.index + 1}"
  
  node_name = var.proxmox_node
  
  cpu {
    cores = 2
  }
  
  memory {
    dedicated = 2048
  }
  
  disk {
    interface = "scsi0"
    size      = 20
    file_format = "qcow2"
    datastore_id = var.proxmox_datastore
  }
  
  
  
  
  network_device {
    bridge = "vmbr0"
  }
  
  initialization {
    user_account {
      username = var.vm_username
      password = var.vm_password
      keys    = var.ssh_keys
    }
    
    ip_config {
      ipv4 {
        address = "${var.ip_addresses[count.index]}/24"
        gateway = var.gateway
      }
    }
  }
  
  operating_system {
    type = "l26"
  }
  
  clone {
    vm_id = var.template_vm_id
  }

}

output "vm_ips" {
  value = proxmox_virtual_environment_vm.server[*].ipv4_addresses
}

output "vm_names" {
  value = proxmox_virtual_environment_vm.server[*].name
}
