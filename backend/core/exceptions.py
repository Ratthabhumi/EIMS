"""
==============================================================================
EIMS RFC 7807 Problem Details Exception Architecture
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
==============================================================================
"""

import uuid
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.core.logger import get_logger

logger = get_logger("eims.exceptions")


class EIMSProblemException(Exception):
    """
    Authoritative exception base class that guarantees every processing fault,
    state violation, or telemetry error transforms into structured RFC 7807 Problem Details JSON.
    """
    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        type_uri: str = "about:blank",
        instance_uri: Optional[str] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        **extra_metrics: Any
    ):
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.instance_uri = instance_uri
        self.additional_headers = additional_headers or {}
        self.extra_metrics = extra_metrics
        self.tracking_uuid = str(uuid.uuid4())


async def eims_problem_exception_handler(request: Request, exc: EIMSProblemException) -> JSONResponse:
    """
    FastAPI Middleware exception transformer catching EIMSProblemException and rendering
    application/problem+json conformant HTTP responses.
    """
    instance = exc.instance_uri or str(request.url.path)
    
    problem_payload: Dict[str, Any] = {
        "type": exc.type_uri,
        "title": exc.title,
        "status": exc.status,
        "detail": exc.detail,
        "instance": instance,
        "tracking_uuid": exc.tracking_uuid,
    }
    
    # Merge optional domain telemetry metrics into RFC 7807 extension attributes
    if exc.extra_metrics:
        problem_payload.update(exc.extra_metrics)
        
    logger.warning(
        f"RFC 7807 Problem Exception | UUID={exc.tracking_uuid} | Status={exc.status} | Title={exc.title} | Path={instance}"
    )
    
    headers = {"Content-Type": "application/problem+json"}
    headers.update(exc.additional_headers)
    
    return JSONResponse(
        status_code=exc.status,
        content=problem_payload,
        headers=headers
    )


async def global_unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Last-line defensive fallback intercepting untraced server crashes and converting
    them into safe RFC 7807 problem payloads without exposing stack trace secrets.
    """
    tracking_uuid = str(uuid.uuid4())
    logger.error(
        f"CRITICAL UNHANDLED SYSTEM EXCEPTION | UUID={tracking_uuid} | Path={request.url.path} | Error={str(exc)}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://errors.eims.platform/v1/internal-server-error",
            "title": "Internal Infrastructure Server Exception",
            "status": 500,
            "detail": "An unhandled runtime exception occurred during telemetry processing or persistence operations.",
            "instance": str(request.url.path),
            "tracking_uuid": tracking_uuid,
        },
        headers={"Content-Type": "application/problem+json"}
    )


# --- Specialized Domain Exception Subclasses ---

class AssetStateViolationException(EIMSProblemException):
    """Raised when an illegal state transition occurs in Asset Lifecycle State Machine."""
    def __init__(self, current_state: str, attempted_state: str, asset_id: str):
        super().__init__(
            status=422,
            title="Asset Lifecycle State Machine Violation",
            detail=f"Cannot transition Asset ID '{asset_id}' from state '{current_state}' directly to '{attempted_state}'. Operation prohibited under Core Law 3.",
            type_uri="https://errors.eims.platform/v1/illegal-state-transition",
            asset_id=asset_id,
            current_state=current_state,
            attempted_state=attempted_state,
        )


class ResourceNotFoundException(EIMSProblemException):
    """Raised when an asset or telemetry log metric cannot be located in storage."""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            status=404,
            title="Requested Infrastructure Resource Missing",
            detail=f"The requested {resource_type} corresponding to identifier '{resource_id}' does not exist in our authoritative database registry.",
            type_uri="https://errors.eims.platform/v1/resource-not-found",
            resource_type=resource_type,
            resource_id=resource_id,
        )
