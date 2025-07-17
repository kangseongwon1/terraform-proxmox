variable "servers" {
  description = "서버 목록"
  type = map(object({
    name            = string
    role            = string
    cpu             = number
    memory          = number
    disks           = list(object({
      size      = number
      interface = string
    }))
    network_devices = list(object({
      bridge     = string
      ip_address = string
    }))
    template_vm_id = number
  }))
}

variable "proxmox_endpoint" { type = string }
variable "proxmox_username" { type = string }
variable "proxmox_password" { type = string }
variable "proxmox_node" { type = string }
variable "proxmox_datastore" { type = string }
variable "vm_username" { type = string }
variable "vm_password" { type = string }
variable "ssh_keys" { type = list(string) }
variable "gateway" { type = string } 