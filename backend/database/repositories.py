"""Repository boundary for production metadata."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import (
    ArtifactRow,
    InspectionRunRow,
    ModelBundleRow,
    PipelineSnapshotRow,
    RunControlRow,
    RunStageCheckpointRow,
    SourceFrameRow,
)
from backend.database.records import (
    ArtifactMetadata,
    InspectionRunMetadata,
    ModelBundleMetadata,
    PipelineSnapshotMetadata,
    RunControlMetadata,
    RunStageCheckpointMetadata,
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

    def get_active_model_bundle(self) -> ModelBundleMetadata | None:
        statement = select(ModelBundleRow).where(ModelBundleRow.state == "active")
        row = self._session.scalar(statement)
        return _model_bundle_metadata(row) if row is not None else None

    def list_model_bundles(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[ModelBundleMetadata]:
        statement = (
            select(ModelBundleRow)
            .order_by(ModelBundleRow.created_at.desc(), ModelBundleRow.model_bundle_id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(_model_bundle_metadata(row) for row in self._session.scalars(statement))

    def set_model_bundle_state(self, model_bundle_id: str, state: str) -> None:
        row = self._session.get(ModelBundleRow, model_bundle_id)
        if row is None:
            raise KeyError(f"unknown model bundle: {model_bundle_id}")
        row.state = state
        self._session.flush()

    def add_pipeline_snapshot(self, value: PipelineSnapshotMetadata) -> None:
        self._session.add(PipelineSnapshotRow(**asdict(value)))
        self._session.flush()

    def get_pipeline_snapshot(
        self,
        pipeline_snapshot_id: str,
    ) -> PipelineSnapshotMetadata | None:
        row = self._session.get(PipelineSnapshotRow, pipeline_snapshot_id)
        return _pipeline_snapshot_metadata(row) if row is not None else None

    def list_pipeline_snapshots(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[PipelineSnapshotMetadata]:
        statement = (
            select(PipelineSnapshotRow)
            .order_by(
                PipelineSnapshotRow.created_at.desc(),
                PipelineSnapshotRow.pipeline_snapshot_id,
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(_pipeline_snapshot_metadata(row) for row in self._session.scalars(statement))

    def add_run(self, value: InspectionRunMetadata) -> None:
        self._session.add(InspectionRunRow(**asdict(value)))
        self._session.flush()
        self._session.add(
            RunControlRow(
                run_id=value.run_id,
                cancellation_requested=False,
                lease_owner=None,
                lease_expires_at=None,
                updated_at=value.created_at,
            )
        )
        self._session.flush()

    def get_run(self, run_id: str) -> InspectionRunMetadata | None:
        row = self._session.get(InspectionRunRow, run_id)
        return _run_metadata(row) if row is not None else None

    def list_runs(
        self,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[InspectionRunMetadata]:
        statement = (
            select(InspectionRunRow)
            .order_by(InspectionRunRow.created_at.desc(), InspectionRunRow.run_id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(_run_metadata(row) for row in self._session.scalars(statement))

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

    def get_run_control(self, run_id: str) -> RunControlMetadata | None:
        row = self._session.get(RunControlRow, run_id)
        return _run_control_metadata(row) if row is not None else None

    def add_run_control(self, value: RunControlMetadata) -> None:
        self._session.add(RunControlRow(**asdict(value)))
        self._session.flush()

    def set_cancellation_requested(
        self,
        run_id: str,
        requested: bool,
        updated_at: datetime,
    ) -> None:
        row = self._session.get(RunControlRow, run_id)
        if row is None:
            raise KeyError(f"unknown run control: {run_id}")
        row.cancellation_requested = requested
        row.updated_at = updated_at
        self._session.flush()

    def try_acquire_run_lease(
        self,
        run_id: str,
        owner: str,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        row = self._session.get(RunControlRow, run_id)
        if row is None:
            raise KeyError(f"unknown run control: {run_id}")
        if (
            row.lease_owner is not None
            and row.lease_owner != owner
            and row.lease_expires_at is not None
            and row.lease_expires_at > now
        ):
            return False
        row.lease_owner = owner
        row.lease_expires_at = expires_at
        row.updated_at = now
        self._session.flush()
        return True

    def renew_run_lease(
        self,
        run_id: str,
        owner: str,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        row = self._session.get(RunControlRow, run_id)
        if row is None or row.lease_owner != owner:
            return False
        row.lease_expires_at = expires_at
        row.updated_at = now
        self._session.flush()
        return True

    def release_run_lease(self, run_id: str, owner: str, updated_at: datetime) -> None:
        row = self._session.get(RunControlRow, run_id)
        if row is None or row.lease_owner != owner:
            return
        row.lease_owner = None
        row.lease_expires_at = None
        row.updated_at = updated_at
        self._session.flush()

    def set_run_status(
        self,
        run_id: str,
        status: str,
        *,
        failure_code: str | None,
        started_at: datetime | None,
        finished_at: datetime | None,
    ) -> None:
        row = self._session.get(InspectionRunRow, run_id)
        if row is None:
            raise KeyError(f"unknown run: {run_id}")
        row.status = status
        row.failure_code = failure_code
        if started_at is not None:
            row.started_at = started_at
        row.finished_at = finished_at
        self._session.flush()

    def get_stage_checkpoint(
        self,
        run_id: str,
        stage_name: str,
    ) -> RunStageCheckpointMetadata | None:
        row = self._session.get(RunStageCheckpointRow, (run_id, stage_name))
        return _run_stage_checkpoint_metadata(row) if row is not None else None

    def put_stage_checkpoint(self, value: RunStageCheckpointMetadata) -> None:
        row = self._session.get(
            RunStageCheckpointRow,
            (value.run_id, value.stage_name),
        )
        payload = asdict(value)
        if row is None:
            self._session.add(RunStageCheckpointRow(**payload))
        else:
            for key, item in payload.items():
                if key not in {"run_id", "stage_name"}:
                    setattr(row, key, item)
        self._session.flush()

    def list_stage_checkpoints(
        self,
        run_id: str,
    ) -> Sequence[RunStageCheckpointMetadata]:
        statement = (
            select(RunStageCheckpointRow)
            .where(RunStageCheckpointRow.run_id == run_id)
            .order_by(RunStageCheckpointRow.stage_name)
        )
        return tuple(
            _run_stage_checkpoint_metadata(row) for row in self._session.scalars(statement)
        )


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


def _run_control_metadata(row: RunControlRow) -> RunControlMetadata:
    return RunControlMetadata(
        run_id=row.run_id,
        cancellation_requested=row.cancellation_requested,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        updated_at=row.updated_at,
    )


def _run_stage_checkpoint_metadata(
    row: RunStageCheckpointRow,
) -> RunStageCheckpointMetadata:
    return RunStageCheckpointMetadata(
        run_id=row.run_id,
        stage_name=row.stage_name,
        status=row.status,
        attempt_count=row.attempt_count,
        evidence_path=row.evidence_path,
        evidence_sha256=row.evidence_sha256,
        failure_code=row.failure_code,
        updated_at=row.updated_at,
    )
