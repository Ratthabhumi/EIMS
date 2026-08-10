"""
==============================================================================
EIMS Telemetry Ingestion Domain Pydantic Schemas
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
Source-Available All Rights Reserved Policy
==============================================================================
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class HeartbeatMetrics(BaseModel):
    """
    Diagnostic runtime metrics extracted from networked operating systems and hardware nodes.
    Enforces strict physical boundary limitations per Core Law 5 Section 6.2.
    """
    cpu_utilization: float = Field(
        ..., ge=0.0, le=100.0, description="CPU usage percentage bound strictly between 0.0 and 100.0."
    )
    ram_used_mb: int = Field(..., ge=0, description="Active Random Access Memory allocation in megabytes.")
    ram_total_mb: int = Field(..., gt=0, description="Aggregate physical RAM architecture installed on host.")
    disk_iops: int = Field(..., ge=0, description="Real-time storage disk input/output operations per second.")


class AgentHeartbeatRequest(BaseModel):
    """High-frequency heartbeat transmission packet emitted by remote Discovery Agents."""
    agent_version: str = Field(..., max_length=50, description="Semantic version string of deploying client agent (e.g., 'v1.2.4').")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="UTC diagnostic sampling timestamp.")
    metrics: HeartbeatMetrics = Field(..., description="Encapsulated hardware and runtime operational metrics.")


class WinlogMetadata(BaseModel):
    """
    Flexible Windows event metadata container designed to accommodate structured attributes
    as well as dynamic diagnostic extensions from specialized forensic tools.
    """
    model_config = ConfigDict(extra="allow")
    
    target_user_name: str | None = Field(None, description="Security subject username target in event occurrence.")
    workstation_name: str | None = Field(None, description="Source computer name or Windows endpoint hostname.")
    source_network_ip: str | None = Field(None, description="Remote IPv4/IPv6 address initiating security interaction.")


class AgentWinlogRequest(BaseModel):
    """Ingestion schema receiving continuous native .evtx streaming event strings and forensic anomalies."""
    occurrence_time: datetime = Field(..., description="Windows event occurrence time stamped in UTC.")
    event_id: int = Field(..., ge=0, description="Canonical Windows Event ID identifier (e.g., 4625 for logon failure).")
    severity: str = Field(..., max_length=50, description="Event severity classification literal (Critical, Warning, Information).")
    event_channel: str = Field(..., max_length=100, description="Windows log channel source (Security, System, Application).")
    metadata: WinlogMetadata = Field(default_factory=WinlogMetadata, description="Associated forensic attributes and custom tool extensions.")


class StreamIngestionResponse(BaseModel):
    """
    Standardized HTTP 202 Accepted response schema indicating successful stream queuing
    into Redis Event Brokers without waiting for relational synchronous disk commits.
    """
    status: str = Field("accepted", description="Standard API processing acceptance indicator.")
    stream_job_id: str = Field(
        default_factory=lambda: f"{int(datetime.now(UTC).timestamp() * 1000)}-0",
        description="Unique Redis Stream sequence identifier assigned to queued telemetry packet."
    )
    queued_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Exact UTC ISO timestamp when payload arrived inside Redis buffer."
    )
