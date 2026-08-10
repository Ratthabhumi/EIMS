# Workspace Rules

## GitOps Workflow (Single Source of Truth)
- All infrastructure changes, deployment files (`compose.yaml`), and configurations MUST be written on the local Windows PC (VS Code) first.
- To deploy to the homelab server, you MUST commit and push the changes to GitHub (`git add .`, `git commit`, `git push`).
- Then, access the homelab server via SSH, pull the latest changes (`git pull origin main`), and apply them locally.
- NEVER modify, create, or manually copy files directly on the homelab server without passing them through the Git repository first. This is to prevent state desynchronization and "not a git repository" errors.

## Observability First (ODD)
- Whenever a new application, container, or service is added to the infrastructure (e.g., in `compose.yaml`), you MUST remind the user to add a monitor for it in Uptime Kuma.
- Ensure every service has its internal URL (e.g., `http://service-name:port`) actively monitored for uptime and alerting.
