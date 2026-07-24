"""Automatic approved center completion for bounded reconstruction previews."""

from __future__ import annotations

import hashlib
import math
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from backend.core.paths import ApplicationPaths
from backend.domain.center_completion import CenterCompletionProfile
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import CalibrationContract, Matrix3x3, Point2D, RoiRectangle
from backend.reconstruction.calibration import (
    CalibrationEstimate,
    PairMatchAttempt,
    PairObservation,
    build_calibration,
)
from backend.reconstruction.center_completion import (
    CenterCompletionPlan,
    detect_flash_angles,
    plan_lower_center_completion,
    plan_upper_center_completion,
)
from backend.reconstruction.image_evidence import CycleImageEvidence


class PreviewCenterCompletionFailure(RuntimeError):
    """Raised when automatic center completion cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class PreviewCenterCompletionResult:
    profile_id: str
    rotation_degrees: float
    scale: float
    filled_pixels: int
    acquired_pixels_changed: int
    target_center_x: float
    target_center_y: float
    target_opening_radius_px: float
    detected_flash_angles_degrees: tuple[float, ...]
    median_angular_residual_degrees: float | None
    maximum_angular_residual_degrees: float | None
    sha256: str
    size_bytes: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def estimate_cycle_calibration(
    evidence: CycleImageEvidence,
    *,
    acquisition_id: str,
    side: DiscSide,
) -> CalibrationEstimate:
    """Recover the fixed rotation center and image-1 reference ray from all joins."""

    attempts: list[PairMatchAttempt] = []
    for pair in evidence.pairs:
        affine, inliers = cv2.estimateAffinePartial2D(
            pair.fit_source_points,
            pair.fit_target_points,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.0,
            maxIters=5000,
            confidence=0.999,
            refineIters=10,
        )
        if affine is None or inliers is None:
            attempts.append(
                PairMatchAttempt(
                    pair.source_frame,
                    pair.target_frame,
                    None,
                    "partial-affine fit failed",
                )
            )
            continue
        affine = np.asarray(affine, dtype=np.float64)
        linear = affine[:, :2]
        angle = math.degrees(math.atan2(linear[1, 0], linear[0, 0]))
        determinant = float(linear[0, 0]) * float(linear[1, 1]) - float(linear[0, 1]) * float(
            linear[1, 0]
        )
        scale = math.sqrt(abs(determinant))
        homogeneous = np.column_stack(
            (
                pair.validation_source_points,
                np.ones(len(pair.validation_source_points), dtype=np.float64),
            )
        )
        predicted = homogeneous @ affine.T
        residuals = np.linalg.norm(predicted - pair.validation_target_points, axis=1)
        attempts.append(
            PairMatchAttempt(
                pair.source_frame,
                pair.target_frame,
                PairObservation(
                    source_frame=pair.source_frame,
                    target_frame=pair.target_frame,
                    angle_degrees=float(angle),
                    scale=scale,
                    affine_matrix=(
                        (
                            float(affine[0, 0]),
                            float(affine[0, 1]),
                            float(affine[0, 2]),
                        ),
                        (
                            float(affine[1, 0]),
                            float(affine[1, 1]),
                            float(affine[1, 2]),
                        ),
                    ),
                    inlier_count=int(np.count_nonzero(inliers)),
                    median_residual_px=float(np.median(residuals)),
                ),
            )
        )
    roi_y = int(round(evidence.image_height * 0.18))
    return build_calibration(
        acquisition_id=acquisition_id,
        side=side,
        attempts=attempts,
        input_width=evidence.image_width,
        input_height=evidence.image_height,
        usable_source_roi=RoiRectangle(
            x=0,
            y=roi_y,
            width=evidence.image_width,
            height=evidence.image_height - roi_y,
        ),
    )


def _map_point(matrix: Matrix3x3, point: Point2D) -> tuple[float, float]:
    values = np.asarray(matrix, dtype=np.float64) @ np.asarray(
        (point.x, point.y, 1.0),
        dtype=np.float64,
    )
    if abs(values[2]) < 1e-12:
        raise PreviewCenterCompletionFailure("disc center maps to an invalid preview point")
    return float(values[0] / values[2]), float(values[1] / values[2])


def _central_opening(
    acquired: npt.NDArray[np.bool_],
    target_center: tuple[float, float],
) -> tuple[npt.NDArray[np.bool_], float]:
    height, width = acquired.shape
    center_x = int(round(target_center[0]))
    center_y = int(round(target_center[1]))
    if center_x not in range(width) or center_y not in range(height):
        raise PreviewCenterCompletionFailure("estimated disc center is outside the preview")
    uncovered = (~acquired).astype(np.uint8)
    _, labels = cv2.connectedComponents(uncovered, connectivity=8)
    label = int(labels[center_y, center_x])
    if label == 0:
        raise PreviewCenterCompletionFailure("estimated disc center is already acquired")
    opening = labels == label
    if (
        np.any(opening[0, :])
        or np.any(opening[-1, :])
        or np.any(opening[:, 0])
        or np.any(opening[:, -1])
    ):
        raise PreviewCenterCompletionFailure("central opening is connected to the exterior")
    rows, columns = np.where(opening)
    radius = float(np.hypot(columns - target_center[0], rows - target_center[1]).max(initial=0.0))
    minimum = min(width, height) * 0.12
    maximum = min(width, height) * 0.45
    if not minimum <= radius <= maximum:
        raise PreviewCenterCompletionFailure("central opening radius is outside safe bounds")
    return opening, radius


def _flash_scores(
    image_bgr: npt.NDArray[np.uint8],
    acquired: npt.NDArray[np.bool_],
    center: tuple[float, float],
    opening_radius: float,
) -> npt.NDArray[np.float64]:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    height, width = acquired.shape
    score = np.zeros(360, dtype=np.float64)
    count = np.zeros(360, dtype=np.float64)
    for row_start in range(0, height, 250):
        row_end = min(row_start + 250, height)
        local_y, local_x = np.indices((row_end - row_start, width))
        local_y += row_start
        delta_x = local_x - center[0]
        delta_y = local_y - center[1]
        radius = np.hypot(delta_x, delta_y)
        angle = ((np.degrees(np.arctan2(delta_y, delta_x)) + 360.0) % 360.0).astype(np.int32)
        selected = (
            acquired[row_start:row_end]
            & (radius > opening_radius * 0.866)
            & (radius < opening_radius * 1.028)
        )
        value = hsv[row_start:row_end, :, 2].astype(np.float64)
        saturation = hsv[row_start:row_end, :, 1].astype(np.float64)
        values = value * (1.0 - saturation / 510.0)
        np.add.at(score, angle[selected], values[selected])
        np.add.at(count, angle[selected], 1.0)
    return np.divide(score, count, out=np.zeros_like(score), where=count > 0)


def _plan(
    profile: CenterCompletionProfile,
    *,
    calibration: CalibrationContract,
    image_bgr: npt.NDArray[np.uint8],
    acquired: npt.NDArray[np.bool_],
    target_center: tuple[float, float],
    opening_radius: float,
) -> tuple[CenterCompletionPlan, tuple[float, ...]]:
    image_one_start = calibration.reference_ray_degrees - 11.25
    center = Point2D(x=target_center[0], y=target_center[1])
    if profile.side is DiscSide.UPPER:
        return (
            plan_upper_center_completion(
                profile,
                image_one_start_ray_degrees=image_one_start,
                target_center=center,
                target_opening_radius_px=opening_radius,
            ),
            (),
        )
    detection = detect_flash_angles(
        _flash_scores(image_bgr, acquired, target_center, opening_radius)
    )
    return (
        plan_lower_center_completion(
            profile,
            image_one_start_ray_degrees=image_one_start,
            detected_flash_angles_degrees=detection.angles_degrees,
            target_center=center,
            target_opening_radius_px=opening_radius,
        ),
        detection.angles_degrees,
    )


def apply_center_completion_to_preview(
    paths: ApplicationPaths,
    *,
    preview_relative_path: str,
    source_to_preview_matrix: Matrix3x3,
    calibration: CalibrationContract,
    profile: CenterCompletionProfile,
) -> PreviewCenterCompletionResult:
    """Fill only the central no-data component using the approved side reference."""

    preview_path = paths.resolve_data_path(preview_relative_path)
    reference_path = paths.resolve_data_path(profile.asset.relative_path)
    image_bgr_value = cv2.imread(str(preview_path), cv2.IMREAD_COLOR)
    reference_bgr_value = cv2.imread(str(reference_path), cv2.IMREAD_COLOR)
    image_bgr = cast(npt.NDArray[np.uint8] | None, image_bgr_value)
    reference_bgr = cast(npt.NDArray[np.uint8] | None, reference_bgr_value)
    if image_bgr is None or reference_bgr is None:
        raise PreviewCenterCompletionFailure("preview or center reference cannot be decoded")
    acquired = np.any(image_bgr != 0, axis=2)
    before = image_bgr.copy()
    target_center = _map_point(source_to_preview_matrix, calibration.source_disc_center)
    opening, opening_radius = _central_opening(acquired, target_center)
    plan, flash_angles = _plan(
        profile,
        calibration=calibration,
        image_bgr=image_bgr,
        acquired=acquired,
        target_center=target_center,
        opening_radius=opening_radius,
    )
    affine = np.asarray(plan.source_to_output_affine, dtype=np.float64)
    width, height = image_bgr.shape[1], image_bgr.shape[0]
    warped = cv2.warpAffine(
        reference_bgr,
        affine,
        (width, height),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    source_mask = np.zeros(reference_bgr.shape[:2], dtype=np.uint8)
    cv2.circle(
        source_mask,
        (
            int(round(profile.asset.source_center.x)),
            int(round(profile.asset.source_center.y)),
        ),
        int(round(profile.asset.source_radius_px)),
        255,
        -1,
        cv2.LINE_AA,
    )
    warped_mask = (
        cv2.warpAffine(
            source_mask,
            affine,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        >= 128
    )
    fill = opening & warped_mask & ~acquired
    if not np.any(fill):
        raise PreviewCenterCompletionFailure("approved center reference filled no pixels")
    image_bgr[fill] = warped[fill]
    acquired_changed = int(
        np.count_nonzero(np.any(image_bgr[acquired] != before[acquired], axis=1))
    )
    if acquired_changed:
        raise PreviewCenterCompletionFailure("center completion changed acquired pixels")
    staging = preview_path.with_name(f".{preview_path.stem}.{uuid.uuid4().hex}.tmp.png")
    try:
        if not cv2.imwrite(str(staging), image_bgr, (cv2.IMWRITE_PNG_COMPRESSION, 3)):
            raise PreviewCenterCompletionFailure("completed preview could not be encoded")
        os.replace(staging, preview_path)
    finally:
        staging.unlink(missing_ok=True)
    return PreviewCenterCompletionResult(
        profile_id=profile.profile_id,
        rotation_degrees=plan.rotation_degrees,
        scale=plan.scale,
        filled_pixels=int(np.count_nonzero(fill)),
        acquired_pixels_changed=acquired_changed,
        target_center_x=target_center[0],
        target_center_y=target_center[1],
        target_opening_radius_px=opening_radius,
        detected_flash_angles_degrees=flash_angles,
        median_angular_residual_degrees=plan.median_absolute_angular_residual_degrees,
        maximum_angular_residual_degrees=plan.maximum_absolute_angular_residual_degrees,
        sha256=_sha256(preview_path),
        size_bytes=preview_path.stat().st_size,
    )
