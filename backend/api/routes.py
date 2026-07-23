"""Thin typed local API routes over repositories and command dispatch."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.api.commands import RunCommandDispatcher
from backend.api.contracts import (
    ArtifactSummary,
    CommandResponse,
    EventBatch,
    ModelSummary,
    PipelineSummary,
    ReadinessResponse,
    RunCreateRequest,
    RunDetail,
    RunSummary,
    StageCheckpointSummary,
)
from backend.api.events import BoundedEventBroker
from backend.database.engine import transaction
from backend.database.records import (
    ArtifactMetadata,
    InspectionRunMetadata,
    ModelBundleMetadata,
    PipelineSnapshotMetadata,
    RunStageCheckpointMetadata,
)
from backend.database.repositories import MetadataRepository


@dataclass(frozen=True, slots=True)
class ApiServices:
    session_factory: sessionmaker[Session] | None
    commands: RunCommandDispatcher | None
    events: BoundedEventBroker


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
            values = MetadataRepository(session).list_model_bundles(
                limit=limit,
                offset=offset,
            )
        return tuple(_model_summary(value) for value in values)

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
        return tuple(_pipeline_summary(value) for value in values)

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


def _database_ready(factory: sessionmaker[Session] | None) -> bool:
    if factory is None:
        return False
    try:
        with transaction(factory) as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _model_summary(value: ModelBundleMetadata) -> ModelSummary:
    return ModelSummary(
        model_bundle_id=value.model_bundle_id,
        display_name=value.display_name,
        model_version=value.model_version,
        state=value.state,
        sha256=value.sha256,
        created_at=value.created_at,
    )


def _pipeline_summary(value: PipelineSnapshotMetadata) -> PipelineSummary:
    return PipelineSummary(
        pipeline_snapshot_id=value.pipeline_snapshot_id,
        pipeline_id=value.pipeline_id,
        revision=value.revision,
        display_name=value.display_name,
        state=value.state,
        model_bundle_id=value.model_bundle_id,
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
