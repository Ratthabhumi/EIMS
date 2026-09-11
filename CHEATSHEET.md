# EIMS Developer Cheatsheet

Welcome to the **Enterprise Infrastructure Management System (EIMS)**. This guide provides quick commands for running the infrastructure, backend, frontend, and simulating telemetry events.

---

## 🏗️ 1. Start Infrastructure (Databases, Cache, Observability)

Before starting any code, ensure all backing services (PostgreSQL, PgBouncer, Redis, MinIO, Prometheus, Grafana, Loki) are running.

```powershell
# Navigate to repository root
cd <repository-root>

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

The backend handles the Asset Registry, Telemetry Ingestion, Search, Analyzer, and WebSocket streams. It uses `uvicorn` as the ASGI server.

```powershell
# Open a NEW terminal at repository root
cd <repository-root>

# Activate the Virtual Environment
.\venv\Scripts\activate

# Initialize / Upgrade the Database Schema (Important for fresh starts!)
alembic upgrade head

# Start the FastAPI server with auto-reload (Dev Mode)
python -m uvicorn backend.main:app --reload
```
- **Backend API URL**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Authentication Modes (`EIMS_AUTH_MODE`)
- **Demo Mode** (Default): `EIMS_AUTH_MODE=demo` in `.env`. Dashboard navigation, log analysis, and evaluations work immediately without a login gate.
- **Secure Mode**: `EIMS_AUTH_MODE=secure`. Protected routes enforce JWT verification; admin write operations require `role == "admin"` or `ADMIN_TOKEN`.

*(Note: Keep this terminal open and running)*

---

## ⚛️ 3. Start Frontend Dashboard (Next.js)

The Operational Dashboard provides a real-time UI to monitor registered endpoints, security alerts, and operational tools.

```powershell
# Open a NEW terminal
cd clients/dashboard

# Start the Next.js development server
npm run dev
```
- **Dashboard URL**: [http://localhost:3001](http://localhost:3001)
- **Universal Search (Command Center)**: Press `Ctrl+K` or `Cmd+K` anywhere in the dashboard to search navigation routes, assets, audit trails, event logs, USB evidence, OCR records, and analysis history.

*(Note: Keep this terminal open and running)*

---

## 📡 4. Simulating Telemetry (Discovery & Alerts)

EIMS is event-driven. To see the dashboard populate with data, you can simulate agent data or upload operational reports.

### Option A: Use the Agent Simulator Script
Continuous mock telemetry generator:

```powershell
# Open a NEW terminal at repository root
cd <repository-root>
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
You can import an offline JSON payload containing hardware and security specs into the USB Auditor:
```powershell
# Using curl to upload a USB auditor report
curl.exe -v -F "file=@clients/usb_auditor/reports/sample_report.json" http://localhost:8000/api/v1/assets/import-report
```
*Note: You can view imported USB evidence in the **Endpoint Auditor** modal ([http://localhost:3001/endpoints](http://localhost:3001/endpoints)) or inspect agent scripts in **[Client Agents Hub](http://localhost:3001/agents)**.*

### Option D: Upload Sticker OCR Image
Upload a physical hardware sticker photo to trigger background OCR parsing:
```powershell
# Using curl to upload a sticker image
curl.exe -v -F "file=@path/to/sticker.jpg" -H "X-Client-Cert-Fingerprint: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" http://localhost:8000/api/v1/assets/ocr-upload
```
*Note: Processed sticker records and extracted metadata appear in the **Sticker OCR History** dashboard ([http://localhost:3001/ocr-history](http://localhost:3001/ocr-history)).*

---

## 📋 5. Service Evaluation System (QR & Admin)

The Service Evaluation System enables post-service customer satisfaction surveys.

**1. Create a Service Session (Admin):**
- Via Web UI: Navigate to **[Evaluations Admin](http://localhost:3001/evaluations/admin)** and click "New Session".
- Via API:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/evaluations/sessions" -Method Post -Headers @{"Content-Type"="application/json"} -Body '{"title": "Network Troubleshooting", "customer_name": "KYB", "engineer_name": "MEW"}'
```

**2. Access Mobile QR Form:**
Scan the generated QR Code on the Admin page, or navigate to `http://localhost:3001/evaluate/<SESSION_ID>`.

---

## 🧠 6. AI Log Analyzer (EventIQ & Vector RAG)

The AI Log Analyzer provides intelligent Root Cause Analysis (RCA) across Windows, Linux, JSON, and Firewall logs with Local Semantic Vector Search.

**1. Analyze a Raw Log via API:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analyze/" -Method Post -Form @{
    text = "Event ID: 41 Source: Microsoft-Windows-Kernel-Power The system has rebooted without cleanly shutting down first."
    language = "th"
}
```

**2. Query Analyzer Statistics & Operational Catalog (API):**
```powershell
# Get analytics metrics & 7-day daily trends (derived from actual analysis_history)
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/history/stats" -Method Get

# Fetch complete 141 Operational Event Catalog (read-only reference knowledge)
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/history/catalog" -Method Get
```

**3. Access via Web Dashboard:**
Navigate to [http://localhost:3001/analyzer](http://localhost:3001/analyzer) to search the 141-event catalog, view 7-day volume trends, and inspect event category analytics.

**4. Run Non-Destructive Unit Verification Suites:**
```powershell
# Run standalone Windows log analyzer benchmark (10 scenarios)
python backend\test_enterprise_benchmark.py

# Run multi-platform benchmark (Linux, JSON, Fortinet, Cisco)
python backend\test_multi_platform_benchmark.py
```

> ⚠️ **CRITICAL BENCHMARK SAFETY**: Do NOT execute high-scale synthetic benchmark scripts (such as `tools/sprint11_benchmark.py`) against your primary application database. The benchmark script contains destructive setup operations and requires a dedicated, isolated database specified via `EIMS_BENCHMARK_DATABASE_URL`. It will refuse to run against any database ending in `registry`.

---

## 🛑 7. Shutting Down & Cleanup

When you are done testing, you can gracefully shut down all services.

```powershell
# Stop all docker-compose infrastructure
docker-compose down

# (Optional) Wipe all volumes/data to start fresh next time
docker-compose down -v
```

For Frontend and Backend terminals, press `Ctrl + C` in the respective terminal window.

---

## 🔧 8. Troubleshooting

**1. Backend `ModuleNotFoundError` (e.g. `requests`)**
- Cause: Missing Python dependencies.
- Fix: Run `pip install -r requirements.txt` in your virtual environment.

**2. Frontend `Module not found` (e.g. `react-hot-toast`)**
- Cause: Missing Node.js packages.
- Fix: Navigate to `clients/dashboard` and run `npm install`.

**3. Telemetry Worker Database Errors (e.g. `ForeignKeyViolationError`)**
- Cause: The database was re-migrated, but the Redis cache still holds stale Asset UUIDs.
- Fix: Flush the Redis cache (`docker-compose exec redis_cache redis-cli FLUSHALL`) and restart `simulate_traffic.py` to register fresh endpoints.
