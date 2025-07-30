# Vault에서 시크릿 데이터 가져오기
data "vault_generic_secret" "proxmox" {
  path = "secret/proxmox"
}

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
  proxmox_password  = data.vault_generic_secret.proxmox.data["proxmox_password"]
  proxmox_node      = var.proxmox_node
  vm_username       = each.value.vm_username != null ? each.value.vm_username : var.vm_username
  vm_password       = each.value.vm_password != null ? each.value.vm_password : data.vault_generic_secret.proxmox.data["vm_password"]
  ssh_keys          = [data.vault_generic_secret.proxmox.data["ssh_public_key"]]
}


