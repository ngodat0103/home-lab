variable "proxmox_username" {
  description = "Proxmox API username (e.g. root@pam)"
  type        = string
}

variable "proxmox_password" {
  description = "Proxmox API password"
  type        = string
  sensitive   = true
}
variable "proxmox_endpoint" {
  description = "ENDPOINT"
  type        = string
}