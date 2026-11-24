"""
==============================================================================
EIMS Automated Test Suite — Open-access Portal identity (no application login)
==============================================================================
Product rule: EIMS has no application login. Engineers use the Portal without a
username/password. AUTH_MODE remains a compatibility setting only.
"""

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.core.config import EIMSSettings, settings
from backend.domain.analyzer.auth import (
    ALGORITHM,
    OPEN_ACCESS_IDENTITY,
    SECRET_KEY,
    create_access_token,
    get_current_user,
)
from backend.main import app


def test_auth_mode_configuration_strict_validation():
    """Confirms only 'demo' and 'secure' remain valid AUTH_MODE values."""
    s_demo = EIMSSettings(AUTH_MODE="demo")
    assert s_demo.AUTH_MODE == "demo"
    assert s_demo.is_demo_mode is True

    s_sec = EIMSSettings(AUTH_MODE="secure")
    assert s_sec.AUTH_MODE == "secure"
    assert s_sec.is_demo_mode is False

    s_upper = EIMSSettings(AUTH_MODE="DEMO")
    assert s_upper.AUTH_MODE == "demo"

    with pytest.raises(ValidationError):
        EIMSSettings(AUTH_MODE="invalid_mode")

    with pytest.raises(ValidationError):
        EIMSSettings(AUTH_MODE="bypass")


def test_jwt_token_generation_and_payload_verification():
    """Verifies JWT encodes and decodes role and sub claims accurately."""
    admin_token = create_access_token("admin_user", role="admin")
    payload = jwt.decode(admin_token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload.get("sub") == "admin_user"
    assert payload.get("role") == "admin"

    user_token = create_access_token("viewer_user", role="user")
    u_payload = jwt.decode(user_token, SECRET_KEY, algorithms=[ALGORITHM])
    assert u_payload.get("role") == "user"


def test_evaluation_write_without_application_login():
    """Evaluation writes succeed with no bearer credential (open access)."""
    with TestClient(app) as client:
        payload = {"title": "Open Access Maintenance Session", "customer_name": "Lab Corp"}
        resp = client.post("/api/v1/evaluations/sessions", json=payload)
        assert resp.status_code == 201, f"Expected 201 without login, got: {resp.status_code}: {resp.text}"


def test_open_access_survives_secure_auth_mode_setting():
    """AUTH_MODE=secure must not reintroduce application login requirements."""
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "secure"
        with TestClient(app) as client:
            payload = {"title": "Still Open Access Session", "customer_name": "Lab Corp"}
            resp = client.post("/api/v1/evaluations/sessions", json=payload)
            assert resp.status_code == 201, (
                f"Expected open-access 201 even when AUTH_MODE=secure, got: {resp.status_code}: {resp.text}"
            )

            health = client.get("/api/v1/timeline", params={"limit": 1})
            assert health.status_code == 200, health.text

            login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
            assert login.status_code == 410, login.text
            assert "not used" in login.json()["detail"].lower()
    finally:
        settings.AUTH_MODE = original_mode


def test_admin_token_still_accepted_for_attribution():
    """Configured ADMIN_TOKEN remains usable for machine/admin tooling."""
    original_token = settings.ADMIN_TOKEN
    try:
        settings.ADMIN_TOKEN = "test_super_secret_admin_token_12345"
        with TestClient(app) as client:
            payload = {"title": "Admin Token Session", "customer_name": "Ops"}
            token_resp = client.post(
                "/api/v1/evaluations/sessions",
                json=payload,
                headers={"Authorization": "Bearer test_super_secret_admin_token_12345"},
            )
            assert token_resp.status_code == 201, token_resp.text
    finally:
        settings.ADMIN_TOKEN = original_token


@pytest.mark.asyncio
async def test_get_current_user_returns_open_access_without_credentials(monkeypatch):
    """Missing bearer credentials resolve to the shared open-access identity."""
    class _Req:
        url = type("U", (), {"path": "/api/v1/analyze/"})()

    identity = await get_current_user(_Req(), None, db=None)  # type: ignore[arg-type]
    assert identity == OPEN_ACCESS_IDENTITY
