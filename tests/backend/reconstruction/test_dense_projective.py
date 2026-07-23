"""Dense evidence splitting and joint projective reconstruction tests."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pytest

from backend.domain.contracts import DiscSide
from backend.reconstruction.dense_evidence import (
    DenseEvidenceFailure,
    DensePairEvidence,
    split_spatial_evidence,
)
from backend.reconstruction.projective import (
    LOWER_PROJECTIVE_PROFILE,
    UPPER_PROJECTIVE_PROFILE,
    ProjectiveReconstructionFailure,
    solve_projective_reconstruction,
)


def _project(
    matrix: npt.NDArray[np.float64],
    points: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    homogeneous = np.column_stack((points, np.ones(len(points))))
    mapped = (matrix @ homogeneous.T).T
    return mapped[:, :2] / mapped[:, 2, None]


def _pose(index: int) -> npt.NDArray[np.float64]:
    angle = math.radians(index * 0.15)
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.asarray(
        (
            (cosine, -sine, index * 0.25),
            (sine, cosine, -index * 0.15),
            (index * 1.0e-7, -index * 0.5e-7, 1.0),
        ),
        dtype=np.float64,
    )


def _exact_cycle() -> tuple[list[DensePairEvidence], list[npt.NDArray[np.float64]]]:
    poses = [_pose(index) for index in range(16)]
    x_values, y_values = np.meshgrid(
        np.linspace(40.0, 600.0, 8),
        np.linspace(30.0, 450.0, 6),
    )
    base_points = np.column_stack((x_values.ravel(), y_values.ravel()))
    pairs = []
    for source in range(16):
        target = (source + 1) % 16
        source_points = base_points + np.asarray((source * 0.01, source * 0.02))
        pair_homography = np.linalg.inv(poses[target]) @ poses[source]
        target_points = _project(pair_homography, source_points)
        pairs.append(
            split_spatial_evidence(
                source_frame=source + 1,
                target_frame=target + 1,
                source_points=source_points,
                target_points=target_points,
                tile_size=64,
            )
        )
    return pairs, poses


def test_spatial_split_is_deterministic_disjoint_and_immutable() -> None:
    points = np.asarray(
        [(float(x), float(y)) for y in range(0, 400, 40) for x in range(0, 600, 50)]
    )
    target = points + np.asarray((2.0, -3.0))
    first = split_spatial_evidence(
        source_frame=1,
        target_frame=2,
        source_points=points,
        target_points=target,
        tile_size=64,
    )
    second = split_spatial_evidence(
        source_frame=1,
        target_frame=2,
        source_points=points[::-1],
        target_points=target[::-1],
        tile_size=64,
    )
    assert first.fit_source_points == pytest.approx(second.fit_source_points)
    assert first.validation_source_points == pytest.approx(second.validation_source_points)
    fit = {tuple(point) for point in first.fit_source_points}
    held_out = {tuple(point) for point in first.validation_source_points}
    assert fit.isdisjoint(held_out)
    with pytest.raises(ValueError):
        first.fit_source_points[0, 0] = 0.0


def test_spatial_split_rejects_insufficient_or_invalid_evidence() -> None:
    with pytest.raises(DenseEvidenceFailure, match="at least ten"):
        split_spatial_evidence(
            source_frame=1,
            target_frame=2,
            source_points=np.zeros((9, 2)),
            target_points=np.zeros((9, 2)),
        )
    with pytest.raises(DenseEvidenceFailure, match="counts"):
        split_spatial_evidence(
            source_frame=1,
            target_frame=2,
            source_points=np.zeros((10, 2)),
            target_points=np.zeros((11, 2)),
        )


def test_upper_and_lower_profiles_are_explicit_pipeline_choices() -> None:
    assert LOWER_PROJECTIVE_PROFILE.side is DiscSide.LOWER
    assert UPPER_PROJECTIVE_PROFILE.side is DiscSide.UPPER
    assert LOWER_PROJECTIVE_PROFILE.profile_id != UPPER_PROJECTIVE_PROFILE.profile_id
    assert LOWER_PROJECTIVE_PROFILE.maximum_validation_px == 1.0
    assert UPPER_PROJECTIVE_PROFILE.maximum_validation_px == 1.0


def test_joint_projective_solve_recovers_exact_cycle_with_closure() -> None:
    pairs, expected = _exact_cycle()
    result = solve_projective_reconstruction(
        pairs,
        image_width=640,
        image_height=480,
        profile=LOWER_PROJECTIVE_PROFILE,
    )
    assert result.passed
    assert result.optimizer_succeeded
    assert result.frame_to_reference_matrices is not None
    assert result.validation_maximum_px is not None
    assert result.validation_maximum_px < 1.0e-5
    assert len(result.pair_validations) == 16
    assert result.pair_validations[-1].is_loop_closure
    for actual, wanted in zip(
        result.frame_to_reference_matrices,
        expected,
        strict=True,
    ):
        actual_matrix = np.asarray(actual) / actual[2][2]
        wanted_matrix = wanted / wanted[2, 2]
        assert actual_matrix == pytest.approx(wanted_matrix, abs=1.0e-5)


def test_held_out_outlier_blocks_transforms_and_identifies_loop_closure() -> None:
    pairs, _ = _exact_cycle()
    closure = pairs[-1]
    bad_targets = closure.validation_target_points.copy()
    bad_targets[0, 0] += 2.0
    bad_targets.setflags(write=False)
    pairs[-1] = DensePairEvidence(
        source_frame=closure.source_frame,
        target_frame=closure.target_frame,
        fit_source_points=closure.fit_source_points,
        fit_target_points=closure.fit_target_points,
        validation_source_points=closure.validation_source_points,
        validation_target_points=bad_targets,
    )
    result = solve_projective_reconstruction(
        pairs,
        image_width=640,
        image_height=480,
        profile=LOWER_PROJECTIVE_PROFILE,
    )
    assert not result.passed
    assert result.frame_to_reference_matrices is None
    assert not result.pair_validations[-1].passed
    assert result.pair_validations[-1].is_loop_closure
    assert any("16->1" in reason for reason in result.failure_reasons)


def test_insufficient_held_out_evidence_never_becomes_a_pass() -> None:
    pairs, _ = _exact_cycle()
    current = pairs[7]
    pairs[7] = DensePairEvidence(
        source_frame=current.source_frame,
        target_frame=current.target_frame,
        fit_source_points=current.fit_source_points,
        fit_target_points=current.fit_target_points,
        validation_source_points=current.validation_source_points[:2],
        validation_target_points=current.validation_target_points[:2],
    )
    result = solve_projective_reconstruction(
        pairs,
        image_width=640,
        image_height=480,
        profile=UPPER_PROJECTIVE_PROFILE,
    )
    assert not result.passed
    assert "insufficient held-out evidence" in result.failure_reasons[0]


def test_projective_solver_rejects_incomplete_or_misordered_cycle() -> None:
    pairs, _ = _exact_cycle()
    with pytest.raises(ProjectiveReconstructionFailure, match="exactly 16"):
        solve_projective_reconstruction(
            pairs[:-1],
            image_width=640,
            image_height=480,
            profile=LOWER_PROJECTIVE_PROFILE,
        )
    pairs[1] = DensePairEvidence(
        source_frame=2,
        target_frame=4,
        fit_source_points=pairs[1].fit_source_points,
        fit_target_points=pairs[1].fit_target_points,
        validation_source_points=pairs[1].validation_source_points,
        validation_target_points=pairs[1].validation_target_points,
    )
    with pytest.raises(ProjectiveReconstructionFailure, match="ordered"):
        solve_projective_reconstruction(
            pairs,
            image_width=640,
            image_height=480,
            profile=LOWER_PROJECTIVE_PROFILE,
        )
