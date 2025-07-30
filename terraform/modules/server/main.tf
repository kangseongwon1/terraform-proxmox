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
      file_format  = disk.value.file_format == "auto" ? (
        disk.value.disk_type == "ssd" || disk.value.disk_type == "nvme" ? "raw" : "qcow2"
      ) : disk.value.file_format
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
    # 각 네트워크 디바이스별로 ip/subnet/gateway 적용
    dynamic "ip_config" {
      for_each = var.network_devices
      content {
        ipv4 {
          address = "${ip_config.value.ip_address}/${ip_config.value.subnet}"
          gateway = ip_config.value.gateway
        }
      }
    }
  }

  operating_system {
    type = "l26"
  }

  clone {
    vm_id = var.template_vm_id
  }

  lifecycle {
    ignore_changes = [
      disk[*].file_format
    ]
  }
}

output "ip" {
  value = [for nd in var.network_devices : nd.ip_address]
}

output "name" {
  value = proxmox_virtual_environment_vm.this.name
} 