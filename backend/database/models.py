"""SQLAlchemy metadata models for the standalone production database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime, TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist aware datetimes as UTC and restore UTC awareness on SQLite."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Any,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("database datetimes must be timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Any,
    ) -> datetime | None:
        del dialect
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ModelBundleRow(Base):
    __tablename__ = "model_bundles"
    __table_args__ = (
        CheckConstraint(
            "state IN ('imported', 'verifying', 'valid', 'approved', 'active', "
            "'retired', 'rejected')",
            name="model_bundle_state",
        ),
        CheckConstraint("length(sha256) = 64", name="model_bundle_sha256_length"),
        Index("ix_model_bundles_state_created_at", "state", "created_at"),
        Index(
            "uq_model_bundles_single_active",
            "state",
            unique=True,
            sqlite_where=text("state = 'active'"),
        ),
    )

    model_bundle_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )


class PipelineSnapshotRow(Base):
    __tablename__ = "pipeline_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "pipeline_id",
            "revision",
            name="uq_pipeline_snapshots_pipeline_revision",
        ),
        CheckConstraint(
            "state IN ('draft', 'testing', 'validated', 'approved', 'active', "
            "'retired', 'rejected', 'archived')",
            name="pipeline_snapshot_state",
        ),
        CheckConstraint("revision >= 1", name="pipeline_snapshot_revision_positive"),
        CheckConstraint("length(sha256) = 64", name="pipeline_snapshot_sha256_length"),
        Index("ix_pipeline_snapshots_state_created_at", "state", "created_at"),
    )

    pipeline_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    model_bundle_id: Mapped[str] = mapped_column(
        ForeignKey("model_bundles.model_bundle_id", ondelete="RESTRICT"),
        nullable=False,
    )
    contract_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )


class InspectionRunRow(Base):
    __tablename__ = "inspection_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed', 'cancelled')",
            name="inspection_run_status",
        ),
        CheckConstraint(
            "source IN ('offline', 'online')",
            name="inspection_run_source",
        ),
        CheckConstraint(
            "side IN ('upper', 'lower', 'not_applicable')",
            name="inspection_run_side",
        ),
        Index("ix_inspection_runs_status_created_at", "status", "created_at"),
        Index("ix_inspection_runs_acquisition_id", "acquisition_id"),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False)
    pipeline_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "pipeline_snapshots.pipeline_snapshot_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class SourceFrameRow(Base):
    __tablename__ = "source_frames"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "frame_index",
            name="uq_source_frames_run_frame_index",
        ),
        UniqueConstraint(
            "run_id",
            "relative_path",
            name="uq_source_frames_run_relative_path",
        ),
        CheckConstraint("frame_index >= 0", name="source_frame_index_nonnegative"),
        CheckConstraint("width >= 1", name="source_frame_width_positive"),
        CheckConstraint("height >= 1", name="source_frame_height_positive"),
        CheckConstraint("length(sha256) = 64", name="source_frame_sha256_length"),
        Index("ix_source_frames_run_frame_index", "run_id", "frame_index"),
    )

    source_frame_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("inspection_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="artifact_size_nonnegative"),
        CheckConstraint("length(sha256) = 64", name="artifact_sha256_length"),
        Index("ix_artifacts_run_kind", "run_id", "kind"),
    )

    artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("inspection_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
    )
