module "server" {
  source = "./modules/server"
  for_each = var.servers

  name           = each.value.name
  role           = each.value.role
  cpu            = each.value.cpu
  memory         = each.value.memory
  disks          = each.value.disks
  network_devices = each.value.network_devices
  template_vm_id = each.value.template_vm_id

  proxmox_endpoint  = var.proxmox_endpoint
  proxmox_username  = var.proxmox_username
  proxmox_password  = var.proxmox_password
  proxmox_node      = var.proxmox_node
  vm_username       = var.vm_username
  vm_password       = var.vm_password
  ssh_keys          = var.ssh_keys
  gateway           = var.gateway
}

