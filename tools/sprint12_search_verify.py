"""Quick search verification after demo data seed."""
import os
os.environ.setdefault("EIMS_ENVIRONMENT", "development")

from fastapi.testclient import TestClient
from backend.main import app

with TestClient(app) as client:
    tests = [
        ("ai", None, "ai keyword"),
        ("KEL", None, "KEL hostname"),
        ("GPU", None, "GPU hostname"),
        ("PROD", None, "PROD hostname"),
        ("TRANSITION", "audit", "audit verb"),
        ("SECURITY", "audit", "SECURITY verb"),
        ("brute force", "analysis", "analysis description"),
        ("4625", None, "Windows event ID"),
        ("SERVER", None, "SERVER in hostname"),
    ]

    print(f"{'Label':25s} | {'Query':15s} | {'Type':8s} | Status | Total | First Title")
    print("-" * 110)

    for q, t, label in tests:
        url = f"/api/v1/search?q={q}&limit=5"
        if t:
            url += f"&type={t}"
        r = client.get(url)
        data = r.json()
        total = data.get("total_results", len(data.get("data", [])))
        results = data.get("data", data.get("results", []))
        first_title = results[0].get("title", "N/A")[:50] if results else "EMPTY"
        print(f"{label:25s} | {q:15s} | {(t or 'all'):8s} | {r.status_code:3d}   | {total:5d} | {first_title}")
