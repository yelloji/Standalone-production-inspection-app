"""Validated application-owned center-reference assets."""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from backend.core.paths import ApplicationPaths
from backend.domain.center_completion import (
    CenterAssetContract,
    CenterCompletionProfile,
    CenterStrategy,
)
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import Point2D


class CenterReferenceLibraryError(RuntimeError):
    """Raised when a center reference is missing or does not match its profile."""


@dataclass(frozen=True, slots=True)
class ApprovedCenterReference:
    side: DiscSide
    profile_id: str
    asset_id: str
    relative_path: str
    expected_sha256: str
    expected_width: int
    expected_height: int
    source_center: Point2D
    source_radius_px: float
    marker_center: Point2D
    source_screen_angles_degrees: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class CenterReferenceStatus:
    side: DiscSide
    profile_id: str
    installed: bool
    relative_path: str
    sha256: str | None
    message: str


APPROVED_CENTER_REFERENCES = {
    DiscSide.UPPER: ApprovedCenterReference(
        side=DiscSide.UPPER,
        profile_id="upper-center-approved-v1",
        asset_id="upper-black-plate-approved-v1",
        relative_path="configuration/center-references/upper.jpg",
        expected_sha256="feaefabab8aaec9cb85c804ae71d1568c3d6383e35d1d102ee7f76ff00566011",
        expected_width=8064,
        expected_height=4536,
        source_center=Point2D(x=3955.9, y=2055.4),
        source_radius_px=1458.1,
        marker_center=Point2D(x=3295.0, y=2514.0),
    ),
    DiscSide.LOWER: ApprovedCenterReference(
        side=DiscSide.LOWER,
        profile_id="lower-center-approved-v1",
        asset_id="lower-complete-assembly-approved-v1",
        relative_path="configuration/center-references/lower.jpg",
        expected_sha256="ef093a23042776d276a205fd2df97cc970c2e0bea7bf0caf0699068a7af3feae",
        expected_width=4536,
        expected_height=8064,
        source_center=Point2D(x=2397.0, y=4017.0),
        source_radius_px=1854.6,
        marker_center=Point2D(x=2290.0, y=3175.0),
        source_screen_angles_degrees=(
            27.0,
            63.0,
            99.0,
            135.0,
            172.0,
            207.0,
            244.0,
            280.0,
            316.0,
            351.0,
        ),
    ),
}


def _approved(side: DiscSide) -> ApprovedCenterReference:
    try:
        return APPROVED_CENTER_REFERENCES[side]
    except KeyError as error:
        raise CenterReferenceLibraryError(
            "center completion requires an upper or lower side"
        ) from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_source(path: Path, approved: ApprovedCenterReference) -> str:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise CenterReferenceLibraryError("select a real local reference image")
    digest = _sha256(path)
    if digest != approved.expected_sha256:
        raise CenterReferenceLibraryError(
            f"selected {approved.side.value} image is not the approved calibrated reference"
        )
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            if image.size != (approved.expected_width, approved.expected_height):
                raise CenterReferenceLibraryError(
                    f"approved {approved.side.value} reference dimensions do not match"
                )
    except (OSError, UnidentifiedImageError) as error:
        raise CenterReferenceLibraryError("selected reference image cannot be decoded") from error
    return digest


class CenterReferenceLibrary:
    """Imports only the two calibrated references into portable application data."""

    def __init__(self, paths: ApplicationPaths) -> None:
        self._paths = paths

    def statuses(self) -> tuple[CenterReferenceStatus, CenterReferenceStatus]:
        return (
            self.status(DiscSide.UPPER),
            self.status(DiscSide.LOWER),
        )

    def status(self, side: DiscSide) -> CenterReferenceStatus:
        approved = _approved(side)
        target = self._paths.resolve_data_path(approved.relative_path)
        if not target.is_file() or target.is_symlink():
            return CenterReferenceStatus(
                side=side,
                profile_id=approved.profile_id,
                installed=False,
                relative_path=approved.relative_path,
                sha256=None,
                message="Approved reference not installed",
            )
        digest = _sha256(target)
        installed = digest == approved.expected_sha256
        return CenterReferenceStatus(
            side=side,
            profile_id=approved.profile_id,
            installed=installed,
            relative_path=approved.relative_path,
            sha256=digest,
            message=(
                "Approved reference ready"
                if installed
                else "Installed reference failed its checksum"
            ),
        )

    def install(self, side: DiscSide, source: Path) -> CenterReferenceStatus:
        approved = _approved(side)
        _validate_source(source, approved)
        target = self._paths.resolve_data_path(approved.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with source.open("rb") as source_stream, staging.open("xb") as target_stream:
                shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)
                target_stream.flush()
                os.fsync(target_stream.fileno())
            if _sha256(staging) != approved.expected_sha256:
                raise CenterReferenceLibraryError("copied reference failed checksum validation")
            os.replace(staging, target)
        finally:
            staging.unlink(missing_ok=True)
        return self.status(side)

    def require_profile(self, side: DiscSide) -> CenterCompletionProfile:
        status = self.status(side)
        if not status.installed:
            raise CenterReferenceLibraryError(
                f"install the approved {side.value} center reference before reconstruction"
            )
        approved = _approved(side)
        is_upper = side is DiscSide.UPPER
        return CenterCompletionProfile(
            profile_id=approved.profile_id,
            side=side,
            strategy=(
                CenterStrategy.UPPER_BLACK_PLATE
                if is_upper
                else CenterStrategy.LOWER_COMPLETE_ASSEMBLY
            ),
            asset=CenterAssetContract(
                asset_id=approved.asset_id,
                relative_path=approved.relative_path,
                sha256=approved.expected_sha256,
                source_center=approved.source_center,
                source_radius_px=approved.source_radius_px,
                marker_center=approved.marker_center,
                black_plate_only=is_upper,
                includes_silver_screens=not is_upper,
                source_screen_angles_degrees=approved.source_screen_angles_degrees,
            ),
            allow_approved_screen_replacement=False,
            commissioned_rotation_offset_degrees=(None if is_upper else -17.009488956364265),
        )
