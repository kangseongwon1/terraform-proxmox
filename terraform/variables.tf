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
      datastore_id = string
    }))
    network_devices = list(object({
      bridge     = string
      ip_address = string
      subnet     = string
      gateway    = string
    }))
    template_vm_id = number
  }))
}



variable "vault_token" {
  description = "Vault token for authentication"
  type        = string
  sensitive   = true
}

variable "proxmox_endpoint" { type = string }
variable "proxmox_username" { type = string }
variable "proxmox_node" { type = string }
variable "vm_username" { type = string }
