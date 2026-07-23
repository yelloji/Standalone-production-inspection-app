"""Programmatic Alembic migration entry points."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parent / "migrations"


def _configuration() -> Config:
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    return configuration


def upgrade_to_head(engine: Engine) -> None:
    """Apply all reviewed migrations to an application-owned database."""

    database = engine.url.database
    if database is None:
        raise ValueError("database engine does not have a file path")
    Path(database).parent.mkdir(parents=True, exist_ok=True)

    configuration = _configuration()
    with engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, "head")


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    return result
