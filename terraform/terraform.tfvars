servers = {
  web1 = {
    name            = "web-1"
    role            = "web"
    cpu             = 2
    memory          = 2048
    disks = [
      { size = 20, interface = "scsi0" },
      { size = 50, interface = "scsi1" }
    ]
    network_devices = [
      { bridge = "vmbr0", ip_address = "192.168.0.101" },
      { bridge = "vmbr1", ip_address = "10.0.0.101" }
    ]
    template_vm_id = 9000
  }
  db1 = {
    name            = "db-1"
    role            = "db"
    cpu             = 4
    memory          = 4096
    disks = [
      { size = 100, interface = "scsi0" }
    ]
    network_devices = [
      { bridge = "vmbr0", ip_address = "192.168.0.201" }
    ]
    template_vm_id = 8000
  }
}

proxmox_endpoint  = "https://prox.dmcmedia.co.kr:8006"
proxmox_username  = "root@pam"
proxmox_password  = "dmc1234)(*&"
proxmox_node      = "prox"
proxmox_datastore = "local-lvm"
vm_username       = "ubuntu"
vm_password       = "ubuntu123"
ssh_keys          = ["ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC5YjxN0N+Xbuv3RJwcUxBXqwlueHXNMidIXHagPO6xXovqo/ypq1EHMKJKXKQND1G2pACX1EIDIF/6gLFVOAMn1tzeiMttn4UskHLGz+oM7PMS3uFnVIN/uBQNDlYxKcyiYvdrP+mxiQsa7lyuxYfcAySoFx64l+giAGppKNuDPBz2SPY87I+V06/+eo6Rnd2XHmJvqpVclEwezZ+WQfkFYRKxxnWAWl2m6apdio2kPyRxEwCP19moyVlQhm5b+IAoktHgaDYFr1YrQ9J/QCSVYkiG3IDCOwI4k+O0MaV5Uelj0NaTDv4Pb2Dv2/86VPTrKOucSs8o0JqboHjKtfEKfmDym25YnTaF+tXGzPkAk8b3l7oESC2SFvPTO3lyiE84dGniQNtJg9YwUb5NxynOk9yydd0L3E6ikfTpdokwjd49GgE/KxkcZjhrxLwUMyJ0SLf/vqaRc9GmTn7JTeqnObMhArXjHuTXmfcL2Q9DYEREVfioWLgu7CPxfdS2+fc= dmc_dev@localhost.localdomain"]
gateway           = "192.168.0.1" 