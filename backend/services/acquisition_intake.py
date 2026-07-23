"""Safe atomic intake of an explicitly ordered 16-image acquisition."""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Literal, cast

from PIL import Image, UnidentifiedImageError
from pydantic import TypeAdapter

from backend.core.paths import ApplicationPaths
from backend.core.serialization import canonical_json_bytes, sha256_hex
from backend.database.models import utc_now
from backend.domain.acquisition import (
    AcquisitionFrameManifest,
    AcquisitionManifest,
    FinalizedAcquisition,
)
from backend.domain.contracts import DiscSide
from backend.domain.value_objects import ContractIdentifier, normalize_relative_path

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
SUPPORTED_FORMATS = {"JPEG", "PNG", "TIFF"}
SUPPORTED_MODES = {"L", "RGB", "RGBA", "I;16", "I;16L", "I;16B"}
_IDENTIFIER_ADAPTER = TypeAdapter(ContractIdentifier)
ImageFormat = Literal["JPEG", "PNG", "TIFF"]
PixelMode = Literal["L", "RGB", "RGBA", "I;16", "I;16L", "I;16B"]


class AcquisitionIntakeError(RuntimeError):
    """Raised when an offline acquisition is unsafe or incomplete."""


class OfflineAcquisitionIntakeService:
    def __init__(self, paths: ApplicationPaths) -> None:
        self._paths = paths

    def intake(
        self,
        *,
        source_directory: Path,
        ordered_relative_paths: tuple[str, ...],
        acquisition_id: str,
        side: DiscSide,
        expected_width: int,
        expected_height: int,
    ) -> FinalizedAcquisition:
        if not source_directory.is_absolute():
            raise AcquisitionIntakeError("source directory must be absolute")
        if not source_directory.is_dir() or source_directory.is_symlink():
            raise AcquisitionIntakeError("source must be a real directory")
        validated_id = _IDENTIFIER_ADAPTER.validate_python(acquisition_id)
        ordered = self._validate_order(ordered_relative_paths)
        self._validate_source_inventory(source_directory, ordered)

        staging_root = self._paths.resolve_data_path("incoming/.staging")
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = staging_root / uuid.uuid4().hex
        staging_frames = staging / "frames"
        staging_frames.mkdir(parents=True)
        final = self._paths.resolve_data_path(f"incoming/{validated_id}")
        if final.exists():
            shutil.rmtree(staging, ignore_errors=True)
            raise AcquisitionIntakeError("acquisition identifier already exists")

        try:
            frames: list[AcquisitionFrameManifest] = []
            seen_hashes: set[str] = set()
            for index, relative in enumerate(ordered, start=1):
                source = self._contained_source(source_directory, relative)
                image_format, pixel_mode = _validate_image(
                    source,
                    expected_width,
                    expected_height,
                )
                checksum = _sha256_file(source)
                if checksum in seen_hashes:
                    raise AcquisitionIntakeError("duplicate image content is not allowed")
                seen_hashes.add(checksum)

                extension = _canonical_extension(image_format)
                target = staging_frames / f"{index:02d}{extension}"
                shutil.copy2(source, target)
                if _sha256_file(target) != checksum:
                    raise AcquisitionIntakeError("copied image checksum verification failed")
                _validate_image(target, expected_width, expected_height)
                frames.append(
                    AcquisitionFrameManifest(
                        position=index,
                        angle_degrees=(index - 1) * 22.5,
                        original_relative_path=relative,
                        owned_relative_path=f"incoming/{validated_id}/frames/{target.name}",
                        image_format=image_format,
                        pixel_mode=pixel_mode,
                        width=expected_width,
                        height=expected_height,
                        size_bytes=target.stat().st_size,
                        sha256=checksum,
                    )
                )

            manifest = AcquisitionManifest(
                acquisition_id=validated_id,
                side=side,
                created_at=utc_now(),
                expected_width=expected_width,
                expected_height=expected_height,
                frames=tuple(frames),
            )
            payload = canonical_json_bytes(manifest)
            (staging / "acquisition_manifest.json").write_bytes(payload)
            manifest_checksum = sha256_hex(payload)
            (staging / "acquisition_manifest.sha256").write_text(
                f"{manifest_checksum}\n",
                encoding="ascii",
            )
            os.replace(staging, final)
            manifest_relative = f"incoming/{validated_id}/acquisition_manifest.json"
            return FinalizedAcquisition(
                manifest=manifest,
                manifest_relative_path=manifest_relative,
                manifest_sha256=manifest_checksum,
            )
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _validate_order(values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != 16:
            raise AcquisitionIntakeError("exactly 16 ordered filenames are required")
        normalized = tuple(normalize_relative_path(value) for value in values)
        if len(set(path.casefold() for path in normalized)) != 16:
            raise AcquisitionIntakeError("ordered filenames must be unique")
        return normalized

    @staticmethod
    def _contained_source(root: Path, relative: str) -> Path:
        candidate = root
        for part in relative.split("/"):
            candidate = candidate / part
            if candidate.is_symlink():
                raise AcquisitionIntakeError(f"source image is linked: {relative}")
        source = candidate.resolve(strict=False)
        try:
            source.relative_to(root.resolve())
        except ValueError as error:
            raise AcquisitionIntakeError("source image escapes selected directory") from error
        if source.is_symlink() or not source.is_file():
            raise AcquisitionIntakeError(f"source image is missing or linked: {relative}")
        if source.suffix.casefold() not in SUPPORTED_SUFFIXES:
            raise AcquisitionIntakeError(f"unsupported image extension: {relative}")
        return source

    @staticmethod
    def _validate_source_inventory(root: Path, ordered: tuple[str, ...]) -> None:
        discovered: set[str] = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                raise AcquisitionIntakeError("links are not allowed in source acquisition")
            if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES:
                discovered.add(
                    normalize_relative_path(path.relative_to(root).as_posix()).casefold()
                )
        expected = {path.casefold() for path in ordered}
        if discovered != expected:
            raise AcquisitionIntakeError(
                "selected folder images do not exactly match the ordered 16-image list"
            )


def _validate_image(
    path: Path,
    width: int,
    height: int,
) -> tuple[ImageFormat, PixelMode]:
    try:
        with Image.open(path) as image:
            image_format = image.format
            pixel_mode = image.mode
            image.verify()
        with Image.open(path) as decoded:
            decoded.load()
            actual_size = decoded.size
            frame_count = getattr(decoded, "n_frames", 1)
    except (OSError, UnidentifiedImageError) as error:
        raise AcquisitionIntakeError(f"image cannot be fully decoded: {path.name}") from error
    if image_format not in SUPPORTED_FORMATS or pixel_mode not in SUPPORTED_MODES:
        raise AcquisitionIntakeError(f"unsupported image format or pixel mode: {path.name}")
    if actual_size != (width, height):
        raise AcquisitionIntakeError(f"unexpected image geometry for {path.name}: {actual_size}")
    if frame_count != 1:
        raise AcquisitionIntakeError(f"multi-frame image is not allowed: {path.name}")
    return cast(ImageFormat, image_format), cast(PixelMode, pixel_mode)


def _canonical_extension(image_format: str) -> str:
    return {"JPEG": ".jpg", "PNG": ".png", "TIFF": ".tif"}[image_format]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
