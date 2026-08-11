"""
==============================================================================
EIMS Asset Registry Domain ORM Models & GIN Index Architecture
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    SmallInteger,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from backend.infrastructure.database import Base


def _utcnow() -> datetime:
    """Returns accurate timezone-aware UTC current timestamp."""
    return datetime.now(timezone.utc)


class InfrastructureAsset(Base):
    """
    Authoritative repository entity indexing every registered compute hardware unit,
    server node, or virtual application endpoint (Core Law 4 Section 6.1).
    """
    __tablename__ = "infrastructure_assets"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Universally unique canonical EIMS asset identifier."
    )
    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Registered operating system networking hostname."
    )
    canonical_ip: Mapped[str] = mapped_column(
        String(45),  # Accommodates both IPv4 and expanded IPv6 string format lengths
        nullable=False,
        doc="Primary networking IP address associated with the asset."
    )
    cryptographic_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        doc="SHA-256 derivation of immutable hardware serial strings."
    )
    lifecycle_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="Discovered",
        doc="Validated state machine value (Discovered, Quarantine, Active, Decommissioned)."
    )
    current_compliance_score: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        doc="Active computed Compliance Score, defaulted at 0 upon discovery."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Record initial ingestion timestamp (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        doc="Timestamp of most recent attribute mutation."
    )
    offline_report_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Full raw JSON report uploaded from offline Auditor tools."
    )

    # Table constraints enforcing strict integrity invariants
    __table_args__ = (
        CheckConstraint(
            "current_compliance_score >= 0 AND current_compliance_score <= 100",
            name="ck_asset_compliance_score_bounds"
        ),
        {"comment": "Core Asset Registry Table governed under Core Law 4."}
    )

    # ORM Relationships
    inventories: Mapped[List["HardwareInventory"]] = relationship(
        "HardwareInventory",
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="asset",
        passive_deletes=True,
    )


class HardwareInventory(Base):
    """
    Catalogs internal physical hardware component configurations mapped directly
    to a parent Infrastructure Asset. Features polymorphic JSONB GIN Indexing.
    """
    __tablename__ = "hardware_inventories"

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary identification record for hardware snapshot."
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("infrastructure_assets.asset_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key binding component data to parent asset."
    )
    cpu_sku_model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="Identified central processor architecture vendor and model."
    )
    total_ram_mb: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Aggregate physical system memory capacity in megabytes."
    )
    storage_topology: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Structured JSON array detailing attached storage disks and UUIDs."
    )
    last_audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Temporal stamp indicating last hardware enumeration scan."
    )

    # Table constraints & explicit Generalized Inverted Index (GIN) on JSONB field (Core Law 4 Section 7.1)
    __table_args__ = (
        CheckConstraint(
            "total_ram_mb >= 0",
            name="ck_hardware_inventory_ram_non_negative"
        ),
        Index("idx_hardware_storage_gin", "storage_topology", postgresql_using="gin"),
        {"comment": "Hardware inventories containing polymorphic GIN-indexed storage topologies."}
    )

    # ORM Relationship
    asset: Mapped["InfrastructureAsset"] = relationship("InfrastructureAsset", back_populates="inventories")


class AuditLog(Base):
    """
    Provides an immutable, tamper-resistant system execution journal tracking all
    configuration mutations, state transitions, and compliance interventions.
    """
    __tablename__ = "audit_logs"

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique audit transaction identification hash."
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Operator user_id or automated Agent service account responsible for mutation."
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("infrastructure_assets.asset_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        doc="Target Infrastructure Asset impacted by operational command."
    )
    action_verb: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Executed operational command verb (e.g., TRANSITION_STATE, UPDATE_COMPLIANCE_SCORE)."
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        doc="Temporal stamp recording exact modification execution (UTC)."
    )
    immutable_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Historical snapshot capturing pre-mutation and post-mutation attributes."
    )

    __table_args__ = (
        Index("idx_audit_logs_action_time", "action_verb", "performed_at"),
        {"comment": "Immutable audit transaction journal governed under Core Law 4."}
    )

    # ORM Relationship
    asset: Mapped[Optional["InfrastructureAsset"]] = relationship("InfrastructureAsset", back_populates="audit_logs")


class OCRRegistrationRecord(Base):
    """
    Manages asynchronous workflow tracking for physical documents processed
    via OCR Asset Registration (Core Law 4 Section 6.2).
    """
    __tablename__ = "ocr_registration_records"

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Tracking identifier for multipart upload tasks."
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("infrastructure_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
        doc="Linked asset created or matched upon extraction completion."
    )
    minio_object_uri: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        doc="Immutable storage pointer within local MinIO storage buckets."
    )
    extraction_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="Pending",
        doc="Workflow execution state (Pending, Processing, Completed, Failed)."
    )
    parsed_raw_text: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Raw OCR extraction output strings and recognized keys."
    )

    __table_args__ = (
        {"comment": "OCR Registration workflow tracking governed under Core Law 4."}
    )

