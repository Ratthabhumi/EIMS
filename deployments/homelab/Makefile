# ==============================================================================
# HOMELAB INFRASTRUCTURE AUTOMATION CONTROLLER (MAKEFILE)
# Single point of execution for Operations, SRE, and Maintenance Tasks
# ==============================================================================

.PHONY: help check status bootstrap apply-local deploy-core backup docs lint

# Default target executes help display
help:
	@echo "==================================================================="
	@echo "    HOME-LAB PLATFORM ENGINEERING & DEV-OPS MANAGEMENT INTERFACE   "
	@echo "==================================================================="
	@echo "Available commands:"
	@echo "  make check          - Check prerequisites (ansible, docker, git, tailscale)"
	@echo "  make bootstrap      - Run initial server hardening and package provisioning via Ansible"
	@echo "  make apply-local    - Run autonomous local GitOps bootstrap directly ON the server"
	@echo "  make deploy-prod    - Deploy unified Production Stack via Ansible IaC"
	@echo "  make rebuild-server - Full bare-metal to production rebuild (OS + Docker)"
	@echo "  make lint           - Validate YAML, scripts, and Markdown styling across repo"
	@echo "  make docs           - Automatically re-generate systems inventory markdown"
	@echo "  make tf-init        - Initialize Terraform providers"
	@echo "  make tf-plan        - Preview Cloudflare DNS changes via Terraform"
	@echo "  make tf-apply       - Deploy DNS changes to Cloudflare via Terraform"
	@echo "  make ssh            - Quick direct SSH connection into mew@homelab via Tailscale"
	@echo "==================================================================="

ssh:
	@ssh mew@homelab

check:
	@echo "[*] Checking engineering tooling on local workstation..."
	@which git >/dev/null && echo "  [OK] Git installed." || echo "  [FAIL] Git missing!"
	@which ssh >/dev/null && echo "  [OK] SSH installed." || echo "  [FAIL] SSH missing!"
	@echo "[*] Workspace structural checks complete."

bootstrap:
	@echo "[*] Executing zero-touch OS bootstrap via Ansible..."
	ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/00_bootstrap_server.yml --vault-password-file .vault_pass

apply-local:
	@echo "[*] Executing Local GitOps self-provisioning script..."
	bash scripts/automation/bootstrap_local.sh

deploy-prod:
	@echo "[*] Deploying Unified Production Stack to /data/docker (Windows Compatible)..."
	ssh mew@homelab 'sudo mkdir -p /data/docker'
	scp -r docker/* mew@homelab:/data/docker/
	ssh mew@homelab 'cd /data/docker && docker compose up -d --remove-orphans'

rebuild-server:
	@echo "[*] 🚨 INITIATING FULL SERVER REBUILD (OS + Application Stack)..."
	@echo "    Ensure you run this from an environment with Ansible installed (e.g., WSL, Linux, or on the server itself via make apply-local)"
	ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/00_bootstrap_server.yml
	ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/01_deploy_homelab.yml
	@echo "[*] ✅ REBUILD COMPLETE! System is fully restored and ready."

# ------------------------------------------------------------------------------
# TERRAFORM IAC (CLOUDFLARE DNS MANAGEMENT)
# ------------------------------------------------------------------------------
tf-init:
	@echo "[*] Initializing Terraform providers..."
	cd terraform/cloudflare && terraform init

tf-plan:
	@echo "[*] Planning Terraform infrastructure changes..."
	cd terraform/cloudflare && terraform plan -var-file=".env.tfvars"

tf-apply:
	@echo "[*] 🚀 APPLYING TERRAFORM CHANGES TO CLOUDFLARE..."
	cd terraform/cloudflare && terraform apply -var-file=".env.tfvars"

# ------------------------------------------------------------------------------
# LOCAL SERVER CONTAINER COMMANDS (Run directly within mew@homelab terminal)
# ------------------------------------------------------------------------------
stack-up:
	@echo "[*] Launching Production Stack..."
	cd /data/docker && docker compose up -d --remove-orphans

stack-down:
	@echo "[*] Shutting down Production Stack..."
	cd /data/docker && docker compose down

# ------------------------------------------------------------------------------
# AUTONOMOUS AUTOMATION & SELF-DOCUMENTING AI COMMANDS (Sprint 4)
# ------------------------------------------------------------------------------
autodox:
	@echo "[*] Launching Autonomous SRE Documentation Engine..."
	@python3 scripts/automation/doc_generator.py
	@echo "[*] Complete! Check docs/architecture/live_inventory.md for results."

backup:
	@echo "[*] Launching Autonomous SRE Snapshot & Recovery Engine..."
	@bash scripts/automation/auto_backup.sh
