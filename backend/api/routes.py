"""Thin typed local API routes over repositories and command dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.api.commands import RunCommandDispatcher
from backend.api.contracts import (
    ArtifactSummary,
    CenterReferenceImportRequest,
    CenterReferenceSummary,
    CommandResponse,
    EventBatch,
    ModelImportRequest,
    ModelJobSummary,
    ModelSummary,
    PipelineDraftRequest,
    PipelineSummary,
    ReadinessResponse,
    ReconstructionJobRequest,
    ReconstructionJobSummary,
    RunCreateRequest,
    RunDetail,
    RunSummary,
    StageCheckpointSummary,
)
from backend.api.events import BoundedEventBroker
from backend.api.model_jobs import ModelJob, ModelJobDispatcher
from backend.api.reconstruction_jobs import ReconstructionJob, ReconstructionJobDispatcher
from backend.database.engine import transaction
from backend.database.records import (
    ArtifactMetadata,
    InspectionRunMetadata,
    ModelBundleMetadata,
    PipelineSnapshotMetadata,
    RunStageCheckpointMetadata,
)
from backend.database.repositories import MetadataRepository
from backend.domain.contracts import DiscSide, PipelineContract
from backend.services.center_reference_library import (
    CenterReferenceLibrary,
    CenterReferenceLibraryError,
    CenterReferenceStatus,
)
from backend.services.pipeline_lifecycle import (
    PipelineDraft,
    PipelineLifecycleError,
    PipelineLifecycleService,
)


@dataclass(frozen=True, slots=True)
class ApiServices:
    session_factory: sessionmaker[Session] | None
    commands: RunCommandDispatcher | None
    events: BoundedEventBroker
    model_jobs: ModelJobDispatcher | None = None
    pipelines: PipelineLifecycleService | None = None
    reconstruction_jobs: ReconstructionJobDispatcher | None = None
    center_references: CenterReferenceLibrary | None = None


def create_api_router(services: ApiServices) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/readiness", response_model=ReadinessResponse, tags=["system"])
    def readiness() -> ReadinessResponse:
        database_ready = _database_ready(services.session_factory)
        command_ready = services.commands is not None and services.commands.ready
        components: dict[str, Literal["ready", "not_ready"]] = {
            "database": "ready" if database_ready else "not_ready",
            "run_commands": "ready" if command_ready else "not_ready",
            "events": "ready",
        }
        return ReadinessResponse(
            status=(
                "ready" if all(value == "ready" for value in components.values()) else "not_ready"
            ),
            components=components,
        )

    @router.get("/models", response_model=tuple[ModelSummary, ...], tags=["models"])
    def list_models(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> tuple[ModelSummary, ...]:
        factory = _require_database(services)
        with transaction(factory) as session:
            repository = MetadataRepository(session)
            values = repository.list_model_bundles(
                limit=limit,
                offset=offset,
            )
            summaries = tuple(
                _model_summary(
                    value,
                    referenced=repository.count_pipeline_snapshots_for_model(value.model_bundle_id)
                    > 0,
                )
                for value in values
            )
        return summaries

    @router.post(
        "/models/import",
        response_model=ModelJobSummary,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["models"],
    )
    def import_model(request: ModelImportRequest) -> ModelJobSummary:
        jobs = _require_model_jobs(services)
        return _model_job_summary(jobs.submit_import(Path(request.source_path)))

    @router.post(
        "/models/{model_bundle_id}/archive",
        response_model=ModelJobSummary,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["models"],
    )
    def archive_model(model_bundle_id: str) -> ModelJobSummary:
        _require_model(services, model_bundle_id)
        return _model_job_summary(_require_model_jobs(services).submit_archive(model_bundle_id))

    @router.post(
        "/models/{model_bundle_id}/delete",
        response_model=ModelJobSummary,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["models"],
    )
    def delete_model(model_bundle_id: str) -> ModelJobSummary:
        _require_model(services, model_bundle_id)
        return _model_job_summary(_require_model_jobs(services).submit_delete(model_bundle_id))

    @router.get(
        "/model-jobs/{job_id}",
        response_model=ModelJobSummary,
        tags=["models"],
    )
    def get_model_job(job_id: str) -> ModelJobSummary:
        job = _require_model_jobs(services).get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="model job not found")
        return _model_job_summary(job)

    @router.post(
        "/reconstruction-jobs",
        response_model=ReconstructionJobSummary,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["reconstruction"],
    )
    def submit_reconstruction(request: ReconstructionJobRequest) -> ReconstructionJobSummary:
        jobs = _require_reconstruction_jobs(services)
        return _reconstruction_job_summary(
            jobs.submit(
                Path(request.source_path),
                DiscSide(request.side),
                request.preview_size,
            )
        )

    @router.get(
        "/center-references",
        response_model=tuple[CenterReferenceSummary, ...],
        tags=["reconstruction"],
    )
    def list_center_references() -> tuple[CenterReferenceSummary, ...]:
        library = _require_center_references(services)
        return tuple(_center_reference_summary(value) for value in library.statuses())

    @router.post(
        "/center-references/import",
        response_model=CenterReferenceSummary,
        tags=["reconstruction"],
    )
    def import_center_reference(
        request: CenterReferenceImportRequest,
    ) -> CenterReferenceSummary:
        library = _require_center_references(services)
        try:
            result = library.install(
                DiscSide(request.side),
                Path(request.source_path),
            )
        except CenterReferenceLibraryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _center_reference_summary(result)

    @router.get(
        "/reconstruction-jobs/{job_id}",
        response_model=ReconstructionJobSummary,
        tags=["reconstruction"],
    )
    def get_reconstruction_job(job_id: str) -> ReconstructionJobSummary:
        job = _require_reconstruction_jobs(services).get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="reconstruction job not found")
        return _reconstruction_job_summary(job)

    @router.get(
        "/reconstruction-jobs/{job_id}/preview",
        response_class=FileResponse,
        tags=["reconstruction"],
    )
    def get_reconstruction_preview(job_id: str) -> FileResponse:
        path = _require_reconstruction_jobs(services).preview_path(job_id)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="reconstruction preview not found")
        return FileResponse(path, media_type="image/png", filename="reconstructed-preview.png")

    @router.get(
        "/pipelines",
        response_model=tuple[PipelineSummary, ...],
        tags=["pipelines"],
    )
    def list_pipelines(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> tuple[PipelineSummary, ...]:
        factory = _require_database(services)
        with transaction(factory) as session:
            values = MetadataRepository(session).list_pipeline_snapshots(
                limit=limit,
                offset=offset,
            )
        return tuple(
            _pipeline_summary(
                value,
                services.pipelines.get_contract(value) if services.pipelines is not None else None,
            )
            for value in values
        )

    @router.get(
        "/pipelines/active",
        response_model=PipelineSummary | None,
        tags=["pipelines"],
    )
    def get_active_pipeline() -> PipelineSummary | None:
        factory = _require_database(services)
        lifecycle = _require_pipeline_lifecycle(services)
        with transaction(factory) as session:
            value = MetadataRepository(session).get_active_pipeline_snapshot()
        return None if value is None else _pipeline_summary(value, lifecycle.get_contract(value))

    @router.post(
        "/pipelines",
        response_model=PipelineSummary,
        status_code=status.HTTP_201_CREATED,
        tags=["pipelines"],
    )
    def create_pipeline_draft(request: PipelineDraftRequest) -> PipelineSummary:
        lifecycle = _require_pipeline_lifecycle(services)
        try:
            value = lifecycle.create_draft(
                PipelineDraft(
                    pipeline_id=request.pipeline_id,
                    display_name=request.display_name,
                    model_bundle_id=request.model_bundle_id,
                    acquisition=request.acquisition,
                    inference=request.inference,
                    reconstruction=request.reconstruction,
                )
            )
            return _pipeline_summary(value, lifecycle.get_contract(value))
        except PipelineLifecycleError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="pipeline identifier or revision already exists",
            ) from error

    @router.post(
        "/pipelines/{pipeline_snapshot_id}/validate",
        response_model=PipelineSummary,
        tags=["pipelines"],
    )
    def validate_pipeline(pipeline_snapshot_id: str) -> PipelineSummary:
        lifecycle = _require_pipeline_lifecycle(services)
        value = _pipeline_transition(lifecycle.validate, pipeline_snapshot_id)
        return _pipeline_summary(value, lifecycle.get_contract(value))

    @router.post(
        "/pipelines/{pipeline_snapshot_id}/activate",
        response_model=PipelineSummary,
        tags=["pipelines"],
    )
    def activate_pipeline(pipeline_snapshot_id: str) -> PipelineSummary:
        lifecycle = _require_pipeline_lifecycle(services)
        value = _pipeline_transition(
            lifecycle.approve_and_activate,
            pipeline_snapshot_id,
        )
        services.events.publish(
            event_type="pipeline_activated",
            message=f"{value.display_name} revision {value.revision}",
        )
        return _pipeline_summary(value, lifecycle.get_contract(value))

    @router.get("/runs", response_model=tuple[RunSummary, ...], tags=["runs"])
    def list_runs(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> tuple[RunSummary, ...]:
        factory = _require_database(services)
        with transaction(factory) as session:
            values = MetadataRepository(session).list_runs(limit=limit, offset=offset)
        return tuple(_run_summary(value) for value in values)

    @router.post(
        "/runs",
        response_model=RunSummary,
        status_code=status.HTTP_201_CREATED,
        tags=["runs"],
    )
    def create_run(request: RunCreateRequest) -> RunSummary:
        factory = _require_database(services)
        created = datetime.now(timezone.utc)
        value = InspectionRunMetadata(
            run_id=request.run_id,
            acquisition_id=request.acquisition_id,
            pipeline_snapshot_id=request.pipeline_snapshot_id,
            source=request.source.value,
            side=request.side.value,
            status="created",
            failure_code=None,
            created_at=created,
        )
        try:
            with transaction(factory) as session:
                repository = MetadataRepository(session)
                pipeline = repository.get_pipeline_snapshot(request.pipeline_snapshot_id)
                if pipeline is None:
                    raise HTTPException(status_code=404, detail="pipeline snapshot not found")
                if pipeline.state not in {"approved", "active"}:
                    raise HTTPException(
                        status_code=409,
                        detail="pipeline snapshot is not approved for runs",
                    )
                repository.add_run(value)
        except IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail="run identifier already exists",
            ) from error
        services.events.publish(event_type="run_created", run_id=request.run_id)
        return _run_summary(value)

    @router.get("/runs/{run_id}", response_model=RunDetail, tags=["runs"])
    def get_run(run_id: str) -> RunDetail:
        factory = _require_database(services)
        with transaction(factory) as session:
            repository = MetadataRepository(session)
            run = repository.get_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="run not found")
            checkpoints = repository.list_stage_checkpoints(run_id)
            artifacts = repository.list_artifacts(run_id)
        return RunDetail(
            run=_run_summary(run),
            checkpoints=tuple(_checkpoint_summary(value) for value in checkpoints),
            artifacts=tuple(_artifact_summary(value) for value in artifacts),
        )

    @router.get(
        "/runs/{run_id}/artifacts",
        response_model=tuple[ArtifactSummary, ...],
        tags=["runs"],
    )
    def list_run_artifacts(run_id: str) -> tuple[ArtifactSummary, ...]:
        factory = _require_database(services)
        with transaction(factory) as session:
            repository = MetadataRepository(session)
            if repository.get_run(run_id) is None:
                raise HTTPException(status_code=404, detail="run not found")
            artifacts = repository.list_artifacts(run_id)
        return tuple(_artifact_summary(value) for value in artifacts)

    @router.post(
        "/runs/{run_id}/start",
        response_model=CommandResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["commands"],
    )
    def start_run(run_id: str) -> CommandResponse:
        factory = _require_database(services)
        commands = _require_commands(services)
        with transaction(factory) as session:
            run = MetadataRepository(session).get_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="run not found")
            if run.status not in {"created", "failed"}:
                raise HTTPException(status_code=409, detail="run cannot be started")
        if not commands.submit(run_id):
            raise HTTPException(status_code=409, detail="run is already queued or queue is full")
        return CommandResponse(run_id=run_id, command="start", accepted=True)

    @router.post(
        "/runs/{run_id}/cancel",
        response_model=CommandResponse,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["commands"],
    )
    def cancel_run(run_id: str) -> CommandResponse:
        factory = _require_database(services)
        commands = _require_commands(services)
        with transaction(factory) as session:
            run = MetadataRepository(session).get_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="run not found")
            if run.status in {"completed", "cancelled"}:
                raise HTTPException(status_code=409, detail="run is already terminal")
        commands.cancel(run_id)
        return CommandResponse(run_id=run_id, command="cancel", accepted=True)

    @router.get("/events", response_model=EventBatch, tags=["events"])
    def read_events(
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> EventBatch:
        return services.events.read(after_sequence=after_sequence, limit=limit)

    return router


def _require_database(services: ApiServices) -> sessionmaker[Session]:
    if services.session_factory is None:
        raise HTTPException(status_code=503, detail="database service is not configured")
    return services.session_factory


def _require_commands(services: ApiServices) -> RunCommandDispatcher:
    if services.commands is None or not services.commands.ready:
        raise HTTPException(status_code=503, detail="run command service is not ready")
    return services.commands


def _require_model_jobs(services: ApiServices) -> ModelJobDispatcher:
    if services.model_jobs is None or not services.model_jobs.ready:
        raise HTTPException(status_code=503, detail="model library service is not ready")
    return services.model_jobs


def _require_pipeline_lifecycle(services: ApiServices) -> PipelineLifecycleService:
    if services.pipelines is None:
        raise HTTPException(status_code=503, detail="pipeline service is not ready")
    return services.pipelines


def _pipeline_transition(
    operation: Callable[[str], PipelineSnapshotMetadata],
    pipeline_snapshot_id: str,
) -> PipelineSnapshotMetadata:
    try:
        return operation(pipeline_snapshot_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="pipeline snapshot not found") from error
    except PipelineLifecycleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _require_model(services: ApiServices, model_bundle_id: str) -> None:
    factory = _require_database(services)
    with transaction(factory) as session:
        if MetadataRepository(session).get_model_bundle(model_bundle_id) is None:
            raise HTTPException(status_code=404, detail="model bundle not found")


def _database_ready(factory: sessionmaker[Session] | None) -> bool:
    if factory is None:
        return False
    try:
        with transaction(factory) as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _model_summary(
    value: ModelBundleMetadata,
    *,
    referenced: bool = False,
) -> ModelSummary:
    return ModelSummary(
        model_bundle_id=value.model_bundle_id,
        display_name=value.display_name,
        model_version=value.model_version,
        state=value.state,
        sha256=value.sha256,
        created_at=value.created_at,
        referenced_by_pipelines=referenced,
        can_archive=value.state != "active" and not referenced,
        can_delete=value.state == "retired" and not referenced,
    )


def _model_job_summary(value: ModelJob) -> ModelJobSummary:
    return ModelJobSummary(
        job_id=value.job_id,
        action=value.action,
        status=value.status,
        model_bundle_id=value.model_bundle_id,
        message=value.message,
    )


def _require_reconstruction_jobs(services: ApiServices) -> ReconstructionJobDispatcher:
    if services.reconstruction_jobs is None:
        raise HTTPException(status_code=503, detail="reconstruction service is not ready")
    return services.reconstruction_jobs


def _require_center_references(services: ApiServices) -> CenterReferenceLibrary:
    if services.center_references is None:
        raise HTTPException(status_code=503, detail="center reference service is not ready")
    return services.center_references


def _center_reference_summary(value: CenterReferenceStatus) -> CenterReferenceSummary:
    return CenterReferenceSummary(
        side=cast(Literal["upper", "lower"], value.side.value),
        profile_id=value.profile_id,
        installed=value.installed,
        relative_path=value.relative_path,
        sha256=value.sha256,
        message=value.message,
    )


def _reconstruction_job_summary(value: ReconstructionJob) -> ReconstructionJobSummary:
    result = value.result
    return ReconstructionJobSummary(
        job_id=value.job_id,
        status=value.status,
        stage=value.stage,
        progress_current=value.progress_current,
        progress_total=value.progress_total,
        acquisition_id=None if result is None else result.acquisition_id,
        production_approved=None if result is None else result.production_approved,
        validation_median_px=None if result is None else result.validation_median_px,
        validation_p95_px=None if result is None else result.validation_p95_px,
        validation_maximum_px=None if result is None else result.validation_maximum_px,
        passed_join_count=None if result is None else result.passed_join_count,
        total_join_count=None if result is None else result.total_join_count,
        preview_url=(
            None if result is None else f"/api/v1/reconstruction-jobs/{value.job_id}/preview"
        ),
        preview_relative_path=None if result is None else result.preview.relative_path,
        report_relative_path=None if result is None else result.report_relative_path,
        preview_width=None if result is None else result.preview.width,
        preview_height=None if result is None else result.preview.height,
        center_completion_applied=(None if result is None else result.center_completion_applied),
        center_profile_id=None if result is None else result.center_profile_id,
        center_rotation_degrees=(None if result is None else result.center_rotation_degrees),
        center_fill_pixels=None if result is None else result.center_fill_pixels,
        message=value.message,
    )


def _pipeline_summary(
    value: PipelineSnapshotMetadata,
    contract: PipelineContract | None,
) -> PipelineSummary:
    inference_enabled = (
        contract.inference.enabled if contract is not None else value.model_bundle_id is not None
    )
    reconstruction_enabled = contract.reconstruction.enabled if contract is not None else True
    inference_mode = (
        contract.inference.mode.value
        if contract is not None and contract.inference.mode is not None
        else None
    )
    acquisition_mode = contract.acquisition.mode.value if contract is not None else "manual_folder"
    expected_frame_count = contract.acquisition.expected_frame_count if contract is not None else 16
    filename_template = (
        contract.acquisition.automatic.filename_template
        if contract is not None and contract.acquisition.automatic is not None
        else None
    )
    return PipelineSummary(
        pipeline_snapshot_id=value.pipeline_snapshot_id,
        pipeline_id=value.pipeline_id,
        revision=value.revision,
        display_name=value.display_name,
        state=value.state,
        model_bundle_id=value.model_bundle_id,
        acquisition_mode=acquisition_mode,
        expected_frame_count=expected_frame_count,
        filename_template=filename_template,
        reconstruction_enabled=reconstruction_enabled,
        inference_enabled=inference_enabled,
        inference_mode=inference_mode,
        can_validate=value.state == "draft",
        can_activate=value.state in {"validated", "approved"},
        sha256=value.sha256,
        created_at=value.created_at,
    )


def _run_summary(value: InspectionRunMetadata) -> RunSummary:
    return RunSummary(**asdict(value))


def _checkpoint_summary(value: RunStageCheckpointMetadata) -> StageCheckpointSummary:
    payload = asdict(value)
    payload.pop("run_id")
    return StageCheckpointSummary(**payload)


def _artifact_summary(value: ArtifactMetadata) -> ArtifactSummary:
    payload = asdict(value)
    payload.pop("run_id")
    return ArtifactSummary(**payload)
