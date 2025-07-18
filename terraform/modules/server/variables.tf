variable "disks" {
  description = "List of disks"
  type = list(object({
    size         = number
    interface    = string
    datastore_id = string
  }))
} 