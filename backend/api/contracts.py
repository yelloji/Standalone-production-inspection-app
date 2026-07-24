"""Versioned immutable HTTP request and response contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from backend.domain.contracts import (
    AcquisitionConfiguration,
    AcquisitionSource,
    DiscSide,
    InferenceConfiguration,
    ReconstructionConfiguration,
)
from backend.domain.value_objects import ContractIdentifier, SafeRelativePath, Sha256Hex


class ApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class HealthResponse(ApiContract):
    status: Literal["ready"]
    service: str
    version: str


class ReadinessResponse(ApiContract):
    status: Literal["ready", "not_ready"]
    components: dict[str, Literal["ready", "not_ready"]]


class ModelSummary(ApiContract):
    model_bundle_id: str
    display_name: str
    model_version: str
    state: str
    sha256: Sha256Hex
    created_at: AwareDatetime
    referenced_by_pipelines: bool = False
    can_archive: bool = False
    can_delete: bool = False


class ModelImportRequest(ApiContract):
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]


class ModelJobSummary(ApiContract):
    job_id: str
    action: Literal["import", "archive", "delete"]
    status: Literal["queued", "running", "completed", "failed"]
    model_bundle_id: str | None = None
    message: Annotated[str, Field(max_length=500)] | None = None


class ReconstructionJobRequest(ApiContract):
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    side: Literal["upper", "lower"]
    preview_size: Literal[3000, 4000, 5000] = 5000


class CenterReferenceImportRequest(ApiContract):
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    side: Literal["upper", "lower"]


class CenterReferenceSummary(ApiContract):
    side: Literal["upper", "lower"]
    profile_id: str
    installed: bool
    relative_path: SafeRelativePath
    sha256: Sha256Hex | None = None
    message: Annotated[str, Field(max_length=500)]


class ReconstructionJobSummary(ApiContract):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    progress_current: Annotated[int, Field(ge=0)]
    progress_total: Annotated[int, Field(ge=1)]
    acquisition_id: str | None = None
    production_approved: bool | None = None
    validation_median_px: float | None = None
    validation_p95_px: float | None = None
    validation_maximum_px: float | None = None
    passed_join_count: int | None = None
    total_join_count: int | None = None
    preview_url: str | None = None
    preview_relative_path: str | None = None
    report_relative_path: str | None = None
    preview_width: int | None = None
    preview_height: int | None = None
    center_completion_applied: bool | None = None
    center_profile_id: str | None = None
    center_rotation_degrees: float | None = None
    center_fill_pixels: int | None = None
    message: Annotated[str, Field(max_length=1000)] | None = None


class PipelineSummary(ApiContract):
    pipeline_snapshot_id: str
    pipeline_id: str
    revision: int
    display_name: str
    state: str
    model_bundle_id: str | None
    acquisition_mode: str
    expected_frame_count: int
    filename_template: str | None
    reconstruction_enabled: bool
    inference_enabled: bool
    inference_mode: str | None
    can_validate: bool
    can_activate: bool
    sha256: Sha256Hex
    created_at: AwareDatetime


class PipelineDraftRequest(ApiContract):
    pipeline_id: ContractIdentifier
    display_name: Annotated[str, Field(min_length=1, max_length=500)]
    model_bundle_id: ContractIdentifier | None = None
    acquisition: AcquisitionConfiguration
    inference: InferenceConfiguration
    reconstruction: ReconstructionConfiguration


class RunCreateRequest(ApiContract):
    run_id: ContractIdentifier
    acquisition_id: ContractIdentifier
    pipeline_snapshot_id: ContractIdentifier
    source: AcquisitionSource
    side: DiscSide


class RunSummary(ApiContract):
    run_id: str
    acquisition_id: str
    pipeline_snapshot_id: str
    source: str
    side: str
    status: str
    failure_code: str | None
    created_at: AwareDatetime
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None


class StageCheckpointSummary(ApiContract):
    stage_name: str
    status: str
    attempt_count: int
    evidence_path: SafeRelativePath | None
    evidence_sha256: Sha256Hex | None
    failure_code: str | None
    updated_at: AwareDatetime


class ArtifactSummary(ApiContract):
    artifact_id: str
    kind: str
    relative_path: SafeRelativePath
    sha256: Sha256Hex
    size_bytes: int
    media_type: str
    created_at: AwareDatetime


class RunDetail(ApiContract):
    run: RunSummary
    checkpoints: tuple[StageCheckpointSummary, ...]
    artifacts: tuple[ArtifactSummary, ...]


class CommandResponse(ApiContract):
    run_id: str
    command: Literal["start", "cancel"]
    accepted: Literal[True]


class RunEvent(ApiContract):
    sequence: Annotated[int, Field(ge=1)]
    occurred_at: AwareDatetime
    event_type: ContractIdentifier
    run_id: ContractIdentifier | None = None
    stage: str | None = None
    progress_current: Annotated[int, Field(ge=0)] | None = None
    progress_total: Annotated[int, Field(ge=1)] | None = None
    message: Annotated[str, Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def validate_progress(self) -> RunEvent:
        if (self.progress_current is None) != (self.progress_total is None):
            raise ValueError("event progress current and total must be present together")
        if (
            self.progress_current is not None
            and self.progress_total is not None
            and self.progress_current > self.progress_total
        ):
            raise ValueError("event progress cannot exceed its total")
        return self


class EventBatch(ApiContract):
    events: tuple[RunEvent, ...]
    latest_sequence: Annotated[int, Field(ge=0)]
    gap_detected: bool
