"""Portable resource and writable-data path resolution."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from backend.domain.value_objects import normalize_relative_path

DATA_ROOT_ENVIRONMENT_VARIABLE = "PRODUCTION_DATA_ROOT"
DATA_DIRECTORY_NAMES = (
    "configuration",
    "pipelines",
    "models",
    "incoming",
    "processing",
    "completed",
    "failed",
    "database",
    "logs",
    "temp",
)


class PathContainmentError(ValueError):
    """Raised when a path would escape an approved application root."""


def _contained_path(root: Path, relative_path: str) -> Path:
    normalized = normalize_relative_path(relative_path)
    candidate = (root / Path(*normalized.split("/"))).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PathContainmentError("resolved path escapes its approved root") from error
    return candidate


@dataclass(frozen=True, slots=True)
class ApplicationPaths:
    """Resolved application roots with strict containment helpers."""

    resource_root: Path
    data_root: Path

    def __post_init__(self) -> None:
        if not self.resource_root.is_absolute() or not self.data_root.is_absolute():
            raise ValueError("application roots must be absolute paths")

    @classmethod
    def resolve(
        cls,
        *,
        resource_root: Path,
        data_root: Path | str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> ApplicationPaths:
        if not resource_root.is_absolute():
            raise ValueError("resource root must be supplied as an absolute path")
        resolved_resource_root = resource_root.resolve(strict=False)
        selected_environment = os.environ if environment is None else environment
        environment_value = selected_environment.get(DATA_ROOT_ENVIRONMENT_VARIABLE)
        selected_root = data_root if data_root is not None else environment_value

        if selected_root is None:
            candidate = resolved_resource_root / "data"
        else:
            if isinstance(selected_root, str) and not selected_root.strip():
                raise ValueError("configured production data root must not be blank")
            candidate = Path(selected_root)
            if not candidate.is_absolute():
                candidate = resolved_resource_root / candidate

        return cls(
            resource_root=resolved_resource_root,
            data_root=candidate.resolve(strict=False),
        )

    def ensure_data_layout(self) -> tuple[Path, ...]:
        """Create the approved writable directory layout explicitly."""

        self.data_root.mkdir(parents=True, exist_ok=True)
        directories = tuple(self.data_root / name for name in DATA_DIRECTORY_NAMES)
        for directory in directories:
            directory.mkdir(exist_ok=True)
        return directories

    def data_directory(self, name: str) -> Path:
        if name not in DATA_DIRECTORY_NAMES:
            raise KeyError(f"unknown data directory: {name}")
        return _contained_path(self.data_root, name)

    def resolve_data_path(self, relative_path: str) -> Path:
        return _contained_path(self.data_root, relative_path)

    def resolve_resource_path(self, relative_path: str) -> Path:
        return _contained_path(self.resource_root, relative_path)

    def to_data_relative_path(self, path: Path) -> str:
        candidate = path.resolve(strict=False)
        try:
            relative = candidate.relative_to(self.data_root)
        except ValueError as error:
            raise PathContainmentError("path is outside the approved data root") from error
        if not relative.parts:
            raise PathContainmentError("data root itself is not a storable file path")
        return normalize_relative_path(relative.as_posix())
