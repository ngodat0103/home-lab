variable "proxmox_root_password" {
  type      = string
  sensitive = true
}
variable "proxmox_endpoint" {
  description = "ENDPOINT"
  type        = string
}
variable "influxdb_token" {
  type      = string
  sensitive = true
}