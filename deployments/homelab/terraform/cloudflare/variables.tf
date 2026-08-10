variable "cloudflare_api_token" {
  description = "API Token for Cloudflare (Requires Edit DNS permissions)"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "The Zone ID of your domain on Cloudflare"
  type        = string
}

variable "domain_name" {
  description = "Your primary domain name (e.g., example.com)"
  type        = string
  default     = "example.com"
}

variable "public_ip" {
  description = "Your Home Public IP address (if using standard port forwarding)"
  type        = string
  default     = "1.2.3.4"
}

variable "cloudflare_tunnel_id" {
  description = "Your Cloudflare Tunnel ID (if using Zero Trust Tunnels)"
  type        = string
  default     = "xxxx-xxxx-xxxx-xxxx"
}
