"""Shared real isolated SQLite fixtures for backend tests."""

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import (
    create_session_factory,
    create_sqlite_engine,
    database_path,
)
from backend.database.migration import upgrade_to_head


@pytest.fixture
def application_paths(tmp_path: Path) -> ApplicationPaths:
    return ApplicationPaths.resolve(resource_root=tmp_path, environment={})


@pytest.fixture
def database_engine(application_paths: ApplicationPaths) -> Generator[Engine, None, None]:
    path = database_path(application_paths)
    engine = create_sqlite_engine(path)
    upgrade_to_head(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(database_engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(database_engine)
