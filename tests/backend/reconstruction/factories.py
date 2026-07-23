"""Deterministic fixtures for reconstruction geometry tests."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from backend.domain.acquisition import AcquisitionFrameManifest, AcquisitionManifest
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import (
    CalibrationContract,
    CalibrationState,
    Point2D,
    RoiRectangle,
)
from backend.reconstruction.calibration import PairMatchAttempt, PairObservation


def acquisition_manifest() -> AcquisitionManifest:
    return AcquisitionManifest(
        acquisition_id="acquisition-001",
        side=DiscSide.UPPER,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
        expected_width=200,
        expected_height=200,
        frames=tuple(
            AcquisitionFrameManifest(
                position=position,
                angle_degrees=(position - 1) * 22.5,
                original_relative_path=f"frame-{position:02d}.png",
                owned_relative_path=f"incoming/acquisition-001/frame-{position:02d}.png",
                image_format="PNG",
                pixel_mode="RGB",
                width=200,
                height=200,
                size_bytes=1000 + position,
                sha256=f"{position:064x}",
            )
            for position in range(1, 17)
        ),
    )


def calibration() -> CalibrationContract:
    outer = math.hypot(100.0, 700.0)
    radius = math.ceil(outer) + 1
    translate_x, translate_y = radius - 100.0, radius + 500.0
    return CalibrationContract(
        acquisition_id="acquisition-001",
        side=DiscSide.UPPER,
        state=CalibrationState.VALIDATED,
        input_width=200,
        input_height=200,
        output_width=2 * radius + 1,
        output_height=2 * radius + 1,
        usable_source_roi=RoiRectangle(x=0, y=100, width=200, height=100),
        source_disc_center=Point2D(x=100.0, y=-500.0),
        output_disc_center=Point2D(x=radius, y=radius),
        inner_radius=600.0,
        outer_radius=outer,
        reference_ray_degrees=90.0,
        source_to_calibrated_matrix=(
            (1.0, 0.0, translate_x),
            (0.0, 1.0, translate_y),
            (0.0, 0.0, 1.0),
        ),
        calibrated_to_source_matrix=(
            (1.0, 0.0, -translate_x),
            (0.0, 1.0, -translate_y),
            (0.0, 0.0, 1.0),
        ),
    )


def pair_attempt(
    frame: int,
    *,
    center: tuple[float, float] = (100.0, -500.0),
    step_correction: float = 0.0,
    inliers: int = 30,
    residual: float = 1.0,
) -> PairMatchAttempt:
    angle_degrees = -(22.5 + step_correction)
    radians = math.radians(angle_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    translate_x = center[0] - (cosine * center[0] - sine * center[1])
    translate_y = center[1] - (sine * center[0] + cosine * center[1])
    target = frame + 1 if frame < 16 else 1
    observation = PairObservation(
        source_frame=frame,
        target_frame=target,
        angle_degrees=angle_degrees,
        scale=1.0,
        affine_matrix=(
            (cosine, -sine, translate_x),
            (sine, cosine, translate_y),
        ),
        inlier_count=inliers,
        median_residual_px=residual,
    )
    return PairMatchAttempt(frame, target, observation)


def attempts_for_frame_corrections(corrections: list[float]) -> list[PairMatchAttempt]:
    return [
        pair_attempt(
            index + 1,
            step_correction=corrections[(index + 1) % 16] - corrections[index],
        )
        for index in range(16)
    ]
