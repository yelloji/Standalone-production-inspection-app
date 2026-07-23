"""SQLite engine and transaction lifecycle."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths

DEFAULT_DATABASE_RELATIVE_PATH = "database/inspection.sqlite3"
SQLITE_BUSY_TIMEOUT_MILLISECONDS = 30_000

SessionFactory = sessionmaker[Session]


def database_path(
    paths: ApplicationPaths,
    relative_path: str = DEFAULT_DATABASE_RELATIVE_PATH,
) -> Path:
    return paths.resolve_data_path(relative_path)


def create_sqlite_engine(path: Path) -> Engine:
    """Create an engine for an absolute application-owned SQLite file."""

    if not path.is_absolute():
        raise ValueError("SQLite database path must be absolute")

    url = URL.create("sqlite+pysqlite", database=str(path))
    engine = create_engine(
        url,
        connect_args={
            "check_same_thread": False,
            "timeout": SQLITE_BUSY_TIMEOUT_MILLISECONDS / 1000,
        },
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(
        dbapi_connection: sqlite3.Connection,
        connection_record: object,
    ) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def transaction(factory: SessionFactory) -> Generator[Session, None, None]:
    """Commit one service operation or roll it back completely."""

    session = factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
