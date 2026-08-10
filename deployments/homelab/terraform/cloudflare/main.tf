terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# ------------------------------------------------------------------------------
# DNS RECORDS
# ------------------------------------------------------------------------------

# Example A Record: Pointing the root domain to your public IP (if port forwarding)
# resource "cloudflare_record" "root_a" {
#   zone_id = var.cloudflare_zone_id
#   name    = "@"
#   value   = var.public_ip
#   type    = "A"
#   proxied = true
# }

# Example CNAME: Catch-all subdomain pointing to the root (for Traefik)
# resource "cloudflare_record" "wildcard" {
#   zone_id = var.cloudflare_zone_id
#   name    = "*"
#   value   = var.domain_name
#   type    = "CNAME"
#   proxied = true
# }

# Example CNAME: Cloudflare Tunnel (Zero Trust) instead of port forwarding
# resource "cloudflare_record" "tunnel" {
#   zone_id = var.cloudflare_zone_id
#   name    = "auth"
#   value   = "${var.cloudflare_tunnel_id}.cfargotunnel.com"
#   type    = "CNAME"
#   proxied = true
# }
