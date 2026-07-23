"""Framework-neutral metadata records accepted and returned by repositories."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from backend.domain.value_objects import normalize_relative_path

_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _validate_checksum(value: str) -> None:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("metadata SHA-256 must contain 64 lowercase hexadecimal characters")


def _validate_timestamp(value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("metadata timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ModelBundleMetadata:
    model_bundle_id: str
    display_name: str
    model_version: str
    state: str
    manifest_path: str
    sha256: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "manifest_path",
            normalize_relative_path(self.manifest_path),
        )
        _validate_checksum(self.sha256)
        _validate_timestamp(self.created_at)


@dataclass(frozen=True, slots=True)
class PipelineSnapshotMetadata:
    pipeline_snapshot_id: str
    pipeline_id: str
    revision: int
    display_name: str
    state: str
    model_bundle_id: str
    contract_path: str
    sha256: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "contract_path",
            normalize_relative_path(self.contract_path),
        )
        _validate_checksum(self.sha256)
        _validate_timestamp(self.created_at)


@dataclass(frozen=True, slots=True)
class InspectionRunMetadata:
    run_id: str
    acquisition_id: str
    pipeline_snapshot_id: str
    source: str
    side: str
    status: str
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_timestamp(self.created_at)
        _validate_timestamp(self.started_at)
        _validate_timestamp(self.finished_at)


@dataclass(frozen=True, slots=True)
class SourceFrameMetadata:
    source_frame_id: str
    run_id: str
    frame_index: int
    relative_path: str
    sha256: str
    width: int
    height: int
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relative_path",
            normalize_relative_path(self.relative_path),
        )
        _validate_checksum(self.sha256)
        _validate_timestamp(self.created_at)


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    artifact_id: str
    run_id: str
    kind: str
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relative_path",
            normalize_relative_path(self.relative_path),
        )
        _validate_checksum(self.sha256)
        _validate_timestamp(self.created_at)
