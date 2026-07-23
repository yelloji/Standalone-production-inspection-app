"""Integrity-checked SQLite backup and recovery."""

from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

from backend.core.paths import ApplicationPaths
from backend.database.engine import DEFAULT_DATABASE_RELATIVE_PATH


class DatabaseIntegrityError(RuntimeError):
    """Raised when SQLite integrity validation does not pass."""


def verify_sqlite_database(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)

    try:
        with sqlite3.connect(path) as connection:
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
            foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.DatabaseError as error:
        raise DatabaseIntegrityError("database file could not be validated") from error

    if integrity_rows != [("ok",)] or foreign_key_rows:
        raise DatabaseIntegrityError("database integrity validation failed")


class DatabaseBackupService:
    """Backup and restore only files contained beneath the approved data root."""

    def __init__(self, paths: ApplicationPaths) -> None:
        self._paths = paths

    def backup(
        self,
        destination_relative_path: str,
        source_relative_path: str = DEFAULT_DATABASE_RELATIVE_PATH,
    ) -> Path:
        source = self._paths.resolve_data_path(source_relative_path)
        destination = self._paths.resolve_data_path(destination_relative_path)
        if source == destination:
            raise ValueError("backup destination must differ from the database")
        if not source.is_file():
            raise FileNotFoundError(source)

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_database_path(destination)
        try:
            _sqlite_backup(source, temporary)
            verify_sqlite_database(temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def restore(
        self,
        backup_relative_path: str,
        target_relative_path: str = DEFAULT_DATABASE_RELATIVE_PATH,
    ) -> Path:
        backup = self._paths.resolve_data_path(backup_relative_path)
        target = self._paths.resolve_data_path(target_relative_path)
        if backup == target:
            raise ValueError("restore source must differ from the database")

        verify_sqlite_database(backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_database_path(target)
        try:
            _sqlite_backup(backup, temporary)
            verify_sqlite_database(temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target


def _sqlite_backup(source: Path, destination: Path) -> None:
    with (
        sqlite3.connect(source) as source_connection,
        sqlite3.connect(destination) as destination_connection,
    ):
        source_connection.backup(destination_connection)


def _temporary_database_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
