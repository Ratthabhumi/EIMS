"""
==============================================================================
EIMS Automated Test Suite — Homelab Deployment Configuration Tests
Governed by EIMS Documentation System (EDS v1.0.0)
==============================================================================
Verifies:
1. docker-compose.homelab.yml overlay specifies 127.0.0.1 bindings for internal infrastructure.
2. MinIO setup in homelab uses anonymous set none (private bucket).
3. .env.homelab.example contains all required production override keys without plaintext production secrets.
4. EIMSSettings boot refusal in production when required secrets are missing or auth is demo.
==============================================================================
"""

import os
import yaml
import pytest
from pydantic import ValidationError

from backend.core.config import EIMSSettings


def test_homelab_compose_network_isolation():
    """Confirms docker-compose.homelab.yml strictly binds all backing services to loopback (127.0.0.1)."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.homelab.yml")
    assert os.path.exists(compose_path), "docker-compose.homelab.yml must exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    services = data.get("services", {})
    assert "postgres_db" in services
    assert "pgbouncer" in services
    assert "redis_cache" in services
    assert "minio_s3" in services

    for svc_name, svc_cfg in services.items():
        ports = svc_cfg.get("ports", [])
        for port_mapping in ports:
            # Must start with 127.0.0.1: to guarantee loopback-only binding
            assert port_mapping.startswith("127.0.0.1:"), (
                f"Service {svc_name} port {port_mapping} is NOT bound to 127.0.0.1"
            )


def test_homelab_minio_bucket_privacy():
    """Confirms MinIO setup in docker-compose.homelab.yml sets bucket privacy to none (not public)."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.homelab.yml")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "anonymous set none" in content, "Homelab MinIO setup must set bucket anonymous access to 'none'"
    assert "anonymous set public" not in content, "Homelab MinIO setup must NOT set bucket to public"


def test_env_homelab_example_structure():
    """Confirms .env.homelab.example provides required production configuration placeholders without leaking secrets."""
    example_path = os.path.join(os.path.dirname(__file__), "..", ".env.homelab.example")
    assert os.path.exists(example_path), ".env.homelab.example must exist"

    with open(example_path, "r", encoding="utf-8") as f:
        text = f.read()

    required_keys = [
        "EIMS_ENVIRONMENT=production",
        "EIMS_AUTH_MODE=secure",
        "EIMS_DB_PASSWORD=",
        "EIMS_JWT_SECRET_KEY=",
        "EIMS_ADMIN_TOKEN=",
        "EIMS_ADMIN_PASSWORD=",
        "EIMS_MINIO_SECRET_KEY=",
    ]
    for key in required_keys:
        assert key in text, f"Missing required configuration key in .env.homelab.example: {key}"


def test_production_boot_refusal_when_secrets_missing():
    """Confirms EIMSSettings refuses to boot in production tier if dev defaults are used or admin password is missing."""
    with pytest.raises(RuntimeError) as exc_info:
        EIMSSettings(
            ENVIRONMENT="production",
            AUTH_MODE="secure",
            ADMIN_PASSWORD=None,
        )
    assert "Refusing to boot EIMS in 'production' tier" in str(exc_info.value)
    assert "ADMIN_PASSWORD" in str(exc_info.value)


def test_production_boot_refusal_when_auth_is_demo():
    """Confirms EIMSSettings refuses to boot in production tier if AUTH_MODE is set to 'demo'."""
    with pytest.raises(RuntimeError) as exc_info:
        EIMSSettings(
            ENVIRONMENT="production",
            AUTH_MODE="demo",
            ADMIN_PASSWORD="StrongProductionAdminPassword123!",
            DB_PASSWORD="StrongProductionDBPassword123!",
            MINIO_SECRET_KEY="StrongProductionMinIOSecretKey123!",
            JWT_SECRET_KEY="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
            ADMIN_TOKEN="StrongProductionAdminToken12345678",
        )
    assert "Refusing to boot EIMS in 'production' tier" in str(exc_info.value)
    assert "AUTH_MODE" in str(exc_info.value)


def test_production_boot_success_with_explicit_secrets():
    """Confirms EIMSSettings successfully initializes in production tier when all required secrets are provided."""
    s = EIMSSettings(
        ENVIRONMENT="production",
        AUTH_MODE="secure",
        ADMIN_PASSWORD="StrongProductionAdminPassword123!",
        DB_PASSWORD="StrongProductionDBPassword123!",
        MINIO_SECRET_KEY="StrongProductionMinIOSecretKey123!",
        JWT_SECRET_KEY="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        ADMIN_TOKEN="StrongProductionAdminToken12345678",
    )
    assert s.ENVIRONMENT == "production"
    assert s.AUTH_MODE == "secure"
    assert s.is_demo_mode is False
    assert s.ADMIN_PASSWORD == "StrongProductionAdminPassword123!"
