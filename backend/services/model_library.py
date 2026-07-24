"""Protected archive and deletion rules for application-owned model bundles."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.records import ModelBundleMetadata
from backend.database.repositories import MetadataRepository


class ModelLibraryError(RuntimeError):
    """Raised when a model-library mutation would violate lifecycle safety."""


class ModelLibraryService:
    def __init__(
        self,
        *,
        paths: ApplicationPaths,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory

    def archive(self, model_bundle_id: str) -> ModelBundleMetadata:
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            current = _required(repository, model_bundle_id)
            if current.state == "active":
                raise ModelLibraryError("the active production model cannot be archived")
            if repository.count_pipeline_snapshots_for_model(model_bundle_id) > 0:
                raise ModelLibraryError("a model used by a saved pipeline cannot be archived")
            if current.state != "retired":
                repository.set_model_bundle_state(model_bundle_id, "retired")
            return _required(repository, model_bundle_id)

    def delete_archived(self, model_bundle_id: str) -> None:
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            current = _required(repository, model_bundle_id)
            if current.state != "retired":
                raise ModelLibraryError("archive the model before deleting it")
            if repository.count_pipeline_snapshots_for_model(model_bundle_id) > 0:
                raise ModelLibraryError("a model used by a saved pipeline cannot be deleted")

        owned_directory = self._owned_model_directory(current)
        trash_root = self._paths.resolve_data_path("models/.trash")
        trash_root.mkdir(parents=True, exist_ok=True)
        trash = trash_root / f"{model_bundle_id}-{uuid.uuid4().hex}"
        os.replace(owned_directory, trash)
        try:
            with transaction(self._session_factory) as session:
                MetadataRepository(session).delete_model_bundle(model_bundle_id)
        except BaseException:
            os.replace(trash, owned_directory)
            raise
        shutil.rmtree(trash)

    def _owned_model_directory(self, value: ModelBundleMetadata) -> Path:
        manifest = self._paths.resolve_data_path(value.manifest_path)
        directory = manifest.parent
        expected = self._paths.resolve_data_path(f"models/{value.model_bundle_id}")
        if directory != expected or not manifest.is_file():
            raise ModelLibraryError("owned model files are missing or inconsistent")
        return directory


def _required(
    repository: MetadataRepository,
    model_bundle_id: str,
) -> ModelBundleMetadata:
    value = repository.get_model_bundle(model_bundle_id)
    if value is None:
        raise ModelLibraryError("model bundle was not found")
    return value
