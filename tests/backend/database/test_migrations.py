"""Migration, schema, index, and SQLite connection-policy tests."""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from backend.core.paths import ApplicationPaths
from backend.database.engine import create_sqlite_engine, database_path
from backend.database.migration import current_revision, upgrade_to_head
from backend.database.models import Base

EXPECTED_TABLES = {
    "alembic_version",
    "artifacts",
    "inspection_runs",
    "model_bundles",
    "pipeline_snapshots",
    "source_frames",
}


def test_migration_creates_expected_schema_and_indexes(database_engine: Engine) -> None:
    inspector = inspect(database_engine)

    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    assert current_revision(database_engine) == "0002_single_active_model"
    assert {index["name"] for index in inspector.get_indexes("inspection_runs")} >= {
        "ix_inspection_runs_acquisition_id",
        "ix_inspection_runs_status_created_at",
    }
    assert {index["name"] for index in inspector.get_indexes("source_frames")} >= {
        "ix_source_frames_run_frame_index"
    }


def test_upgrade_is_idempotent_on_real_sqlite_file(
    application_paths: ApplicationPaths,
) -> None:
    path = database_path(application_paths)
    engine = create_sqlite_engine(path)
    try:
        upgrade_to_head(engine)
        upgrade_to_head(engine)
        assert current_revision(engine) == "0002_single_active_model"
    finally:
        engine.dispose()

    assert path.is_file()


def test_migration_schema_matches_sqlalchemy_metadata(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_sqlite_connection_policy_is_enabled(database_engine: Engine) -> None:
    with database_engine.connect() as connection:
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        synchronous = connection.execute(text("PRAGMA synchronous")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert foreign_keys == 1
    assert journal_mode == "wal"
    assert synchronous == 1
    assert busy_timeout == 30_000


def test_database_path_is_portable_and_data_root_relative(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(
        resource_root=tmp_path,
        data_root="portable-data",
        environment={},
    )

    assert (
        database_path(paths) == (tmp_path / "portable-data/database/inspection.sqlite3").resolve()
    )
