"""
==============================================================================
EIMS mTLS Cryptographic Security Gatekeeper Dependency
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 5.3
Source-Available All Rights Reserved Policy
==============================================================================
"""

import re
from typing import Optional
from fastapi import Header, status
from backend.core.exceptions import EIMSProblemException
from backend.core.logger import get_logger

logger = get_logger("eims.security.mtls")

# Canonical regular expression asserting explicit SHA-256 hexadecimal formatting (64 chars)
_SHA256_HEX_REGEX = re.compile(r"^[a-fA-F0-9]{64}$")


async def verify_mtls_fingerprint(
    x_client_cert_fingerprint: Optional[str] = Header(None, alias="X-Client-Cert-Fingerprint")
) -> str:
    """
    FastAPI security dependency enforcing Mutual TLS (mTLS) cryptographic client validation
    on high-frequency edge ingestion routes per Core Law 5 Section 5.3 and Section 7.1.

    Reverse proxy layers (or test injectors) extract active client SSL certificate SHA-256
    hashes and inject them into the 'X-Client-Cert-Fingerprint' internal routing header.
    If missing or mathematically invalid, interrupts request processing instantly with HTTP 401 Unauthorized.
    """
    if not x_client_cert_fingerprint:
        logger.warning("mTLS Ingestion Rejection: Missing required 'X-Client-Cert-Fingerprint' transport header.")
        raise EIMSProblemException(
            status=status.HTTP_401_UNAUTHORIZED,
            title="mTLS Client Authentication Required",
            detail="Missing required cryptographic client certificate fingerprint in X-Client-Cert-Fingerprint header.",
            type_uri="https://errors.eims.platform/v1/mtls-authentication-missing",
            additional_headers={"WWW-Authenticate": 'mTLS realm="EIMS Telemetry Collector"'}
        )

    if not _SHA256_HEX_REGEX.match(x_client_cert_fingerprint):
        logger.warning(f"mTLS Ingestion Rejection: Malformed SHA-256 certificate hash '{x_client_cert_fingerprint}'.")
        raise EIMSProblemException(
            status=status.HTTP_401_UNAUTHORIZED,
            title="Invalid mTLS Certificate Fingerprint",
            detail="The provided X-Client-Cert-Fingerprint does not conform to canonical 64-character SHA-256 hexadecimal standards.",
            type_uri="https://errors.eims.platform/v1/mtls-fingerprint-malformed",
            provided_fingerprint_length=len(x_client_cert_fingerprint)
        )

    logger.debug(f"mTLS cryptographic identity authenticated successfully: SHA-256='{x_client_cert_fingerprint}'")
    return x_client_cert_fingerprint
