variable "cloudflare_api_token" {
  type        = string
  description = "The Cloudflare API token"
  sensitive   = true
}
variable "ddns_content" {
  type        = string
  description = "The content of the DDNS record"
  sensitive   = true
}