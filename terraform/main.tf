# Vault에서 시크릿 데이터 가져오기
data "vault_generic_secret" "proxmox" {
  path = "secret/proxmox"
}

data "vault_generic_secret" "vm" {
  path = "secret/vm"
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

  # Vault에서 민감한 정보 가져오기
  proxmox_endpoint  = var.proxmox_endpoint
  proxmox_username  = var.proxmox_username
  proxmox_password  = data.vault_generic_secret.proxmox.data["password"]
  proxmox_node      = var.proxmox_node
  vm_username       = each.value.vm_username != null ? each.value.vm_username : data.vault_generic_secret.vm.data["username"]
  vm_password       = each.value.vm_password != null ? each.value.vm_password : data.vault_generic_secret.vm.data["password"]
  ssh_keys          = [var.ssh_keys]
}