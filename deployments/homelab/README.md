# Enterprise HomeLab & AI Cloud Infrastructure Monorepo

![Architecture Mode: Production & GitOps](https://img.shields.io/badge/Architecture-GitOps%20%2F%20IaC-blue?style=for-the-badge)
![OS: Ubuntu Server 24.04 LTS](https://img.shields.io/badge/Ubuntu%20Server-24.04%20LTS-e95420?style=for-the-badge&logo=ubuntu)
![Networking: Tailscale Mesh](https://img.shields.io/badge/Networking-Tailscale%20Mesh-orange?style=for-the-badge)
![CI Status](https://img.shields.io/github/actions/workflow/status/Ratthabhumi/Pi_Personal-Infrastructure/ci.yml?label=CI%20Linting&style=for-the-badge)
![CD Status](https://img.shields.io/github/actions/workflow/status/Ratthabhumi/Pi_Personal-Infrastructure/cd.yml?label=CD%20Deploy&style=for-the-badge)
![Project Status: Phase 1 Completed](https://img.shields.io/badge/Project%20Status-Phase%201%20(Docker)%20COMPLETED-success?style=for-the-badge)

## 📌 Vision & Philosophy
This repository serves as the **Single Source of Truth (SSOT)** for deploying, maintaining, monitoring, and scaling a personal cloud and Artificial Intelligence infrastructure. 

> 🎉 **Update (August 2026): PHASE 1 COMPLETED**
> The infrastructure has been successfully deployed as a highly optimized, lightweight Docker Compose stack, tailor-made to run efficiently on an Acer Aspire V13 (4GB RAM). Features include a Zero-Trust Tailscale network, UFW firewall, automated self-hosted CI/CD via GitHub Actions, and an expansive self-hosted application suite (Vaultwarden, AdGuard, Grafana). Phase 2 (Kubernetes & Local LLMs) is currently on hold pending a hardware upgrade (16GB+ RAM recommended).

We strictly abide by modern **DevOps, Site Reliability Engineering (SRE), and Platform Engineering** practices:
1. **Cattle, Not Pets**: Servers and configurations are completely modular, automated, and ephemeral. Should any compute instance fail, rebuilding it takes minutes via code.
2. **Zero-Trust Security**: No assumptions are made regarding local area networks; we enforce least-privilege, encrypted network overlays (Tailscale), and robust secrets management.
3. **Observability Driven Development (ODD)**: Every running container, service, and automation workflow explicitly outputs diagnostics, logs, and telemetry.
4. **Autonomous Agent Ready**: Structured clean to enable LLM agents to monitor, debug, self-heal, and dynamically document infrastructure states.

---

## 📂 Repository Directory Structure

```
homelab/
├── .github/                      # [CI/CD Layer] GitHub Actions for Linting (CI) & Deployment (CD)
├── ansible/                      # [OS / Provisioning Layer] Automation playbooks & host definitions
│   ├── inventory/                # Target machines list (homelab server & future AI desktop)
│   └── playbooks/                # Step-by-step OS harding, package & docker installers
├── terraform/                    # [External Infrastructure] Cloudflare DNS Management (Template)
├── docker/                       # [Compute / Container Layer] Monolithic Compose Configuration
│   ├── compose.yaml              # Unified declarative stack (Traefik, Observability, Vaultwarden, AdGuard, Kuma)
│   └── ai-platform/              # (Future) Local LLMs, Vector DBs, Worker nodes & Inference engines
├── kubernetes/                   # [Orchestration Layer] Future declarative K3s / GitOps Helm deployment
├── scripts/                      # Utility scripts (Automated Restic backups, Self-healing, Document bots)
├── docs/                         # Architecture designs, runbooks, post-mortems, and DR plans
│   ├── architecture/             # High-level system & networking diagrams
│   └── runbooks/                 # Step-by-step operating & crisis resolution procedures
├── Makefile                      # Developer Ergonomics: Unified commands (make bootstrap, make lint, etc.)
└── .gitignore                    # Iron-clad credential & state file exclusions
```

---

## 🚀 Quick Start (Developer Ergonomics)

We provide a specialized `Makefile` interface to streamline complex shell operations:

```bash
# Verify tooling, dependencies, and lint repository syntax
make check

# View active targets and running cluster status
make status

# Deploy core foundational Docker network and Traefik router on 'homelab'
make deploy-core
```

---

## 🔒 Security & Secrets Warning
**NEVER** commit plain-text passwords, SSH private keys, tokens, or `.env` files directly into this repository. All confidential parameters must rely on encrypted structures (such as SOPS, HashiCorp Vault, or strict Git-excluded templates).
