#!/usr/bin/env bash
# ==============================================================================
# LOCAL GITOPS SELF-BOOTSTRAPPING & RECONCILIATION ENGINE
# Designed for execution directly inside mew@homelab via terminal or cron
# ==============================================================================

set -e # Exit immediately on any undocumented execution failure

echo "==================================================================="
echo "   🛡️ HOMELAB SELF-PROVISIONING & GITOPS RECONCILIATION ENGINE     "
echo "==================================================================="

# 1. Ensure core Python, Ansible & Make automation runtimes exist natively on Ubuntu
echo "[1/4] Checking OS prerequisite packages (Git, Make & Ansible)..."
if ! command -v ansible-playbook &> /dev/null || ! command -v make &> /dev/null; then
    echo "  -> Prerequisites missing! Initializing localized package provisioning..."
    sudo apt-get update -y
    sudo apt-get install -y git make build-essential ansible python3-apt software-properties-common
    echo "  -> [OK] Automation engine & tooling successfully injected."
else
    echo "  -> [OK] Automation tooling (Ansible & Make) detected natively."
fi

# 2. Synchronize current working state with Remote Git Repository (Optional if Git URL exists)
echo "[2/4] Checking git repository sync status..."
if git rev-parse --is-inside-work-tree &> /dev/null; then
    if git remote get-url origin &> /dev/null; then
        echo "  -> Pulling latest infrastructure declaration state from remote Git origin..."
        git pull origin main || git pull origin master || echo "  -> [Notice] Using current local branch filesystem state."
    else
        echo "  -> [Notice] No remote origin attached yet. Relying on current folder contents."
    fi
fi

# 3. Execute Ansible locally to configure Ubuntu OS and Docker Engine
echo "[3/4] Launching local Ansible Playbook for OS Configuration..."

# Automatically detect if sudo requires password confirmation (-K flag)
if sudo -n true 2>/dev/null; then
    SUDO_FLAG=""
    echo "  -> [OK] Sudo privileges active without manual password prompt."
else
    SUDO_FLAG="-K"
    echo "  -> [Notice] Sudo authentication required. Please enter user password when prompted for 'BECOME password'."
fi

ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/00_bootstrap_server.yml \
    --connection=local \
    --limit=homelab \
    ${SUDO_FLAG} \
    --extra-vars="ansible_python_interpreter=/usr/bin/python3"

echo "[4/4] Launching local Ansible Playbook for Application Deployment..."
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/01_deploy_homelab.yml \
    --connection=local \
    --limit=homelab \
    ${SUDO_FLAG} \
    --extra-vars="ansible_python_interpreter=/usr/bin/python3"

echo "==================================================================="
echo "   ✅ HOMELAB RECONCILIATION COMPLETE: ALL SYSTEMS NOMINAL         "
echo "==================================================================="
