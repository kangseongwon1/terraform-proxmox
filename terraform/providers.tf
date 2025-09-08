terraform {
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~> 3.0"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox_endpoint
  username = var.proxmox_username
  password = var.proxmox_password
  insecure = true

  ssh {
    agent = true
  }
}

provider "vault" {
  address = var.vault_address
  token   = var.vault_token
}

# Vault에서 민감한 정보 가져오기
data "vault_generic_secret" "proxmox_credentials" {
  path = "secret/proxmox"
}

data "vault_generic_secret" "vm_credentials" {
  path = "secret/vm"
}