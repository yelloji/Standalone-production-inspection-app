from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.repositories import MetadataRepository
from backend.services.model_import import ModelImportService
from backend.services.model_library import ModelLibraryError, ModelLibraryService
from tests.backend.database.factories import pipeline_snapshot
from tests.backend.model_bundle_factory import create_model_bundle


def test_archive_then_delete_removes_only_unreferenced_owned_model(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    imported = ModelImportService(
        paths=application_paths,
        session_factory=session_factory,
    ).import_bundle(create_model_bundle(tmp_path / "bundle"))
    library = ModelLibraryService(
        paths=application_paths,
        session_factory=session_factory,
    )
    owned_directory = application_paths.resolve_data_path(imported.manifest_path).parent

    archived = library.archive(imported.model_bundle_id)
    assert archived.state == "retired"
    assert owned_directory.is_dir()

    library.delete_archived(imported.model_bundle_id)

    assert not owned_directory.exists()
    with transaction(session_factory) as session:
        assert MetadataRepository(session).get_model_bundle(imported.model_bundle_id) is None


def test_active_and_referenced_models_are_protected(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    importer = ModelImportService(
        paths=application_paths,
        session_factory=session_factory,
    )
    active = importer.import_bundle(
        create_model_bundle(tmp_path / "active", model_bundle_id="active-model")
    )
    referenced = importer.import_bundle(
        create_model_bundle(tmp_path / "referenced", model_bundle_id="referenced-model")
    )
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        repository.set_model_bundle_state(active.model_bundle_id, "active")
        repository.add_pipeline_snapshot(
            pipeline_snapshot(model_bundle_id=referenced.model_bundle_id)
        )

    library = ModelLibraryService(
        paths=application_paths,
        session_factory=session_factory,
    )
    with pytest.raises(ModelLibraryError, match="active production"):
        library.archive(active.model_bundle_id)
    with pytest.raises(ModelLibraryError, match="saved pipeline"):
        library.archive(referenced.model_bundle_id)


def test_delete_requires_archive_first(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    imported = ModelImportService(
        paths=application_paths,
        session_factory=session_factory,
    ).import_bundle(create_model_bundle(tmp_path / "bundle"))

    with pytest.raises(ModelLibraryError, match="archive"):
        ModelLibraryService(
            paths=application_paths,
            session_factory=session_factory,
        ).delete_archived(imported.model_bundle_id)
