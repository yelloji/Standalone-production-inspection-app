"""SQLite backup, integrity, and recovery tests."""

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.backup import (
    DatabaseBackupService,
    DatabaseIntegrityError,
    verify_sqlite_database,
)
from backend.database.engine import (
    create_session_factory,
    create_sqlite_engine,
    database_path,
    transaction,
)
from backend.database.migration import current_revision
from backend.database.repositories import MetadataRepository
from tests.backend.database.factories import model_bundle


def test_backup_and_restore_recover_committed_state(
    application_paths: ApplicationPaths,
    database_engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    with transaction(session_factory) as session:
        MetadataRepository(session).add_model_bundle(model_bundle("before-backup"))

    service = DatabaseBackupService(application_paths)
    backup = service.backup("database/backups/known-good.sqlite3")
    verify_sqlite_database(backup)

    with transaction(session_factory) as session:
        MetadataRepository(session).add_model_bundle(model_bundle("after-backup"))

    database_engine.dispose()
    service.restore("database/backups/known-good.sqlite3")

    restored_engine = create_sqlite_engine(database_path(application_paths))
    restored_factory = create_session_factory(restored_engine)
    try:
        with transaction(restored_factory) as session:
            repository = MetadataRepository(session)
            assert repository.get_model_bundle("before-backup") is not None
            assert repository.get_model_bundle("after-backup") is None
        assert current_revision(restored_engine) == "0003_run_orchestration"
    finally:
        restored_engine.dispose()


def test_corrupt_backup_is_rejected_without_replacing_database(
    application_paths: ApplicationPaths,
    database_engine: Engine,
) -> None:
    database_engine.dispose()
    target = database_path(application_paths)
    original_bytes = target.read_bytes()
    corrupt = application_paths.resolve_data_path("database/backups/corrupt.sqlite3")
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"not a sqlite database")

    with pytest.raises(DatabaseIntegrityError):
        DatabaseBackupService(application_paths).restore("database/backups/corrupt.sqlite3")

    assert target.read_bytes() == original_bytes
    verify_sqlite_database(target)


def test_backup_paths_cannot_escape_data_root(
    application_paths: ApplicationPaths,
) -> None:
    with pytest.raises(ValueError):
        DatabaseBackupService(application_paths).backup("../outside.sqlite3")


def test_missing_database_cannot_create_empty_backup(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, environment={})

    with pytest.raises(FileNotFoundError):
        DatabaseBackupService(paths).backup("database/backups/missing.sqlite3")
