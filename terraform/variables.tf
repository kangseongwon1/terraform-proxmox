variable "servers" {
  description = "서버 목록"
  type = map(object({
    name            = string
    role            = string
    cpu             = number
    memory          = number
    disks           = list(object({
      size         = number
      interface    = string
      datastore_id = string
      disk_type    = optional(string, "hdd")  # "hdd", "ssd", "nvme"
      file_format  = optional(string, "auto") # "auto", "raw", "qcow2", "vmdk"
    }))
    network_devices = list(object({
      bridge     = string
      ip_address = string
      subnet     = string
      gateway    = string
    }))
    template_vm_id = number
    vm_username    = optional(string)  # 서버별 사용자명 (기본값은 전역 vm_username 사용)
    vm_password    = optional(string)  # 서버별 비밀번호 (기본값은 전역 vm_password 사용)
  }))
}

# Vault 설정
variable "vault_address" {
  description = "Vault server address"
  type        = string
  default     = "http://127.0.0.1:8200"
}

variable "vault_token" {
  description = "Vault token for authentication"
  type        = string
  sensitive   = true
}

# Proxmox 설정 (Vault에서 가져올 예정)
variable "proxmox_endpoint" { type = string }
variable "proxmox_username" { type = string }
variable "proxmox_password" { 
  type = string
  sensitive = true
}
variable "proxmox_node" { type = string }

# VM 설정 (Vault에서 가져올 예정)
variable "vm_username" { type = string }
variable "vm_password" { 
  type = string
  sensitive = true
}
variable "ssh_keys" { type = string }