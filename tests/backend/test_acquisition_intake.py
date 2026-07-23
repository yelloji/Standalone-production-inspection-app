"""Real-image offline acquisition intake and rejection tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from backend.core.paths import ApplicationPaths
from backend.core.serialization import sha256_hex
from backend.domain.acquisition import AcquisitionManifest, FinalizedAcquisition
from backend.domain.contracts import DiscSide
from backend.services.acquisition_intake import (
    AcquisitionIntakeError,
    OfflineAcquisitionIntakeService,
)
from tests.backend.image_acquisition_factory import create_acquisition_images

WIDTH = 32
HEIGHT = 24


def intake(
    paths: ApplicationPaths,
    source: Path,
    ordered_names: tuple[str, ...],
    *,
    acquisition_id: str = "acquisition-001",
) -> tuple[OfflineAcquisitionIntakeService, FinalizedAcquisition]:
    service = OfflineAcquisitionIntakeService(paths)
    result = service.intake(
        source_directory=source,
        ordered_relative_paths=ordered_names,
        acquisition_id=acquisition_id,
        side=DiscSide.UPPER,
        expected_width=WIDTH,
        expected_height=HEIGHT,
    )
    return service, result


def test_explicit_order_is_preserved_and_source_becomes_unnecessary(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    source = tmp_path / "external"
    names = create_acquisition_images(source)
    explicit_order = tuple(reversed(names))

    _, finalized = intake(application_paths, source, explicit_order)
    source.rename(tmp_path / "external-removed")

    assert finalized.manifest.frame_count == 16
    assert [frame.original_relative_path for frame in finalized.manifest.frames] == list(
        explicit_order
    )
    assert [frame.angle_degrees for frame in finalized.manifest.frames] == [
        index * 22.5 for index in range(16)
    ]
    manifest_path = application_paths.resolve_data_path(finalized.manifest_relative_path)
    payload = manifest_path.read_bytes()
    reopened = AcquisitionManifest.model_validate(json.loads(payload))
    assert reopened == finalized.manifest
    assert sha256_hex(payload) == finalized.manifest_sha256
    checksum_path = manifest_path.with_name("acquisition_manifest.sha256")
    assert checksum_path.read_text(encoding="ascii").strip() == finalized.manifest_sha256
    assert all(
        application_paths.resolve_data_path(frame.owned_relative_path).is_file()
        for frame in reopened.frames
    )


def test_jpeg_png_and_tiff_are_fully_decoded(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    formats = ("JPEG", "PNG", "TIFF", "PNG") * 4
    source = tmp_path / "mixed"
    names = create_acquisition_images(source, formats=formats)

    _, finalized = intake(application_paths, source, names)

    assert tuple(frame.image_format for frame in finalized.manifest.frames) == formats
    assert all(frame.pixel_mode == "RGB" for frame in finalized.manifest.frames)


@pytest.mark.parametrize("count", [0, 15])
def test_incomplete_order_is_rejected_before_copy(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    count: int,
) -> None:
    source = tmp_path / "incomplete"
    names = create_acquisition_images(source)

    with pytest.raises(AcquisitionIntakeError, match="exactly 16"):
        intake(application_paths, source, names[:count])

    assert not application_paths.resolve_data_path("incoming/.staging").exists()


def test_duplicate_content_is_rejected_and_staging_cleaned(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    source = tmp_path / "duplicate"
    names = create_acquisition_images(source)
    (source / names[1]).write_bytes((source / names[0]).read_bytes())

    with pytest.raises(AcquisitionIntakeError, match="duplicate image content"):
        intake(application_paths, source, names)

    staging = application_paths.resolve_data_path("incoming/.staging")
    assert list(staging.iterdir()) == []
    assert not application_paths.resolve_data_path("incoming/acquisition-001").exists()


def test_wrong_geometry_is_rejected(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    source = tmp_path / "geometry"
    names = create_acquisition_images(source)
    Image.new("RGB", (WIDTH + 1, HEIGHT), "red").save(source / names[7])

    with pytest.raises(AcquisitionIntakeError, match="unexpected image geometry"):
        intake(application_paths, source, names)


def test_corrupt_image_is_rejected(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    source = tmp_path / "corrupt"
    names = create_acquisition_images(source)
    (source / names[9]).write_bytes(b"not an image")

    with pytest.raises(AcquisitionIntakeError, match="fully decoded"):
        intake(application_paths, source, names)


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "../outside.png",
        "C:/fixed.png",
        r"folder\windows.png",
    ],
)
def test_unsafe_ordered_paths_are_rejected(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    unsafe_name: str,
) -> None:
    source = tmp_path / "unsafe"
    names = list(create_acquisition_images(source))
    names[0] = unsafe_name

    with pytest.raises(ValueError):
        intake(application_paths, source, tuple(names))


def test_duplicate_acquisition_id_never_overwrites_owned_data(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    source = tmp_path / "duplicate-id"
    names = create_acquisition_images(source)
    _, first = intake(application_paths, source, names)
    manifest_path = application_paths.resolve_data_path(first.manifest_relative_path)
    original = manifest_path.read_bytes()

    with pytest.raises(AcquisitionIntakeError, match="already exists"):
        intake(application_paths, source, names)

    assert manifest_path.read_bytes() == original


def test_unselected_seventeenth_image_is_rejected(
    tmp_path: Path,
    application_paths: ApplicationPaths,
) -> None:
    source = tmp_path / "extra"
    names = create_acquisition_images(source)
    Image.new("RGB", (WIDTH, HEIGHT), "white").save(source / "extra.png")

    with pytest.raises(AcquisitionIntakeError, match="exactly match"):
        intake(application_paths, source, names)


def test_relative_source_directory_is_rejected(
    application_paths: ApplicationPaths,
) -> None:
    with pytest.raises(AcquisitionIntakeError, match="absolute"):
        OfflineAcquisitionIntakeService(application_paths).intake(
            source_directory=Path("relative"),
            ordered_relative_paths=tuple(f"{index}.png" for index in range(16)),
            acquisition_id="relative-source",
            side=DiscSide.UPPER,
            expected_width=WIDTH,
            expected_height=HEIGHT,
        )
