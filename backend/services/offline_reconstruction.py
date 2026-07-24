"""Offline 16-frame reconstruction workflow for commissioning and review."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image

from backend.core.paths import ApplicationPaths
from backend.domain.contracts import DiscSide
from backend.reconstruction.image_evidence import (
    ImageEvidenceProfile,
    extract_cycle_image_evidence,
)
from backend.reconstruction.preview import ReconstructionPreview, render_reconstruction_preview
from backend.reconstruction.preview_center import (
    apply_center_completion_to_preview,
    estimate_cycle_calibration,
)
from backend.reconstruction.projective import (
    LOWER_PROJECTIVE_PROFILE,
    UPPER_PROJECTIVE_PROFILE,
    solve_projective_reconstruction,
)
from backend.reconstruction.rendering import RenderFrame
from backend.services.acquisition_intake import (
    SUPPORTED_SUFFIXES,
    OfflineAcquisitionIntakeService,
)
from backend.services.center_reference_library import CenterReferenceLibrary

ProgressCallback = Callable[[str, int, int], None]


class OfflineReconstructionError(RuntimeError):
    """Raised when an offline reconstruction cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class OfflineReconstructionResult:
    acquisition_id: str
    side: DiscSide
    source_names: tuple[str, ...]
    production_approved: bool
    validation_median_px: float | None
    validation_p95_px: float | None
    validation_maximum_px: float | None
    passed_join_count: int
    total_join_count: int
    preview: ReconstructionPreview
    report_relative_path: str
    failure_reasons: tuple[str, ...]
    center_completion_applied: bool = False
    center_profile_id: str | None = None
    center_rotation_degrees: float | None = None
    center_fill_pixels: int | None = None


def _ordered_images(source: Path) -> tuple[Path, ...]:
    if not source.is_absolute() or not source.is_dir() or source.is_symlink():
        raise OfflineReconstructionError("select a real local acquisition folder")
    candidates = [
        path
        for path in source.iterdir()
        if path.is_file() and not path.is_symlink() and path.suffix.casefold() in SUPPORTED_SUFFIXES
    ]
    if len(candidates) != 16:
        raise OfflineReconstructionError("the selected folder must contain exactly 16 images")
    numbered: dict[int, Path] = {}
    for path in candidates:
        match = re.match(r"(\d+)", path.name)
        if match is None:
            raise OfflineReconstructionError("each image filename must start with position 1 to 16")
        position = int(match.group(1))
        if position not in range(1, 17) or position in numbered:
            raise OfflineReconstructionError("image filename positions must be unique from 1 to 16")
        numbered[position] = path
    if set(numbered) != set(range(1, 17)):
        raise OfflineReconstructionError("image filename positions must cover 1 through 16")
    return tuple(numbered[position] for position in range(1, 17))


class OfflineReconstructionService:
    def __init__(
        self,
        paths: ApplicationPaths,
        center_references: CenterReferenceLibrary | None = None,
    ) -> None:
        self._paths = paths
        self._intake = OfflineAcquisitionIntakeService(paths)
        self._center_references = center_references or CenterReferenceLibrary(paths)

    @property
    def paths(self) -> ApplicationPaths:
        return self._paths

    def reconstruct(
        self,
        *,
        source_directory: Path,
        side: DiscSide,
        preview_size: int,
        progress: ProgressCallback,
    ) -> OfflineReconstructionResult:
        if side not in {DiscSide.UPPER, DiscSide.LOWER}:
            raise OfflineReconstructionError("reconstruction side must be upper or lower")
        if preview_size not in {3000, 4000, 5000}:
            raise OfflineReconstructionError("preview size must be 3000, 4000, or 5000 pixels")
        center_profile = self._center_references.require_profile(side)
        ordered = _ordered_images(source_directory)
        with Image.open(ordered[0]) as first:
            width, height = first.size
        acquisition_id = f"offline-{uuid.uuid4().hex[:16]}"
        progress("verifying", 0, 16)
        finalized = self._intake.intake(
            source_directory=source_directory,
            ordered_relative_paths=tuple(path.name for path in ordered),
            acquisition_id=acquisition_id,
            side=side,
            expected_width=width,
            expected_height=height,
        )
        progress("registering", 0, 16)
        owned = tuple(
            self._paths.resolve_data_path(frame.owned_relative_path)
            for frame in finalized.manifest.frames
        )
        evidence = extract_cycle_image_evidence(
            owned,
            profile=ImageEvidenceProfile(
                feature_channel="blue",
                flow_channels=("blue", "gray", "saturation"),
            ),
            progress=lambda current, total: progress("registering", current, total),
        )
        calibration = estimate_cycle_calibration(
            evidence,
            acquisition_id=acquisition_id,
            side=side,
        )
        progress("validating", 0, 1)
        projective_profile = (
            UPPER_PROJECTIVE_PROFILE if side is DiscSide.UPPER else LOWER_PROJECTIVE_PROFILE
        )
        solved = solve_projective_reconstruction(
            evidence.pairs,
            image_width=width,
            image_height=height,
            profile=projective_profile,
        )
        candidate = solved.diagnostic_frame_to_reference_matrices
        if candidate is None:
            raise OfflineReconstructionError("registration did not produce a reviewable cycle")
        progress("rendering", 0, 1)
        preview = render_reconstruction_preview(
            self._paths,
            frames=tuple(
                RenderFrame(
                    position=frame.position,
                    source_relative_path=frame.owned_relative_path,
                    source_sha256=frame.sha256,
                    source_to_reference_matrix=matrix,
                )
                for frame, matrix in zip(finalized.manifest.frames, candidate, strict=True)
            ),
            source_width=width,
            source_height=height,
            output_relative_path=f"completed/{acquisition_id}/reconstructed-preview.png",
            maximum_dimension=preview_size,
            square_size=preview_size,
        )
        if preview.source_to_preview_matrix is None:
            raise OfflineReconstructionError("preview mapping metadata is missing")
        progress("completing_center", 0, 1)
        center = apply_center_completion_to_preview(
            self._paths,
            preview_relative_path=preview.relative_path,
            source_to_preview_matrix=preview.source_to_preview_matrix,
            calibration=calibration.calibration,
            profile=center_profile,
        )
        preview = replace(
            preview,
            sha256=center.sha256,
            size_bytes=center.size_bytes,
        )
        passed_join_count = sum(item.passed for item in solved.pair_validations)
        report_relative = f"completed/{acquisition_id}/reconstruction-report.json"
        report_path = self._paths.resolve_data_path(report_relative)
        report_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "acquisition_id": acquisition_id,
                    "side": side.value,
                    "source_order": [path.name for path in ordered],
                    "production_approved": solved.passed,
                    "validation_median_px": solved.validation_median_px,
                    "validation_p95_px": solved.validation_p95_px,
                    "validation_maximum_px": solved.validation_maximum_px,
                    "passed_join_count": passed_join_count,
                    "total_join_count": len(solved.pair_validations),
                    "failure_reasons": solved.failure_reasons,
                    "preview_relative_path": preview.relative_path,
                    "center_completion": {
                        "applied": True,
                        "profile_id": center.profile_id,
                        "reference_sha256": center_profile.asset.sha256,
                        "rotation_degrees": center.rotation_degrees,
                        "scale": center.scale,
                        "filled_pixels": center.filled_pixels,
                        "acquired_pixels_changed": center.acquired_pixels_changed,
                        "target_center_px": [
                            center.target_center_x,
                            center.target_center_y,
                        ],
                        "target_opening_radius_px": center.target_opening_radius_px,
                        "detected_flash_angles_degrees": (center.detected_flash_angles_degrees),
                        "median_angular_residual_degrees": (center.median_angular_residual_degrees),
                        "maximum_angular_residual_degrees": (
                            center.maximum_angular_residual_degrees
                        ),
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        progress("completed", 1, 1)
        return OfflineReconstructionResult(
            acquisition_id=acquisition_id,
            side=side,
            source_names=tuple(path.name for path in ordered),
            production_approved=solved.passed,
            validation_median_px=solved.validation_median_px,
            validation_p95_px=solved.validation_p95_px,
            validation_maximum_px=solved.validation_maximum_px,
            passed_join_count=passed_join_count,
            total_join_count=len(solved.pair_validations),
            preview=preview,
            report_relative_path=report_relative,
            failure_reasons=solved.failure_reasons,
            center_completion_applied=True,
            center_profile_id=center.profile_id,
            center_rotation_degrees=center.rotation_degrees,
            center_fill_pixels=center.filled_pixels,
        )
