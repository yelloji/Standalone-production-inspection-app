"""Strict, versioned contracts used across production application boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from backend.domain.value_objects import (
    ContractIdentifier,
    SafeRelativePath,
    Sha256Hex,
)

SchemaVersion = Literal[1]
NonEmptyText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, strip_whitespace=True),
]
PositiveDimension = Annotated[int, Field(ge=1, le=1_000_000)]
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]


class ContractModel(BaseModel):
    """Immutable contract base that rejects accidental schema expansion."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class AcquisitionSource(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"


class DiscSide(str, Enum):
    UPPER = "upper"
    LOWER = "lower"
    NOT_APPLICABLE = "not_applicable"


class InferenceMode(str, Enum):
    DIRECT = "direct"
    SAHI = "sahi"


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ArtifactKind(str, Enum):
    SOURCE_IMAGE = "source_image"
    RECONSTRUCTED_IMAGE = "reconstructed_image"
    PREDICTION = "prediction"
    MASK = "mask"
    REPORT = "report"
    DIAGNOSTIC = "diagnostic"


class ErrorSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BoundingBox(ContractModel):
    """Axis-aligned pixel bounding box."""

    x: Annotated[float, Field(ge=0)]
    y: Annotated[float, Field(ge=0)]
    width: Annotated[float, Field(gt=0)]
    height: Annotated[float, Field(gt=0)]


class SahiConfiguration(ContractModel):
    """SAHI slicing parameters captured in an immutable pipeline snapshot."""

    slice_width: PositiveDimension = 1312
    slice_height: PositiveDimension = 1312
    overlap_width_ratio: UnitInterval = 0.5
    overlap_height_ratio: UnitInterval = 0.5
    batch_size: Annotated[int, Field(ge=1, le=1024)] = 1


class InferenceConfiguration(ContractModel):
    mode: InferenceMode
    confidence_threshold: UnitInterval
    sahi: SahiConfiguration | None = None

    @model_validator(mode="after")
    def validate_mode_configuration(self) -> InferenceConfiguration:
        if self.mode is InferenceMode.SAHI and self.sahi is None:
            raise ValueError("SAHI mode requires slicing configuration")
        if self.mode is InferenceMode.DIRECT and self.sahi is not None:
            raise ValueError("direct mode must not include SAHI configuration")
        return self


class AcquisitionConfiguration(ContractModel):
    source: AcquisitionSource
    expected_frame_count: Annotated[int, Field(ge=1, le=100_000)]
    ordered: bool = True
    side: DiscSide = DiscSide.NOT_APPLICABLE


class ReconstructionConfiguration(ContractModel):
    enabled: bool
    segment_count: Annotated[int, Field(ge=1, le=100_000)] | None = None
    degrees_per_segment: Annotated[float, Field(gt=0, le=360)] | None = None

    @model_validator(mode="after")
    def validate_enabled_configuration(self) -> ReconstructionConfiguration:
        values = (self.segment_count, self.degrees_per_segment)
        if self.enabled and any(value is None for value in values):
            raise ValueError("enabled reconstruction requires segment count and angle")
        if not self.enabled and any(value is not None for value in values):
            raise ValueError("disabled reconstruction must not define segment geometry")
        if (
            self.enabled
            and self.segment_count is not None
            and self.degrees_per_segment is not None
            and abs(self.segment_count * self.degrees_per_segment - 360.0) > 1e-6
        ):
            raise ValueError("reconstruction segment geometry must cover exactly 360 degrees")
        return self


class ModelBundleContract(ContractModel):
    schema_version: SchemaVersion = 1
    model_bundle_id: ContractIdentifier
    display_name: NonEmptyText
    model_version: NonEmptyText
    model_path: SafeRelativePath
    model_sha256: Sha256Hex
    input_width: PositiveDimension
    input_height: PositiveDimension
    class_names: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def validate_classes(self) -> ModelBundleContract:
        if not self.class_names:
            raise ValueError("model bundle requires at least one class")
        if len(set(self.class_names)) != len(self.class_names):
            raise ValueError("model class names must be unique")
        return self


class PipelineContract(ContractModel):
    schema_version: SchemaVersion = 1
    pipeline_id: ContractIdentifier
    revision: Annotated[int, Field(ge=1)]
    display_name: NonEmptyText
    model_bundle_id: ContractIdentifier
    acquisition: AcquisitionConfiguration
    inference: InferenceConfiguration
    reconstruction: ReconstructionConfiguration


class AcquisitionContract(ContractModel):
    schema_version: SchemaVersion = 1
    acquisition_id: ContractIdentifier
    source: AcquisitionSource
    side: DiscSide
    captured_at: AwareDatetime
    frame_paths: tuple[SafeRelativePath, ...]

    @model_validator(mode="after")
    def validate_frames(self) -> AcquisitionContract:
        if not self.frame_paths:
            raise ValueError("acquisition requires at least one source frame")
        if len(set(self.frame_paths)) != len(self.frame_paths):
            raise ValueError("acquisition frame paths must be unique")
        return self


class ErrorContract(ContractModel):
    schema_version: SchemaVersion = 1
    code: ContractIdentifier
    severity: ErrorSeverity
    operator_message: NonEmptyText
    technical_detail: str | None = None
    retryable: bool = False


class StageContract(ContractModel):
    schema_version: SchemaVersion = 1
    stage_id: ContractIdentifier
    name: NonEmptyText
    status: StageStatus
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    error: ErrorContract | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> StageContract:
        if self.finished_at is not None and self.started_at is None:
            raise ValueError("finished stage requires a start time")
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("stage finish time must not precede start time")
        if self.status is StageStatus.FAILED and self.error is None:
            raise ValueError("failed stage requires an error")
        if self.status is not StageStatus.FAILED and self.error is not None:
            raise ValueError("only failed stages may contain an error")
        return self


class RunContract(ContractModel):
    schema_version: SchemaVersion = 1
    run_id: ContractIdentifier
    acquisition_id: ContractIdentifier
    pipeline_id: ContractIdentifier
    pipeline_revision: Annotated[int, Field(ge=1)]
    pipeline_sha256: Sha256Hex
    status: RunStatus
    created_at: AwareDatetime
    stages: tuple[StageContract, ...] = ()

    @model_validator(mode="after")
    def validate_stage_ids(self) -> RunContract:
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("run stage identifiers must be unique")
        return self


class TransformContract(ContractModel):
    schema_version: SchemaVersion = 1
    transform_id: ContractIdentifier
    source_frame_index: Annotated[int, Field(ge=0)]
    segment_index: Annotated[int, Field(ge=0)]
    angle_degrees: Annotated[float, Field(ge=0, lt=360)]
    source_to_output_matrix: tuple[
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
    ]


class PredictionContract(ContractModel):
    schema_version: SchemaVersion = 1
    prediction_id: ContractIdentifier
    class_name: NonEmptyText
    confidence: UnitInterval
    source_frame_index: Annotated[int, Field(ge=0)]
    source_box: BoundingBox
    transform_id: ContractIdentifier | None = None


class ArtifactContract(ContractModel):
    schema_version: SchemaVersion = 1
    artifact_id: ContractIdentifier
    kind: ArtifactKind
    relative_path: SafeRelativePath
    sha256: Sha256Hex
    size_bytes: Annotated[int, Field(ge=0)]
    media_type: NonEmptyText
    created_at: AwareDatetime


class ApplicationConfiguration(ContractModel):
    """Minimal persisted application configuration; expanded by later tasks."""

    schema_version: SchemaVersion = 1
    configuration_revision: Annotated[int, Field(ge=1)] = 1
    active_pipeline_id: ContractIdentifier | None = None
    updated_at: AwareDatetime


def utc_now() -> datetime:
    """Return an aware timestamp for composition layers."""

    return datetime.now(timezone.utc)
