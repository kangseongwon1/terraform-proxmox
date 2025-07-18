terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
  }
}



resource "proxmox_virtual_environment_vm" "this" {
  name  = var.name
  node_name = var.proxmox_node

  cpu {
    cores = var.cpu
  }

  memory {
    dedicated = var.memory
  }

  dynamic "disk" {
    for_each = var.disks
    content {
      interface    = disk.value.interface
      size         = disk.value.size
      file_format  = "qcow2"
      datastore_id = disk.value.datastore_id
    }
  }

  dynamic "network_device" {
    for_each = var.network_devices
    content {
      bridge = network_device.value.bridge
    }
  }

  initialization {
    user_account {
      username = var.vm_username
      password = var.vm_password
      keys    = var.ssh_keys
    }
    # 첫 번째 네트워크 디바이스의 IP만 초기화에 사용 (예시)
    ip_config {
      ipv4 {
        address = "${var.network_devices[0].ip_address}/24"
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

output "ip" {
  value = [for nd in var.network_devices : nd.ip_address]
}

output "name" {
  value = proxmox_virtual_environment_vm.this.name
} 