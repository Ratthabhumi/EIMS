#!/usr/bin/env bash
# ==============================================================================
# AUTONOMOUS SRE SNAPSHOT & RECOVERY ENGINE (Sprint 5)
# Location: scripts/automation/auto_backup.sh
# Performs live archiving of the /data/docker production directory
# ==============================================================================

set -e

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_ROOT="/data/backups"
SOURCE_DIR="/data/docker"
RETENTION_DAYS=7

echo "==================================================================="
echo "   🛡️ HOMELAB PRODUCTION DATA BACKUP ENGINE                      "
echo "==================================================================="

# Ensure backup directory exists
sudo mkdir -p "${BACKUP_ROOT}"

echo "[1/3] Archiving production Docker state (/data/docker)..."
# We exclude logs to save space
sudo tar --exclude='*/logs/*' -czvf "${BACKUP_ROOT}/homelab_backup_${TIMESTAMP}.tar.gz" -C "/data" "docker" > /dev/null

echo "[2/3] Executing SRE retention governance..."
echo "  -> Pruning historical archives older than ${RETENTION_DAYS} days..."
sudo find "${BACKUP_ROOT}" -name "homelab_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

FINAL_SIZE=$(du -sh "${BACKUP_ROOT}/homelab_backup_${TIMESTAMP}.tar.gz" | awk '{print $1}')
echo "==================================================================="
echo "   ✅ BACKUP SUCCESSFUL | Archive Size: ${FINAL_SIZE}             "
echo "   📁 Path: ${BACKUP_ROOT}/homelab_backup_${TIMESTAMP}.tar.gz     "
echo "==================================================================="
