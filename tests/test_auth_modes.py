"""
==============================================================================
EIMS Automated Test Suite — Auth Hardening & Multi-Mode Security Enforcement
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 2 & 5 Compliance
==============================================================================
Proves contract adherence for:
1. AUTH_MODE configuration validation (Literal["demo", "secure"]).
2. Demo Mode evaluation writes without token (Evaluation Admin UI functional).
3. Secure Mode rejection of unauthenticated writes (HTTP 401/403).
4. Secure Mode recognition of valid Admin JWT (role == "admin").
5. Secure Mode rejection of non-admin JWT (role == "user").
6. Secure Mode recognition of server-side ADMIN_TOKEN.
"""

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

import jwt
from backend.core.config import EIMSSettings, settings
from backend.domain.analyzer.auth import create_access_token, SECRET_KEY, ALGORITHM
from backend.main import app


def test_auth_mode_configuration_strict_validation():
    """Confirms only 'demo' and 'secure' are valid AUTH_MODE values."""
    # Valid values
    s_demo = EIMSSettings(AUTH_MODE="demo")
    assert s_demo.AUTH_MODE == "demo"
    assert s_demo.is_demo_mode is True

    s_sec = EIMSSettings(AUTH_MODE="secure")
    assert s_sec.AUTH_MODE == "secure"
    assert s_sec.is_demo_mode is False

    # Case-insensitive normalization
    s_upper = EIMSSettings(AUTH_MODE="DEMO")
    assert s_upper.AUTH_MODE == "demo"

    # Invalid values must raise ValidationError
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


def test_evaluation_write_in_demo_mode():
    """In DEMO mode, evaluation write operations succeed without token."""
    original_mode = settings.AUTH_MODE
    try:
        settings.AUTH_MODE = "demo"
        with TestClient(app) as client:
            # POST to create evaluation session without token in demo mode
            payload = {"title": "Demo Maintenance Session", "customer_name": "Demo Corp"}
            resp = client.post("/api/v1/evaluations/sessions", json=payload)
            # In demo mode, require_admin_for_write allows the request
            assert resp.status_code == 201, f"Expected 201 Created in demo mode, got: {resp.status_code}: {resp.text}"
    finally:
        settings.AUTH_MODE = original_mode


def test_evaluation_write_in_secure_mode_enforcement():
    """In SECURE mode, evaluation writes strictly require Admin JWT or ADMIN_TOKEN."""
    original_mode = settings.AUTH_MODE
    original_token = settings.ADMIN_TOKEN
    try:
        settings.AUTH_MODE = "secure"
        settings.ADMIN_TOKEN = "test_super_secret_admin_token_12345"

        with TestClient(app) as client:
            payload = {"title": "Secure Maintenance Session", "customer_name": "Secure Corp"}

            # 1. Unauthenticated write must be rejected with 401
            no_auth_resp = client.post("/api/v1/evaluations/sessions", json=payload)
            assert no_auth_resp.status_code in (401, 403), f"Expected 401/403, got: {no_auth_resp.status_code}"

            # 2. Non-admin JWT (role == 'user') must be rejected with 403 Forbidden
            user_jwt = create_access_token("normal_user", role="user")
            user_resp = client.post(
                "/api/v1/evaluations/sessions",
                json=payload,
                headers={"Authorization": f"Bearer {user_jwt}"}
            )
            assert user_resp.status_code == 403, f"Non-admin JWT should be rejected with 403, got: {user_resp.status_code}"

            # 3. Admin JWT (role == 'admin') must be accepted (HTTP 201)
            admin_jwt = create_access_token("sys_admin", role="admin")
            admin_resp = client.post(
                "/api/v1/evaluations/sessions",
                json=payload,
                headers={"Authorization": f"Bearer {admin_jwt}"}
            )
            assert admin_resp.status_code == 201, f"Admin JWT was rejected: {admin_resp.status_code} {admin_resp.text}"

            # 4. Server-side ADMIN_TOKEN via Bearer must be accepted (HTTP 201)
            token_resp = client.post(
                "/api/v1/evaluations/sessions",
                json=payload,
                headers={"Authorization": "Bearer test_super_secret_admin_token_12345"}
            )
            assert token_resp.status_code == 201, f"Admin Token was rejected: {token_resp.status_code} {token_resp.text}"
    finally:
        settings.AUTH_MODE = original_mode
        settings.ADMIN_TOKEN = original_token
