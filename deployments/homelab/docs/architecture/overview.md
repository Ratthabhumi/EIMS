# System Architecture Overview: Zero-Trust Personal Cloud & AI Platform

## 1. Top-Level Philosophy
Our engineering goals mirror top-tier corporate platform designs (Google, Cloudflare, Netflix):
* **Zero-Trust Ingress**: Every communication layer assumes an untrusted underlying transport. We utilize Tailscale WireGuard mesh networking for cross-device communications.
* **Declarative Infrastructure**: Infrastructure state is declared within this repository via YAML (Ansible / Compose / Kubernetes Manifests) rather than imperative shell executions.

## 2. Network Topology & Routing Map

```
[ External Internet ]
         │ (No open port forwarding required on router - Zero-Trust Shield)
         ▼
[ Tailscale WireGuard Overlay Mesh Network ]
         │
         ├──► [ mATX AI Server (~60k THB - GPU Node) ] (Future)
         │        ├── 100.x.x.101 : Ollama AI API (Port 11434)
         │        └── 100.x.x.101 : GPU Compute & Vector DBs
         │
         └──► [ Acer Aspire V13 ('homelab' - Control & Edge Server) ] (24/7 Live)
                  ├── 100.x.x.10 : SSH Administration Port (OpenSSH)
                  ├── Traefik Edge Router (Internal HTTPS Termination)
                  │       ├── vaultwarden.homelab.ts.net ---> Port 80 (Password Vault)
                  │       ├── adguard.homelab.ts.net   ---> Port 80 (DNS/Adblock)
                  │       ├── grafana.homelab.ts.net   ---> Port 3000 (Grafana UI)
                  │       └── portainer.homelab.ts.net ---> Port 9000 (Container UI)
                  │
                  └── Core Services: Uptime Kuma (Alerting), VictoriaMetrics, Watchtower
```

## 3. Hardware Responsibility Breakdown

| Machine Name | Hardware Specs | Operating System | Primary Responsibility | Availability |
| :--- | :--- | :--- | :--- | :--- |
| **`homelab`** | Acer Aspire V13 | Ubuntu 24.04 LTS | Core Ingress, SRE Observability, DNS, Automation Control Plane | 24 / 7 Always On |
| **`daily-pc`** | Dell All-In-One | Windows PC | Daily Workstation, VS Code IDE, SSH terminal, local Web UI access | On Demand |
| **`ai-server`** | mATX Custom (TBD) | Proxmox / Bare Metal Linux | LLM GPU Inference, Vector Storage, Autonomous AI Agents, VMs | On Demand / Heavy |
