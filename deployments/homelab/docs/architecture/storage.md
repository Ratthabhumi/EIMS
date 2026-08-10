# Homelab Storage Architecture

This document outlines the physical and logical storage topology for the Homelab. The architecture follows Enterprise SRE best practices by implementing **Storage Tiering** (separating OS, Cold Data, and Hot Data).

## 💽 Storage Tiers

### 1. OS & Core System (สมองกล)
* **Drive:** `/dev/sdb` (256GB M.2 NVMe/SATA SSD)
* **Mount Point:** `/` (Root)
* **Role:** Operating System (Ubuntu 24.04), Base Docker Engine, System Logs.
* **Why:** Ensures the server boots instantly, system updates are fast, and core OS operations remain stable without being bottlenecked by heavy application I/O.

### 2. Cold Storage (สายแบก)
* **Drive:** `/dev/sda` (1TB WDC HDD)
* **Mount Point:** `/data`
* **Format:** `ext4`
* **Role:** High-capacity storage for large, infrequently accessed files, or sequential read/write operations.
* **Use Cases:**
  - Media Streaming (Jellyfin/Plex movies)
  - Personal Cloud Storage (Nextcloud documents/photos)
  - Long-term Backups (Restic/Tar archives)
  - Centralized Logging Archives (Loki long-term storage)

### 3. Hot Storage (สายซิ่ง)
* **Drive:** `/dev/sdc` (500GB SSD)
* **Mount Point:** `/ssd-data`
* **Format:** `ext4`
* **Role:** High IOPS (Input/Output Operations Per Second) storage for latency-sensitive applications.
* **Use Cases:**
  - Relational Databases (PostgreSQL, MySQL for Nextcloud/Gitea)
  - Key-Value Stores (Redis caching)
  - Kubernetes / K3s (etcd state, local-path provisioner)
  - CI/CD Runners (GitHub Actions / GitLab Runner build directories)
  - Vector Databases (Milvus, Qdrant for Future AI/RAG workloads)

## 📌 Usage Policy
When deploying a new Docker Compose stack or Kubernetes Pod, developers MUST explicitly define the volume binding based on the application's I/O profile:
- Bound to `/data/...` if it requires massive storage.
- Bound to `/ssd-data/...` if it requires high-speed read/write.
