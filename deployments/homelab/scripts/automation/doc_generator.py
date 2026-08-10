#!/usr/bin/env python3
# ==============================================================================
# SRE AUTONOMOUS DOCUMENTATION GENERATOR (Autodox)
# Location: scripts/automation/doc_generator.py
# Uses Python standard libraries + Docker CLI JSON output to ensure 100%
# compatibility on Ubuntu Server without requiring external pip dependencies.
# ==============================================================================

import subprocess
import json
import socket
from datetime import datetime
from pathlib import Path

# Resolve absolute path to project root regardless of execution working directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
OUTPUT_FILE = PROJECT_ROOT / "docs" / "architecture" / "live_inventory.md"

def fetch_container_inventory():
    """Scans local Docker engine for all active containers using standard CLI JSON stream."""
    try:
        cmd = ["docker", "ps", "-a", "--format", "{{json .}}"]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[!] Error reading Docker runtime: {e}")
        return []

    containers = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        try:
            data = json.loads(line)
            containers.append({
                "name": data.get("Names", "N/A"),
                "image": data.get("Image", "N/A"),
                "status": data.get("Status", "N/A"),
                "ports": data.get("Ports", "None"),
                "state": data.get("State", "unknown")
            })
        except json.JSONDecodeError:
            continue
    return sorted(containers, key=lambda x: x["name"])

def generate_markdown(containers):
    """Compiles container telemetry into an enterprise GitHub-style Markdown report."""
    hostname = socket.gethostname()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    running_count = sum(1 for c in containers if c["state"].lower() == "running")

    md = [
        "# 📊 Autonomous SRE Live Cluster Inventory",
        "",
        "> **Notice:** This document is dynamically generated via automated inspection (`make autodox`).",
        f"> **Last Reconnaissance:** `{timestamp}` | **Control Node:** `{hostname}` | **Health:** `{running_count}/{len(containers)} Active`",
        "",
        "---",
        "",
        "## 🐳 Active Container Telemetry Table",
        "",
        "| Service Name | Base Docker Image | Runtime Status | Ingress / Port Mappings | Engine State |",
        "| :--- | :--- | :--- | :--- | :---: |"
    ]

    if not containers:
        md.append("| *No active containers detected* | `-` | `-` | `-` | 🔴 Offline |")
    else:
        for c in containers:
            state_icon = "🟢 Running" if c["state"].lower() == "running" else "🔴 Stopped"
            ports = c["ports"] if c["ports"] and c["ports"] != "" else "Internal Mesh / Host PID"
            md.append(f"| **`{c['name']}`** | `{c['image']}` | `{c['status']}` | `{ports}` | {state_icon} |")

    md.extend([
        "",
        "---",
        "",
        "## 🛠️ Autodocs Workflow Reconciliation",
        "To execute a manual regeneration of this architecture state file directly on the control machine:",
        "```bash",
        "# Trigger autonomous inspection engine",
        "make autodox",
        "```",
        ""
    ])

    return "\n".join(md)

def main():
    print("[*] Initiating Autonomous SRE Cluster Inspection...")
    containers = fetch_container_inventory()
    print(f"[*] Identified {len(containers)} container deployments across Docker daemon.")

    markdown_content = generate_markdown(containers)

    # Ensure output directory exists before writing
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(markdown_content, encoding="utf-8")

    print(f"[+] Reconciled infrastructure snapshot -> {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")

if __name__ == "__main__":
    main()
