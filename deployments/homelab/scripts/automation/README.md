# Automation & Maintenance Scripts

This module contains autonomous utility scripts designed to keep infrastructure resilient without requiring manual admin interventions.

## Future Automation Scripts
1. **`auto_backup.sh` (Restic / Borg Backup Engine)**: Encrypted incremental backups of Docker volumes and Ansible configurations sent nightly to external drives or cloud object storage.
2. **`doc_generator.py` (Live Markdown Autodoc)**: Python tool utilizing Docker SDK and Ollama API to scan running containers, extract open port mappings, and autogenerate live Markdown summary reports right into our Git `docs/` repository.
3. **`health_remediator.sh` (Self-Healing Cron)**: Detects stalled container networks or memory leaks and cleanly gracefully restarts non-responsive containers before escalating alerts.
