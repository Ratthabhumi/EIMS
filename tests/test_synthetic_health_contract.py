"""Synthetic acceptance harness health keys must match the production/UI contract."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Runs in a subprocess so importing the harness (which mutates auth settings) cannot leak.
# The engine URL is a lazy dummy that passes dedicated_url(); no connection is ever opened.
_SCRIPT = r"""
import asyncio, json
from tests import analyzer_synthetic_demo_app as h
from backend.core.health_probe import HealthProbeCoordinator

async def run(db_ok):
    calls = {"db": 0, "redis": 0, "minio": 0}
    async def probe(name, value):
        calls[name] += 1
        return value
    h._health_probe = HealthProbeCoordinator(ttl_seconds=5)
    h.database_engine.ping = lambda: probe("db", db_ok)
    h.cache_manager.ping = lambda: probe("redis", True)
    h.object_storage.ping = lambda: probe("minio", True)
    first = await h.read_synthetic_health()
    second = await h.read_synthetic_health()
    return {"first": json.loads(first.body), "second": json.loads(second.body), "calls": calls}

print(json.dumps({"up": asyncio.run(run(True)), "down": asyncio.run(run(False))}))
"""


def _synthetic_health():
    env = {**os.environ, "EIMS_TEST_DATABASE_URL":
           "postgresql+asyncpg://eims_test:x@127.0.0.1:55432/eims_integration_test"}
    out = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=120, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def _production_component_keys():
    src = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    return set(re.findall(r'"(\w+_tier)":\s*"UP"\s+if', src))


def _ui_component_keys():
    src = (ROOT / "clients" / "dashboard" / "src" / "components" / "SystemStatusCard.tsx").read_text(encoding="utf-8")
    return set(re.findall(r"\bhealth\.components\.(\w+_tier)\b", src))


def test_synthetic_health_component_keys_match_production_and_ui_contract():
    health = _synthetic_health()
    prod = _production_component_keys()
    assert prod, "failed to extract production component keys"
    assert set(health["up"]["first"]["components"]) == prod
    assert _ui_component_keys() <= set(health["up"]["first"]["components"])
    assert "postgresql_pgbouncer_tier" in health["up"]["first"]["components"]
    assert health["up"]["first"] == health["up"]["second"]
    assert health["up"]["calls"] == {"db": 1, "redis": 1, "minio": 1}


def test_synthetic_database_health_value_is_probed_not_hardcoded():
    health = _synthetic_health()
    for result in (health["up"]["first"], health["up"]["second"]):
        assert result["components"]["postgresql_pgbouncer_tier"] == "UP"
    for result in (health["down"]["first"], health["down"]["second"]):
        assert result["components"]["postgresql_pgbouncer_tier"] == "DOWN"
        assert result["status"] == "DEGRADED"
    assert health["down"]["calls"] == {"db": 1, "redis": 1, "minio": 1}
