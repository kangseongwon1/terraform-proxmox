terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
  }
}

variable "name" { type = string }
variable "role" { type = string }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "disks" {
  type = list(object({
    size      = number
    interface = string
  }))
}
variable "network_devices" {
  type = list(object({
    bridge     = string
    ip_address = string
  }))
}
variable "template_vm_id" { type = number }

variable "proxmox_endpoint" { type = string }
variable "proxmox_username" { type = string }
variable "proxmox_password" { type = string }
variable "proxmox_node" { type = string }
variable "proxmox_datastore" { type = string }
variable "vm_username" { type = string }
variable "vm_password" { type = string }
variable "ssh_keys" { type = list(string) }
variable "gateway" { type = string }

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
      datastore_id = var.proxmox_datastore
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