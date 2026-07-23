"""Globally closed similarity poses that preserve complete source frames."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt

from backend.domain.reconstruction import Matrix3x3
from backend.reconstruction.calibration import PairMatchAttempt

FRAME_COUNT = 16


@dataclass(frozen=True, slots=True)
class PoseGraphResult:
    frame_to_reference_matrices: tuple[Matrix3x3, ...]
    edge_median_residuals_px: tuple[float, ...]
    edge_maximum_residuals_px: tuple[float, ...]
    union_bounds_xyxy: tuple[float, float, float, float]
    maximum_edge_median_residual_px: float
    maximum_edge_residual_px: float
    angle_corrections_degrees: tuple[float, ...]
    scale_corrections: tuple[float, ...]


def _weighted_solve(
    rows: Sequence[npt.NDArray[np.float64]],
    targets: Sequence[float],
    weights: Sequence[float],
) -> npt.NDArray[np.float64]:
    matrix = np.asarray(rows, dtype=np.float64)
    target = np.asarray(targets, dtype=np.float64)
    root = np.sqrt(np.asarray(weights, dtype=np.float64))
    return cast(
        npt.NDArray[np.float64],
        np.linalg.lstsq(matrix * root[:, None], target * root, rcond=None)[0],
    )


def _observation_matrix(attempt: PairMatchAttempt) -> npt.NDArray[np.float64]:
    if attempt.observation is None:
        raise ValueError(f"pair {attempt.pair_name} has no measured transform")
    matrix = np.eye(3, dtype=np.float64)
    matrix[:2, :] = np.asarray(attempt.observation.affine_matrix, dtype=np.float64)
    return matrix


def solve_similarity_pose_graph(
    attempts: tuple[PairMatchAttempt, ...] | list[PairMatchAttempt],
    input_width: int,
    input_height: int,
) -> PoseGraphResult:
    """Close all 16 measured similarities without cropping any source frame."""

    if len(attempts) != FRAME_COUNT:
        raise ValueError("pose graph requires exactly 16 pair attempts")
    if input_width <= 0 or input_height <= 0:
        raise ValueError("source dimensions must be positive")

    observations = []
    weights = []
    for index, attempt in enumerate(attempts):
        expected_target = index + 2 if index < FRAME_COUNT - 1 else 1
        if attempt.source_frame != index + 1 or attempt.target_frame != expected_target:
            raise ValueError("pair attempts must follow the complete ordered acquisition cycle")
        observation = attempt.observation
        if observation is None:
            raise ValueError(f"pair {attempt.pair_name} has no measured transform")
        if observation.scale <= 0 or observation.inlier_count < 3:
            raise ValueError(f"pair {attempt.pair_name} has invalid similarity evidence")
        observations.append(observation)
        weights.append(
            max(1e-6, min(1.0, observation.inlier_count / 50.0))
            / max(0.5, observation.median_residual_px) ** 2
        )

    edge_rows = []
    angle_targets = []
    scale_targets = []
    for index, observation in enumerate(observations):
        row = np.zeros(FRAME_COUNT, dtype=np.float64)
        row[(index + 1) % FRAME_COUNT] = 1.0
        row[index] -= 1.0
        edge_rows.append(row)
        angle_target = -math.radians(observation.angle_degrees)
        if index == FRAME_COUNT - 1:
            angle_target -= 2.0 * math.pi
        angle_targets.append(angle_target)
        scale_targets.append(-math.log(observation.scale))

    anchor = np.zeros(FRAME_COUNT, dtype=np.float64)
    anchor[0] = 1.0
    solve_weights = weights + [1000.0]
    angles = _weighted_solve(edge_rows + [anchor], angle_targets + [0.0], solve_weights)
    log_scales = _weighted_solve(
        edge_rows + [anchor],
        scale_targets + [0.0],
        solve_weights,
    )

    linear_parts = []
    for angle, log_scale in zip(angles, log_scales, strict=True):
        scale = math.exp(float(log_scale))
        cosine, sine = math.cos(float(angle)), math.sin(float(angle))
        linear_parts.append(scale * np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64))

    translation_rows = []
    target_x = []
    target_y = []
    for index, observation in enumerate(observations):
        source, target = index, (index + 1) % FRAME_COUNT
        row = np.zeros(FRAME_COUNT, dtype=np.float64)
        row[source] = 1.0
        row[target] -= 1.0
        translated = (
            linear_parts[target]
            @ np.asarray(
                observation.affine_matrix,
                dtype=np.float64,
            )[:, 2]
        )
        translation_rows.append(row)
        target_x.append(float(translated[0]))
        target_y.append(float(translated[1]))
    translations_x = _weighted_solve(
        translation_rows + [anchor],
        target_x + [0.0],
        solve_weights,
    )
    translations_y = _weighted_solve(
        translation_rows + [anchor],
        target_y + [0.0],
        solve_weights,
    )

    poses = []
    for linear, tx, ty in zip(
        linear_parts,
        translations_x,
        translations_y,
        strict=True,
    ):
        pose = np.eye(3, dtype=np.float64)
        pose[:2, :2] = linear
        pose[:2, 2] = (tx, ty)
        poses.append(pose)

    sample_points = np.asarray(
        (
            (0.0, 0.0, 1.0),
            (input_width, 0.0, 1.0),
            (input_width, input_height, 1.0),
            (0.0, input_height, 1.0),
            (input_width / 2.0, input_height / 2.0, 1.0),
        ),
        dtype=np.float64,
    ).T
    medians = []
    maximums = []
    for index in range(FRAME_COUNT):
        target = (index + 1) % FRAME_COUNT
        transformed = _observation_matrix(attempts[index]) @ sample_points
        source_global = poses[index] @ sample_points
        target_global = poses[target] @ transformed
        residuals = np.linalg.norm(source_global[:2] - target_global[:2], axis=0)
        medians.append(float(np.median(residuals)))
        maximums.append(float(np.max(residuals)))

    corners = sample_points[:, :4]
    all_corners = np.concatenate([(pose @ corners)[:2] for pose in poses], axis=1)
    nominal_angles = np.radians(np.arange(FRAME_COUNT, dtype=np.float64) * 22.5)
    matrices = tuple(
        cast(
            Matrix3x3,
            tuple(tuple(float(value) for value in row) for row in pose),
        )
        for pose in poses
    )
    return PoseGraphResult(
        frame_to_reference_matrices=matrices,
        edge_median_residuals_px=tuple(medians),
        edge_maximum_residuals_px=tuple(maximums),
        union_bounds_xyxy=(
            float(np.min(all_corners[0])),
            float(np.min(all_corners[1])),
            float(np.max(all_corners[0])),
            float(np.max(all_corners[1])),
        ),
        maximum_edge_median_residual_px=max(medians),
        maximum_edge_residual_px=max(maximums),
        angle_corrections_degrees=tuple(
            float(math.degrees(angle - nominal))
            for angle, nominal in zip(angles, nominal_angles, strict=True)
        ),
        scale_corrections=tuple(float(math.exp(value)) for value in log_scales),
    )
