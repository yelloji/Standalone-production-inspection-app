"""Safe staged directory/ZIP model import tests."""

import zipfile
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.repositories import MetadataRepository
from backend.services.model_import import ModelImportError, ModelImportService
from tests.backend.model_bundle_factory import create_model_bundle, zip_bundle


def test_directory_import_copies_and_registers_owned_bundle(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    source = create_model_bundle(tmp_path / "external-bundle")
    service = ModelImportService(paths=application_paths, session_factory=session_factory)

    imported = service.import_bundle(source)
    source.rename(tmp_path / "source-was-removed")

    owned_manifest = application_paths.resolve_data_path(imported.manifest_path)
    assert imported.state == "valid"
    assert owned_manifest.is_file()
    assert owned_manifest.parent.joinpath("model.onnx").is_file()
    with transaction(session_factory) as session:
        assert MetadataRepository(session).get_model_bundle("crack-detector-v1") == imported


def test_zip_import_succeeds(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    bundle = create_model_bundle(tmp_path / "bundle", model_bundle_id="zip-model")
    archive = zip_bundle(bundle, tmp_path / "bundle.zip")

    imported = ModelImportService(
        paths=application_paths,
        session_factory=session_factory,
    ).import_bundle(archive)

    assert imported.model_bundle_id == "zip-model"
    assert application_paths.resolve_data_path(imported.manifest_path).is_file()


def test_zip_traversal_is_rejected_and_staging_is_cleaned(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.txt", "unsafe")

    with pytest.raises(ValueError):
        ModelImportService(
            paths=application_paths,
            session_factory=session_factory,
        ).import_bundle(archive)

    staging = application_paths.resolve_data_path("models/.staging")
    assert list(staging.iterdir()) == []
    assert not application_paths.resolve_data_path("outside.txt").exists()


def test_duplicate_bundle_never_overwrites_registered_files(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    source = create_model_bundle(tmp_path / "bundle")
    service = ModelImportService(paths=application_paths, session_factory=session_factory)
    imported = service.import_bundle(source)
    owned_model = application_paths.resolve_data_path(imported.manifest_path).with_name(
        "model.onnx"
    )
    original = owned_model.read_bytes()

    with pytest.raises(ModelImportError, match="already registered"):
        service.import_bundle(source)

    assert owned_model.read_bytes() == original
    assert list(application_paths.resolve_data_path("models/.staging").iterdir()) == []


def test_relative_source_path_is_rejected(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(ModelImportError, match="absolute"):
        ModelImportService(
            paths=application_paths,
            session_factory=session_factory,
        ).import_bundle(Path("relative-bundle"))


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "/absolute.txt",
        "C:/fixed.txt",
        r"folder\windows.txt",
    ],
)
def test_unsafe_zip_member_paths_are_rejected(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
    unsafe_name: str,
) -> None:
    archive = tmp_path / "unsafe-member.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(unsafe_name, "unsafe")

    with pytest.raises(ValueError):
        ModelImportService(
            paths=application_paths,
            session_factory=session_factory,
        ).import_bundle(archive)
