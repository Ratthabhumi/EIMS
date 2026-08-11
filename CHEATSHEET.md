# EIMS Developer Cheatsheet

Welcome to the **Enterprise Infrastructure Management System (EIMS)**. This guide provides quick commands for running the infrastructure, backend, frontend, and simulating telemetry events.

---

## 🏗️ 1. Start Infrastructure (Databases, Cache, Observability)

Before starting any code, ensure all backing services (PostgreSQL, PgBouncer, Redis, MinIO, Prometheus, Grafana, Loki) are running.

```powershell
# Navigate to project root
cd C:\Users\Ratthabhumi\Desktop\EIMS

# Start all infrastructure containers in detached mode
docker-compose up -d

# Check the status of the containers
docker-compose ps
```

- **PgBouncer / PostgreSQL**: `localhost:6432` / `localhost:5432`
- **Redis**: `localhost:6379`
- **MinIO S3**: `localhost:9000` (Console: `localhost:9001`)
- **Prometheus**: `localhost:9090`
- **Grafana**: `localhost:3000`

---

## 🐍 2. Start Backend API (FastAPI)

The backend handles the Asset Registry, Telemetry Ingestion, and WebSocket streams. It uses `uvicorn` as the ASGI server.

```powershell
# Open a NEW terminal
cd C:\Users\Ratthabhumi\Desktop\EIMS

# Activate the Virtual Environment
.\venv\Scripts\activate

# Initialize / Upgrade the Database Schema (Important for fresh starts!)
alembic upgrade head

# Start the FastAPI server with auto-reload (Dev Mode)
python -m uvicorn backend.main:app --reload
```
- **Backend API URL**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

*(Note: Keep this terminal open and running)*

---

## ⚛️ 3. Start Frontend Dashboard (Next.js)

The Operational Dashboard provides a real-time UI to monitor registered endpoints and security alerts.

```powershell
# Open a NEW terminal
cd C:\Users\Ratthabhumi\Desktop\EIMS\clients\dashboard

# Start the Next.js development server
npm run dev
```
- **Dashboard URL**: [http://localhost:3001](http://localhost:3001)

*(Note: Keep this terminal open and running)*

---

## 📡 4. Simulating Telemetry (Discovery & Alerts)

EIMS is event-driven. To see the dashboard populate with data, you need to simulate agent data.

### Option A: Use the Agent Simulator Script
We have a Python simulator that continuously generates mock telemetry and pushes it to the backend.

```powershell
# Open a NEW terminal
cd C:\Users\Ratthabhumi\Desktop\EIMS
.\venv\Scripts\activate

# Run the agent simulator
python simulate_traffic.py
```

### Option B: Manual cURL Commands (PowerShell)

**1. Register a new Endpoint (Discovery Event):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/telemetry/heartbeat" -Method Post -Headers @{"Content-Type"="application/json"; "Authorization"="Bearer EIMS-CORE-LAW-5"; "X-Client-Cert-Fingerprint"="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"} -Body '{"hostname": "SERVER-01", "ip_address": "192.168.1.100", "os_version": "Windows Server 2022", "cpu_cores": 16, "total_memory_mb": 65536, "active_users": ["Administrator"], "running_processes": ["svchost.exe", "explorer.exe"]}'
```

**2. Send a Security Alert (Winlog Event):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/telemetry/winlog" -Method Post -Headers @{"Content-Type"="application/json"; "Authorization"="Bearer EIMS-CORE-LAW-5"; "X-Client-Cert-Fingerprint"="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"} -Body '{"occurrence_time": "2026-08-10T12:00:00Z", "event_id": 4625, "severity": "Critical", "event_channel": "Security", "metadata": {"target_user_name": "admin", "workstation_name": "SERVER-01", "source_network_ip": "10.0.0.5"}}'
```

### Option C: Import USB Auditor Report
You can import an offline JSON payload containing hardware and security specs into the Endpoint Auditor.
```powershell
# Using curl to upload the generated USB auditor report
curl.exe -v -F "file=@C:\Users\Ratthabhumi\Desktop\EIMS\clients\usb_auditor\reports\report_name.json" http://localhost:8000/api/v1/assets/import-report
```
*Note: You can also use the **Import Offline Report** button in the Endpoint Auditor UI to upload via the browser.*

---

## 🛑 5. Shutting Down & Cleanup

When you are done testing, you can gracefully shut down all services.

```powershell
# Stop all docker-compose infrastructure
docker-compose down

# (Optional) Wipe all volumes/data to start fresh next time
docker-compose down -v
```

For the Frontend and Backend terminals, simply click into the terminal and press `Ctrl + C` to stop the running process.
