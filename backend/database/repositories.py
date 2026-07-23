"""Repository boundary for production metadata."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import (
    ArtifactRow,
    InspectionRunRow,
    ModelBundleRow,
    PipelineSnapshotRow,
    SourceFrameRow,
)
from backend.database.records import (
    ArtifactMetadata,
    InspectionRunMetadata,
    ModelBundleMetadata,
    PipelineSnapshotMetadata,
    SourceFrameMetadata,
)


class MetadataRepository:
    """Map framework-neutral records to SQLAlchemy rows without committing."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_model_bundle(self, value: ModelBundleMetadata) -> None:
        self._session.add(ModelBundleRow(**asdict(value)))
        self._session.flush()

    def get_model_bundle(self, model_bundle_id: str) -> ModelBundleMetadata | None:
        row = self._session.get(ModelBundleRow, model_bundle_id)
        return _model_bundle_metadata(row) if row is not None else None

    def add_pipeline_snapshot(self, value: PipelineSnapshotMetadata) -> None:
        self._session.add(PipelineSnapshotRow(**asdict(value)))
        self._session.flush()

    def get_pipeline_snapshot(
        self,
        pipeline_snapshot_id: str,
    ) -> PipelineSnapshotMetadata | None:
        row = self._session.get(PipelineSnapshotRow, pipeline_snapshot_id)
        return _pipeline_snapshot_metadata(row) if row is not None else None

    def add_run(self, value: InspectionRunMetadata) -> None:
        self._session.add(InspectionRunRow(**asdict(value)))
        self._session.flush()

    def get_run(self, run_id: str) -> InspectionRunMetadata | None:
        row = self._session.get(InspectionRunRow, run_id)
        return _run_metadata(row) if row is not None else None

    def add_source_frame(self, value: SourceFrameMetadata) -> None:
        self._session.add(SourceFrameRow(**asdict(value)))
        self._session.flush()

    def list_source_frames(self, run_id: str) -> Sequence[SourceFrameMetadata]:
        statement = (
            select(SourceFrameRow)
            .where(SourceFrameRow.run_id == run_id)
            .order_by(SourceFrameRow.frame_index)
        )
        return tuple(_source_frame_metadata(row) for row in self._session.scalars(statement))

    def add_artifact(self, value: ArtifactMetadata) -> None:
        self._session.add(ArtifactRow(**asdict(value)))
        self._session.flush()

    def list_artifacts(self, run_id: str) -> Sequence[ArtifactMetadata]:
        statement = (
            select(ArtifactRow)
            .where(ArtifactRow.run_id == run_id)
            .order_by(ArtifactRow.created_at, ArtifactRow.artifact_id)
        )
        return tuple(_artifact_metadata(row) for row in self._session.scalars(statement))


def _model_bundle_metadata(row: ModelBundleRow) -> ModelBundleMetadata:
    return ModelBundleMetadata(
        model_bundle_id=row.model_bundle_id,
        display_name=row.display_name,
        model_version=row.model_version,
        state=row.state,
        manifest_path=row.manifest_path,
        sha256=row.sha256,
        created_at=row.created_at,
    )


def _pipeline_snapshot_metadata(row: PipelineSnapshotRow) -> PipelineSnapshotMetadata:
    return PipelineSnapshotMetadata(
        pipeline_snapshot_id=row.pipeline_snapshot_id,
        pipeline_id=row.pipeline_id,
        revision=row.revision,
        display_name=row.display_name,
        state=row.state,
        model_bundle_id=row.model_bundle_id,
        contract_path=row.contract_path,
        sha256=row.sha256,
        created_at=row.created_at,
    )


def _run_metadata(row: InspectionRunRow) -> InspectionRunMetadata:
    return InspectionRunMetadata(
        run_id=row.run_id,
        acquisition_id=row.acquisition_id,
        pipeline_snapshot_id=row.pipeline_snapshot_id,
        source=row.source,
        side=row.side,
        status=row.status,
        failure_code=row.failure_code,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _source_frame_metadata(row: SourceFrameRow) -> SourceFrameMetadata:
    return SourceFrameMetadata(
        source_frame_id=row.source_frame_id,
        run_id=row.run_id,
        frame_index=row.frame_index,
        relative_path=row.relative_path,
        sha256=row.sha256,
        width=row.width,
        height=row.height,
        created_at=row.created_at,
    )


def _artifact_metadata(row: ArtifactRow) -> ArtifactMetadata:
    return ArtifactMetadata(
        artifact_id=row.artifact_id,
        run_id=row.run_id,
        kind=row.kind,
        relative_path=row.relative_path,
        sha256=row.sha256,
        size_bytes=row.size_bytes,
        media_type=row.media_type,
        created_at=row.created_at,
    )
