
variable "proxmox_endpoint" {
  description = "Proxmox VE endpoint"
  type        = string
}

variable "proxmox_username" {
  description = "Proxmox VE username"
  type        = string
}

variable "proxmox_password" {
  description = "Proxmox VE password"
  type        = string
}

variable "proxmox_node" {
  description = "Proxmox VE node name"
  type        = string
}

variable "proxmox_datastore" {
  description = "Proxmox VE datastore"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "vm_username" {
  description = "VM username"
  type        = string
}

variable "vm_password" {
  description = "VM password"
  type        = string
}

variable "ssh_keys" {
  description = "ssh keys"
  type        = list(string)
}

variable "template_vm_id" {
  description = "Template VM ID"
  type        = number
}

variable "ip_addresses" {
  description = "IP addresses for VMs"
  type        = list(string)
}

variable "gateway" {
  description = "Gateway IP"
  type        = string
}
