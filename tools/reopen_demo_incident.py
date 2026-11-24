"""Reopen one demo incident so the presentation shows an active remediation cycle.

Uses the authenticated API exactly as an operator would (reviewer credential).
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

BASE = "https://eims-demo-api.onrender.com"
TMP = Path(os.environ["TEMP"]) / "opencode"


def kv() -> dict[str, str]:
    out = {}
    for line in (TMP / "eims_demo_secrets.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


s = kv()
status, body = call("POST", "/api/v1/auth/login",
                    {"username": s["EIMS_DEMO_REVIEWER"], "password": s["EIMS_DEMO_PASSWORD"]})
token = body["access_token"]
print("login", status)

status, listing = call("GET", "/api/v1/incidents?limit=50", token=token)
target = next(i for i in listing["data"] if "DEMO-DB-01" in i["title"])
print("target", target["incident_id"], target["status"], "cycle", target["remediation_cycle"])
if target["status"] == "resolved":
    st, res = call("PATCH", f"/api/v1/incidents/{target['incident_id']}/status",
                   {"status": "investigating"}, token=token)
    print("reopen", st, res.get("status"), "cycle", res.get("remediation_cycle"))
else:
    print("already", target["status"])
