"""Global registration and complete-source pose-graph tests."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pytest

from backend.domain.reconstruction import TransformSetContract
from backend.reconstruction.calibration import PairMatchAttempt, PairObservation
from backend.reconstruction.placement import build_nominal_transform_set, map_points
from backend.reconstruction.pose_graph import solve_similarity_pose_graph
from backend.reconstruction.registration import refine_nominal_transforms
from tests.backend.reconstruction.factories import (
    acquisition_manifest,
    attempts_for_frame_corrections,
    calibration,
    pair_attempt,
)


def nominal_transforms() -> TransformSetContract:
    return build_nominal_transform_set(
        acquisition_manifest(),
        calibration(),
        calibration_relative_path="processing/acquisition-001/calibration.json",
        mask_directory_relative_path="processing/acquisition-001/masks",
    )


def test_global_registration_recovers_bounded_corrections_and_closes_loop() -> None:
    expected = [
        0.0,
        0.10,
        0.15,
        0.05,
        -0.05,
        -0.10,
        -0.15,
        -0.10,
        0.0,
        0.10,
        0.15,
        0.10,
        0.0,
        -0.05,
        -0.10,
        -0.05,
    ]
    result = refine_nominal_transforms(
        nominal_transforms(),
        calibration(),
        attempts_for_frame_corrections(expected),
    )
    assert result.passed
    assert result.corrected_transforms is not None
    assert result.frame_corrections_degrees == pytest.approx(expected, abs=1e-9)
    assert result.maximum_loop_residual_px is not None
    assert result.maximum_loop_residual_px < 1e-8
    assert result.pair_results[-1].is_loop_closure
    points = np.asarray(((0.0, 100.0), (100.0, 150.0), (199.0, 199.0)))
    for transform in result.corrected_transforms.transforms:
        mapped = map_points(transform.source_to_output_matrix, points)
        restored = map_points(transform.output_to_source_matrix, mapped)
        assert restored == pytest.approx(points, abs=1e-8)


def test_registration_refuses_missing_or_wrong_center_evidence() -> None:
    attempts = attempts_for_frame_corrections([0.0] * 16)
    attempts[7] = PairMatchAttempt(8, 9, None, "no stable correspondence")
    result = refine_nominal_transforms(nominal_transforms(), calibration(), attempts)
    assert not result.passed
    assert result.corrected_transforms is None
    assert "8->9" in result.failure_reasons[0]

    attempts = attempts_for_frame_corrections([0.0] * 16)
    attempts[2] = pair_attempt(3, center=(300.0, -500.0))
    result = refine_nominal_transforms(nominal_transforms(), calibration(), attempts)
    assert not result.passed
    assert "fixed calibration" in result.failure_reasons[0]


def test_registration_rejects_global_limit_and_loop_residual() -> None:
    corrections = [
        0.0,
        0.3,
        0.6,
        0.9,
        1.2,
        1.5,
        1.8,
        2.1,
        1.8,
        1.5,
        1.2,
        0.9,
        0.6,
        0.3,
        0.1,
        0.0,
    ]
    result = refine_nominal_transforms(
        nominal_transforms(),
        calibration(),
        attempts_for_frame_corrections(corrections),
    )
    assert not result.passed
    assert any("limit is 2.0" in reason for reason in result.failure_reasons)

    attempts = attempts_for_frame_corrections([0.0] * 16)
    attempts[-1] = pair_attempt(16, step_correction=1.0)
    large_radius_calibration = calibration().model_copy(update={"outer_radius": 4000.0})
    result = refine_nominal_transforms(
        nominal_transforms(),
        large_radius_calibration,
        attempts,
    )
    assert not result.passed
    assert any("loop residual" in reason for reason in result.failure_reasons)


def _pose(
    angle_degrees: float,
    tx: float,
    ty: float,
    scale: float = 1.0,
) -> npt.NDArray[np.float64]:
    radians = math.radians(angle_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    return np.asarray(
        (
            (scale * cosine, -scale * sine, tx),
            (scale * sine, scale * cosine, ty),
            (0.0, 0.0, 1.0),
        )
    )


def _closed_attempts() -> tuple[
    list[PairMatchAttempt],
    list[npt.NDArray[np.float64]],
]:
    corrections = [
        0.0,
        0.4,
        -0.3,
        0.7,
        -0.5,
        0.2,
        -0.6,
        0.5,
        -0.2,
        0.6,
        -0.4,
        0.3,
        -0.7,
        0.1,
        0.5,
        -0.3,
    ]
    poses = [
        _pose(
            index * 22.5 + corrections[index],
            index * 1.5,
            -index * 0.75,
            1.0 + index * 0.0001,
        )
        for index in range(16)
    ]
    attempts = []
    for index, source_pose in enumerate(poses):
        target = (index + 1) % 16
        observed = np.linalg.inv(poses[target]) @ source_pose
        attempts.append(
            PairMatchAttempt(
                index + 1,
                target + 1,
                PairObservation(
                    source_frame=index + 1,
                    target_frame=target + 1,
                    angle_degrees=math.degrees(math.atan2(observed[1, 0], observed[0, 0])),
                    scale=math.hypot(observed[0, 0], observed[0, 1]),
                    affine_matrix=(tuple(observed[0]), tuple(observed[1])),
                    inlier_count=40,
                    median_residual_px=1.0,
                ),
            )
        )
    return attempts, poses


def test_pose_graph_recovers_complete_frame_poses_and_bounds() -> None:
    attempts, expected = _closed_attempts()
    result = solve_similarity_pose_graph(attempts, 100, 60)
    assert result.maximum_edge_residual_px < 1e-8
    for actual, wanted in zip(result.frame_to_reference_matrices, expected, strict=True):
        assert np.asarray(actual) == pytest.approx(wanted, abs=1e-8)
    left, top, right, bottom = result.union_bounds_xyxy
    assert left <= right and top <= bottom


def test_pose_graph_refuses_missing_evidence() -> None:
    attempts, _ = _closed_attempts()
    attempts[8] = PairMatchAttempt(9, 10, None, "no evidence")
    with pytest.raises(ValueError, match="9->10"):
        solve_similarity_pose_graph(attempts, 100, 60)
