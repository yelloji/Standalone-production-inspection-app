"""Validated atomic JSON configuration persistence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from backend.core.paths import ApplicationPaths
from backend.core.serialization import (
    canonical_checksum,
    canonical_json_bytes,
    validate_json_model,
)

ConfigurationT = TypeVar("ConfigurationT", bound=BaseModel)


class AtomicConfigurationStore(Generic[ConfigurationT]):
    """Persist one validated configuration type beneath the application data root."""

    def __init__(
        self,
        *,
        paths: ApplicationPaths,
        model_type: type[ConfigurationT],
    ) -> None:
        self._paths = paths
        self._model_type = model_type

    def load(self, relative_path: str) -> ConfigurationT:
        target = self._paths.resolve_data_path(relative_path)
        return validate_json_model(target.read_bytes(), self._model_type)

    def save(self, relative_path: str, value: ConfigurationT) -> str:
        if not isinstance(value, self._model_type):
            raise TypeError(f"expected configuration type {self._model_type.__name__}")

        target = self._paths.resolve_data_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json_bytes(value)
        temporary_path: Path | None = None

        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return canonical_checksum(value)
