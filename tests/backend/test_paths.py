"""Portable path resolution and containment tests."""

from pathlib import Path

import pytest

from backend.core.paths import (
    DATA_DIRECTORY_NAMES,
    ApplicationPaths,
    PathContainmentError,
)
from backend.domain.value_objects import normalize_relative_path


def test_default_data_root_is_relative_to_resource_root(tmp_path: Path) -> None:
    resource_root = tmp_path / "moved-application"

    paths = ApplicationPaths.resolve(resource_root=resource_root, environment={})

    assert paths.resource_root == resource_root.resolve()
    assert paths.data_root == (resource_root / "data").resolve()


def test_explicit_data_root_has_precedence_over_environment(tmp_path: Path) -> None:
    resource_root = tmp_path / "application"

    paths = ApplicationPaths.resolve(
        resource_root=resource_root,
        data_root="explicit-data",
        environment={"PRODUCTION_DATA_ROOT": "environment-data"},
    )

    assert paths.data_root == (resource_root / "explicit-data").resolve()


def test_relative_environment_data_root_is_application_relative(tmp_path: Path) -> None:
    resource_root = tmp_path / "application"

    paths = ApplicationPaths.resolve(
        resource_root=resource_root,
        environment={"PRODUCTION_DATA_ROOT": "plant-data"},
    )

    assert paths.data_root == (resource_root / "plant-data").resolve()


def test_layout_creation_is_explicit_and_complete(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, environment={})
    assert not paths.data_root.exists()

    created = paths.ensure_data_layout()

    assert tuple(path.name for path in created) == DATA_DIRECTORY_NAMES
    assert all(path.is_dir() for path in created)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "",
        "../outside.json",
        "configuration/../../outside.json",
        "C:/fixed/configuration.json",
        "C:fixed/configuration.json",
        "/absolute/configuration.json",
        r"configuration\windows.json",
        "configuration//application.json",
        "configuration/./application.json",
        "configuration/CON.json",
        "configuration/name?.json",
        "configuration/trailing.",
    ],
)
def test_unsafe_relative_paths_are_rejected(unsafe_path: str) -> None:
    with pytest.raises(ValueError):
        normalize_relative_path(unsafe_path)


def test_data_path_round_trip_preserves_portable_form(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, environment={})

    absolute = paths.resolve_data_path("configuration/application.json")

    assert absolute == (tmp_path / "data/configuration/application.json").resolve()
    assert paths.to_data_relative_path(absolute) == "configuration/application.json"


def test_absolute_path_outside_data_root_cannot_be_stored(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path / "application", environment={})

    with pytest.raises(PathContainmentError):
        paths.to_data_relative_path(tmp_path / "outside.json")


def test_unknown_data_directory_is_rejected(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, environment={})

    with pytest.raises(KeyError):
        paths.data_directory("unapproved")


def test_relative_resource_root_is_rejected() -> None:
    with pytest.raises(ValueError, match="resource root"):
        ApplicationPaths.resolve(resource_root=Path("relative-application"), environment={})


def test_process_environment_is_used_when_mapping_is_omitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCTION_DATA_ROOT", "configured-data")

    paths = ApplicationPaths.resolve(resource_root=tmp_path)

    assert paths.data_root == (tmp_path / "configured-data").resolve()
