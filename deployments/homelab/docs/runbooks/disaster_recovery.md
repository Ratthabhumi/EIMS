# SRE Runbook: Disaster Recovery & Server Reconstitution (Bare-Metal Restore)

> **Severity Level:** Critical / Fatal  
> **Scenario:** The primary control plane server (`mew@homelab`) has experienced complete hard drive failure, OS corruption, or catastrophe.

---

## 🛑 Step 0: Don't Panic & Verify State
1. Check physical power and network indicator LEDs on the Acer Aspire V13.
2. Verify if the instance is reachable via standard IP rather than DNS:
   ```bash
   ping <local-router-ip>
   ping homelab
   ```

---

## 🛠️ Step 1: Operating System Re-provisioning
If the hardware or file system is corrupted:
1. Re-install clean **Ubuntu Server 24.04 LTS** onto the target machine.
2. During setup, configure initial system username as `mew` and establish your standard SSH identity key.
3. Install and connect Tailscale onto the bare-metal machine:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
4. Verify the new Tailscale IP matches or registers correctly inside your SSH configuration on your Dell Workstation.

---

## ⚡ Step 2: Zero-Touch IaC Restoration (Ansible)
Instead of manually reinstalling packages, execute our automated infrastructure blueprint from your workstation:
```bash
# Navigate to workspace on your main desktop
cd C:/Users/MewMew/Desktop/Co-op/Pi_Personal-Infrastructure

# Execute base operating system bootstrap & hardening
make bootstrap
```
*This playbook automatically rebuilds: Docker engine, firewall rules (UFW), log rotators, NTP synchronizers, and sysctl network optimizations.*

---

## 📦 Step 3: Service Layer Ignition
Once Ansible completes its provisioning verification:
```bash
# Restore Core routing and proxy layers
make deploy-core

# Restore Site Reliability & Telemetry engines
make deploy-obs
```

---

## ✅ Step 4: Verification Checklist
- [ ] SSH accessible via clean alias: `ssh mew@homelab`
- [ ] Docker service active without crashing containers: `docker ps -a`
- [ ] Traefik dashboard displaying clear routing tables without TLS certificate warnings
- [ ] Prometheus scraping targets actively reporting with `UP` health status
