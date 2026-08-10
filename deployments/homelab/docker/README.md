# 🏢 Homelab Production Environment

## 🏗️ Architecture
This server follows an enterprise DevOps pattern. All Docker configurations and volatile data are isolated to the `/data` HDD.
- **Edge Routing**: Traefik handles reverse-proxying and SSL termination via Tailscale.
- **Observability**: VictoriaMetrics, Grafana, and Node-Exporter provide high-performance telemetry.
- **Management**: Portainer offers a fallback web GUI. Watchtower provides autonomous patching.

## 📂 Folder Structure
```text
/data/
├── backups/           # Automated backups (cron/scripts)
└── docker/
    ├── compose.yaml   # Unified production stack definition
    ├── .env           # Environment variables and secrets
    └── <service>/     # Service-specific data, configs, and logs
```

## 🚀 Commands
Navigate to this directory: `cd /data/docker`
- **Start Stack**: `docker compose up -d`
- **Stop Stack**: `docker compose down`
- **View Logs**: `docker compose logs -f <service_name>`
- **Check Status**: `docker compose ps`

## 🔐 Security Enhancements
- All non-essential capabilities have been dropped (`cap_drop: - ALL`).
- Base containers enforce read-only filesystems (`read_only: true`).
- Internal communications happen over isolated `internal` bridge network.

## 💾 Backup & Restore
- Backups are automatically archived to `/data/backups/`.
- To restore, extract the `.tar.gz` archive directly over the `/data/docker/` folder and run `docker compose up -d`.
