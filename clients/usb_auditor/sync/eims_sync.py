# -*- coding: utf-8 -*-
"""
sync/eims_sync.py

One-shot, offline-first auto-sync of a just-saved USB Auditor JSON report
into the EIMS backend via the existing import endpoint:

    POST {EIMS_API_URL}/api/v1/assets/import-report   (multipart, field `file`)

Design rules (do not violate):
    - The local report is ALWAYS saved first; this module only uploads an
      existing file, so the uploaded copy never becomes the only copy.
    - Exactly ONE attempt per audit run. No retries, no backoff, no daemon.
    - Strictly non-fatal: backend offline, timeout, DNS failure, HTTP 4xx/5xx
      and malformed responses are all converted into a SyncResult; an
      exception NEVER escapes into the audit flow.
    - Python standard library only (urllib) -- no new dependency for a
      single multipart POST.
    - Auth: mirrors current EIMS demo behavior. The import endpoint does not
      require credentials in demo mode, and this client sends NONE (no
      hardcoded tokens). In a future secure mode the server will reject with
      an HTTP 4xx and auto-sync will fail safely; the local report is never
      destroyed or invalidated by an auth failure.
    - The uploaded bytes are EXACTLY the saved local report file. No
      re-serialization, no enrichment, no secret fields are ever added.
"""

import http.client
import json
import logging
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

from config import settings

logger = logging.getLogger(__name__)

# Route on the existing EIMS asset registry controller (backend reuse,
# do NOT add a second ingestion endpoint).
IMPORT_PATH = "/api/v1/assets/import-report"

# Bounded total time budget for connect + read ("never hang").
DEFAULT_TIMEOUT_SECONDS = 8

# Multipart file field name expected by the backend UploadFile parameter.
MULTIPART_FIELD_NAME = "file"


@dataclass
class SyncResult:
    """Outcome of one auto-sync attempt (never raises)."""

    success: bool
    attempted: bool
    status_code: Optional[int] = None
    message: str = ""
    asset_hostname: Optional[str] = None
    compliance_score: Optional[int] = None


def build_import_endpoint(base_url: Optional[str] = None) -> str:
    """Normalize a base backend URL into the full import endpoint.

    Both ``http://localhost:8000`` and ``http://localhost:8000/`` produce
    ``http://localhost:8000/api/v1/assets/import-report`` (no double slash).
    """
    base = (base_url or settings.EIMS_API_URL).strip().rstrip("/")
    return f"{base}{IMPORT_PATH}"


def _build_multipart_body(field_name: str, filename: str, filedata: bytes) -> Tuple[bytes, str]:
    """Build a minimal multipart/form-data body containing one file part."""
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        "Content-Type: application/json\r\n"
        "\r\n"
    ).encode("utf-8")
    body = head + filedata + b"\r\n" + f"--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


def _http_post_multipart(
    url: str,
    field_name: str,
    filename: str,
    filedata: bytes,
    timeout: float,
) -> Tuple[int, str]:
    """POST `filedata` to `url` as multipart/form-data.

    Returns (status_code, response_body). Raises on transport-level errors
    (URLError / OSError / socket.timeout / HTTPException).
    """
    body, content_type = _build_multipart_body(field_name, filename, filedata)
    req = urllib_request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", content_type)
    req.add_header("Content-Length", str(len(body)))

    with urllib_request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _parse_asset_response(body_text: str) -> Tuple[Optional[str], Optional[int]]:
    """Extract display-safe fields (hostname, compliance) from the response.

    Returns (None, None) if the body is absent/not JSON, so the caller never
    invents values the backend did not provide.
    """
    try:
        payload = json.loads(body_text)
    except (TypeError, ValueError):
        return None, None

    if not isinstance(payload, dict):
        return None, None
    hostname = payload.get("hostname")
    compliance = payload.get("current_compliance_score")
    return (
        hostname if isinstance(hostname, str) else None,
        compliance if isinstance(compliance, int) else None,
    )


def sync_report(
    report_path: Path,
    api_base_url: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> SyncResult:
    """Upload one already-saved JSON report to EIMS exactly once.

    This function NEVER raises. Every outcome (disabled, missing file,
    transport error, timeout, HTTP error, success) is returned as a
    `SyncResult`, so the caller can keep the audit flow running.
    """
    if not settings.is_auto_sync_enabled():
        return SyncResult(success=False, attempted=False, message="Auto-sync disabled")

    report_path = Path(report_path)
    if not report_path.is_file():
        return SyncResult(success=False, attempted=True, message="Local report file not found")

    endpoint = build_import_endpoint(api_base_url)
    filename = report_path.name

    try:
        filedata = report_path.read_bytes()
    except OSError as exc:
        logger.warning("Auto-sync could not read local report: %s", exc)
        return SyncResult(success=False, attempted=True, message="Could not read local report")

    logger.info("Auto-sync: POST %s with report %s", endpoint, filename)

    try:
        status_code, body_text = _http_post_multipart(
            endpoint, MULTIPART_FIELD_NAME, filename, filedata, timeout
        )
    except urllib_error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        logger.warning("Auto-sync transport error: %s", reason)
        return SyncResult(success=False, attempted=True, message="EIMS backend unavailable")
    except socket.timeout:
        logger.warning("Auto-sync timed out after %.0fs", timeout)
        return SyncResult(success=False, attempted=True, message="EIMS backend timed out")
    except (http.client.HTTPException, OSError, ValueError) as exc:
        logger.warning("Auto-sync network failure: %s", exc)
        return SyncResult(success=False, attempted=True, message="EIMS sync failed")
    except Exception as exc:  # defensive: never escape the module boundary
        logger.error("Auto-sync unexpected error: %s", exc)
        return SyncResult(success=False, attempted=True, message="EIMS auto-sync skipped")

    hostname, compliance = _parse_asset_response(body_text)

    if status_code == 200:
        message = "Report synced"
        if hostname:
            message += f": {hostname}"
        if compliance is not None:
            message += f" — Compliance: {compliance}%"
        logger.info("Auto-sync accepted by EIMS (HTTP 200)")
        return SyncResult(
            success=True,
            attempted=True,
            status_code=status_code,
            message=message,
            asset_hostname=hostname,
            compliance_score=compliance,
        )

    logger.warning("EIMS import endpoint returned HTTP %s for %s", status_code, filename)
    return SyncResult(
        success=False,
        attempted=True,
        status_code=status_code,
        message=f"EIMS rejected report (HTTP {status_code})",
    )