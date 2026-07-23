"""Atomic configuration persistence tests."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.configuration import AtomicConfigurationStore
from backend.core.paths import ApplicationPaths
from backend.core.serialization import canonical_checksum, canonical_json_bytes
from backend.domain.contracts import ApplicationConfiguration

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)


def make_configuration(revision: int = 1) -> ApplicationConfiguration:
    return ApplicationConfiguration(
        configuration_revision=revision,
        active_pipeline_id="brake-disc-upper",
        updated_at=NOW,
    )


def make_store(
    tmp_path: Path,
) -> tuple[
    ApplicationPaths,
    AtomicConfigurationStore[ApplicationConfiguration],
]:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, environment={})
    store = AtomicConfigurationStore(
        paths=paths,
        model_type=ApplicationConfiguration,
    )
    return paths, store


def test_configuration_save_load_and_atomic_replace(tmp_path: Path) -> None:
    paths, store = make_store(tmp_path)
    relative_path = "configuration/application.json"
    first = make_configuration(1)

    first_checksum = store.save(relative_path, first)
    second = make_configuration(2)
    second_checksum = store.save(relative_path, second)

    target = paths.resolve_data_path(relative_path)
    assert store.load(relative_path) == second
    assert target.read_bytes() == canonical_json_bytes(second)
    assert first_checksum == canonical_checksum(first)
    assert second_checksum == canonical_checksum(second)
    assert first_checksum != second_checksum
    assert list(target.parent.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../application.json",
        "C:/configuration/application.json",
        r"configuration\application.json",
    ],
)
def test_configuration_store_rejects_unsafe_paths(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    _, store = make_store(tmp_path)

    with pytest.raises(ValueError):
        store.save(unsafe_path, make_configuration())


def test_configuration_load_rejects_unsupported_schema(tmp_path: Path) -> None:
    paths, store = make_store(tmp_path)
    target = paths.resolve_data_path("configuration/application.json")
    target.parent.mkdir(parents=True)
    target.write_text(
        '{"active_pipeline_id":null,"configuration_revision":1,'
        '"schema_version":2,"updated_at":"2026-07-23T10:00:00Z"}',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        store.load("configuration/application.json")
