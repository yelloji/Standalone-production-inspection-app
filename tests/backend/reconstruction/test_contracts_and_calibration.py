"""Reconstruction contract and calibration evidence tests."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import CalibrationContract, RoiRectangle
from backend.reconstruction.calibration import (
    CalibrationFailure,
    PairMatchAttempt,
    PairObservation,
    build_calibration,
)
from tests.backend.reconstruction.factories import calibration, pair_attempt


def test_calibration_contract_rejects_bad_roi_and_inverse() -> None:
    current = calibration()
    with pytest.raises(ValidationError, match="ROI"):
        CalibrationContract.model_validate(
            {
                **current.model_dump(mode="python"),
                "usable_source_roi": {"x": 0, "y": 100, "width": 201, "height": 100},
            }
        )
    inverse = current.model_dump(mode="python")
    inverse["calibrated_to_source_matrix"] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    with pytest.raises(ValidationError, match="inverse"):
        CalibrationContract.model_validate(inverse)


def test_pair_observation_recovers_fixed_rotation_center() -> None:
    attempt = pair_attempt(1, center=(150.0, -500.0))
    assert attempt.observation is not None
    assert attempt.observation.rotation_center() == pytest.approx((150.0, -500.0))


def test_build_calibration_uses_robust_consensus_and_native_pixels() -> None:
    attempts = [pair_attempt(frame, center=(150.0, -500.0)) for frame in range(1, 17)]
    attempts[7] = pair_attempt(8, center=(1000.0, -500.0))
    result = build_calibration(
        acquisition_id="acquisition-001",
        side=DiscSide.UPPER,
        attempts=attempts,
        input_width=300,
        input_height=300,
        usable_source_roi=RoiRectangle(x=0, y=100, width=300, height=200),
    )
    assert result.calibration.source_disc_center.x == pytest.approx(150.0)
    assert result.calibration.source_disc_center.y == pytest.approx(-500.0)
    assert result.calibration.inner_radius < result.calibration.outer_radius
    assert len(result.accepted_pairs) == 15
    assert any("outlier" in reason for reason in result.rejected_pairs)


def test_build_calibration_rejects_incomplete_or_weak_evidence() -> None:
    with pytest.raises(CalibrationFailure, match="all 16"):
        build_calibration(
            acquisition_id="acquisition-001",
            side=DiscSide.UPPER,
            attempts=[pair_attempt(frame) for frame in range(1, 16)],
            input_width=200,
            input_height=200,
            usable_source_roi=RoiRectangle(x=0, y=100, width=200, height=100),
        )
    weak = [
        PairMatchAttempt(
            frame,
            frame + 1 if frame < 16 else 1,
            None,
            "no stable evidence",
        )
        for frame in range(1, 17)
    ]
    with pytest.raises(CalibrationFailure, match="reliable neighbor pairs"):
        build_calibration(
            acquisition_id="acquisition-001",
            side=DiscSide.UPPER,
            attempts=weak,
            input_width=200,
            input_height=200,
            usable_source_roi=RoiRectangle(x=0, y=100, width=200, height=100),
        )


def test_pair_observation_rejects_nonfinite_or_degenerate_geometry() -> None:
    with pytest.raises(CalibrationFailure, match="finite"):
        PairObservation(
            source_frame=1,
            target_frame=2,
            angle_degrees=math.nan,
            scale=1.0,
            affine_matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            inlier_count=10,
            median_residual_px=1.0,
        )
    observation = PairObservation(
        source_frame=1,
        target_frame=2,
        angle_degrees=-22.5,
        scale=1.0,
        affine_matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        inlier_count=10,
        median_residual_px=1.0,
    )
    with pytest.raises(CalibrationFailure, match="finite rotation center"):
        observation.rotation_center()
