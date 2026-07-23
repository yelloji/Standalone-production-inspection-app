"""Explicit approval, activation, and rollback-safe model lifecycle tests."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.repositories import MetadataRepository
from backend.services.model_import import ModelImportService
from backend.services.model_lifecycle import ModelLifecycleError, ModelLifecycleService
from tests.backend.model_bundle_factory import create_model_bundle


def test_approval_activation_and_rollback_preserve_both_models(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    importer = ModelImportService(
        paths=application_paths,
        session_factory=session_factory,
    )
    first = importer.import_bundle(
        create_model_bundle(tmp_path / "first", model_bundle_id="model-first")
    )
    second = importer.import_bundle(
        create_model_bundle(tmp_path / "second", model_bundle_id="model-second")
    )
    lifecycle = ModelLifecycleService(session_factory)

    lifecycle.approve(first.model_bundle_id)
    lifecycle.activate(first.model_bundle_id)
    lifecycle.approve(second.model_bundle_id)
    lifecycle.activate(second.model_bundle_id)
    rolled_back = lifecycle.activate(first.model_bundle_id)

    assert rolled_back.state == "active"
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        assert repository.get_model_bundle("model-first").state == "active"  # type: ignore[union-attr]
        assert repository.get_model_bundle("model-second").state == "approved"  # type: ignore[union-attr]
    assert application_paths.resolve_data_path(first.manifest_path).is_file()
    assert application_paths.resolve_data_path(second.manifest_path).is_file()


def test_valid_model_cannot_activate_without_approval(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    imported = ModelImportService(
        paths=application_paths,
        session_factory=session_factory,
    ).import_bundle(create_model_bundle(tmp_path / "bundle"))

    with pytest.raises(ModelLifecycleError, match="approved"):
        ModelLifecycleService(session_factory).activate(imported.model_bundle_id)
