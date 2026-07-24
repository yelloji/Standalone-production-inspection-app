"""Joint 16-frame projective reconstruction with independent validation gates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt
from scipy import optimize
from scipy.sparse import lil_matrix

from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import Matrix3x3
from backend.reconstruction.dense_evidence import DensePairEvidence, PointArray

FRAME_COUNT = 16
PARAMETERS_PER_FREE_POSE = 8


class ProjectiveReconstructionFailure(ValueError):
    """Raised when projective inputs violate the solver contract."""


@dataclass(frozen=True, slots=True)
class ProjectiveProfile:
    profile_id: str
    side: DiscSide
    working_scale: float
    excluded_top_fraction: float
    minimum_fit_points_per_pair: int = 8
    minimum_validation_points_per_pair: int = 5
    maximum_validation_median_px: float = 1.0
    maximum_validation_p95_px: float = 1.0
    maximum_validation_px: float = 1.0
    maximum_condition_number: float = 1.0e10
    maximum_solver_evaluations: int = 2000

    def __post_init__(self) -> None:
        if self.side not in {DiscSide.UPPER, DiscSide.LOWER}:
            raise ValueError("projective profile side must be upper or lower")
        if not 0.05 <= self.working_scale <= 1.0:
            raise ValueError("projective working scale is outside the safe range")
        if not 0.0 <= self.excluded_top_fraction < 0.8:
            raise ValueError("excluded top fraction is outside the safe range")
        if self.minimum_fit_points_per_pair < 4:
            raise ValueError("projective profile requires at least four fit points")
        if self.minimum_validation_points_per_pair < 1:
            raise ValueError("projective profile requires held-out validation")
        thresholds = (
            self.maximum_validation_median_px,
            self.maximum_validation_p95_px,
            self.maximum_validation_px,
            self.maximum_condition_number,
        )
        if not all(math.isfinite(value) and value > 0 for value in thresholds):
            raise ValueError("projective validation limits must be finite and positive")
        if self.maximum_solver_evaluations < 1:
            raise ValueError("projective solver evaluation limit must be positive")


LOWER_PROJECTIVE_PROFILE = ProjectiveProfile(
    profile_id="brake-disc-lower-projective-v1",
    side=DiscSide.LOWER,
    working_scale=0.25,
    excluded_top_fraction=0.18,
)
UPPER_PROJECTIVE_PROFILE = ProjectiveProfile(
    profile_id="brake-disc-upper-projective-v1",
    side=DiscSide.UPPER,
    working_scale=0.25,
    excluded_top_fraction=0.18,
)


@dataclass(frozen=True, slots=True)
class ProjectivePairValidation:
    source_frame: int
    target_frame: int
    is_loop_closure: bool
    fit_count: int
    validation_count: int
    validation_median_px: float | None
    validation_p95_px: float | None
    validation_maximum_px: float | None
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectiveReconstructionResult:
    profile_id: str
    passed: bool
    optimizer_succeeded: bool
    optimizer_message: str
    optimizer_cost: float
    diagnostic_frame_to_reference_matrices: tuple[Matrix3x3, ...] | None
    frame_to_reference_matrices: tuple[Matrix3x3, ...] | None
    pair_validations: tuple[ProjectivePairValidation, ...]
    validation_median_px: float | None
    validation_p95_px: float | None
    validation_maximum_px: float | None
    failure_reasons: tuple[str, ...]


def _expected_target(source_frame: int) -> int:
    return source_frame + 1 if source_frame < FRAME_COUNT else 1


def _validate_cycle(
    pairs: tuple[DensePairEvidence, ...] | list[DensePairEvidence],
) -> tuple[DensePairEvidence, ...]:
    if len(pairs) != FRAME_COUNT:
        raise ProjectiveReconstructionFailure("projective solve requires exactly 16 pair records")
    for position, pair in enumerate(pairs, start=1):
        if pair.source_frame != position or pair.target_frame != _expected_target(position):
            raise ProjectiveReconstructionFailure(
                "projective pairs must follow the complete ordered 16-frame cycle"
            )
    return tuple(pairs)


def _project(matrix: npt.NDArray[np.float64], points: PointArray) -> PointArray:
    homogeneous = np.column_stack((points, np.ones(len(points), dtype=np.float64)))
    mapped = (matrix @ homogeneous.T).T
    denominator = mapped[:, 2]
    if np.any(np.abs(denominator) < 1e-10):
        raise ProjectiveReconstructionFailure("projective mapping contains a point at infinity")
    result = mapped[:, :2] / denominator[:, None]
    if not np.isfinite(result).all():
        raise ProjectiveReconstructionFailure("projective mapping produced non-finite points")
    return result


def _fit_homography(source: PointArray, target: PointArray) -> npt.NDArray[np.float64]:
    if len(source) < 4 or len(target) != len(source):
        raise ProjectiveReconstructionFailure("homography fitting requires four matched points")
    rows = []
    for (source_x, source_y), (target_x, target_y) in zip(source, target, strict=True):
        rows.append(
            (
                -source_x,
                -source_y,
                -1.0,
                0.0,
                0.0,
                0.0,
                target_x * source_x,
                target_x * source_y,
                target_x,
            )
        )
        rows.append(
            (
                0.0,
                0.0,
                0.0,
                -source_x,
                -source_y,
                -1.0,
                target_y * source_x,
                target_y * source_y,
                target_y,
            )
        )
    _, _, right = np.linalg.svd(np.asarray(rows, dtype=np.float64), full_matrices=True)
    matrix = right[-1].reshape(3, 3)
    if abs(matrix[2, 2]) < 1e-12:
        raise ProjectiveReconstructionFailure("fitted homography has an invalid scale")
    matrix /= matrix[2, 2]
    if abs(np.linalg.det(matrix)) < 1e-12:
        raise ProjectiveReconstructionFailure("fitted homography is singular")
    return cast(npt.NDArray[np.float64], matrix)


def _matrix_to_parameters(matrix: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    matrix = matrix / matrix[2, 2]
    return np.asarray(
        (
            matrix[0, 0],
            matrix[0, 1],
            matrix[0, 2],
            matrix[1, 0],
            matrix[1, 1],
            matrix[1, 2],
            matrix[2, 0],
            matrix[2, 1],
        )
    )


def _parameters_to_matrix(parameters: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    return np.asarray(
        (
            (parameters[0], parameters[1], parameters[2]),
            (parameters[3], parameters[4], parameters[5]),
            (parameters[6], parameters[7], 1.0),
        )
    )


def _poses_from_vector(vector: npt.NDArray[np.float64]) -> list[npt.NDArray[np.float64]]:
    return [np.eye(3, dtype=np.float64)] + [
        _parameters_to_matrix(
            vector[index * PARAMETERS_PER_FREE_POSE : (index + 1) * PARAMETERS_PER_FREE_POSE]
        )
        for index in range(FRAME_COUNT - 1)
    ]


def solve_projective_reconstruction(
    pairs: tuple[DensePairEvidence, ...] | list[DensePairEvidence],
    *,
    image_width: int,
    image_height: int,
    profile: ProjectiveProfile,
) -> ProjectiveReconstructionResult:
    """Jointly solve 15 free poses and gate all 16 held-out neighbor joins."""

    evidence = _validate_cycle(pairs)
    if image_width <= 0 or image_height <= 0:
        raise ProjectiveReconstructionFailure("source image dimensions must be positive")

    early_failures = []
    for pair in evidence:
        if len(pair.fit_source_points) < profile.minimum_fit_points_per_pair:
            early_failures.append(f"{pair.pair_name}: insufficient fit evidence")
    if early_failures:
        return ProjectiveReconstructionResult(
            profile.profile_id,
            False,
            False,
            "solver not started",
            math.inf,
            None,
            None,
            (),
            None,
            None,
            None,
            tuple(early_failures),
        )

    normalization = np.asarray(
        (
            (1.0 / image_width, 0.0, -0.5),
            (0.0, 1.0 / image_width, -image_height / (2.0 * image_width)),
            (0.0, 0.0, 1.0),
        )
    )
    inverse_normalization = np.linalg.inv(normalization)

    pair_homographies = [
        _fit_homography(pair.fit_source_points, pair.fit_target_points) for pair in evidence
    ]
    initial_pixel_poses = [np.eye(3, dtype=np.float64)]
    for index in range(FRAME_COUNT - 1):
        initial_pixel_poses.append(
            initial_pixel_poses[-1] @ np.linalg.inv(pair_homographies[index])
        )
    initial_poses = [normalization @ pose @ inverse_normalization for pose in initial_pixel_poses]
    initial_poses = [pose / pose[2, 2] for pose in initial_poses]
    initial = np.concatenate([_matrix_to_parameters(pose) for pose in initial_poses[1:]])

    normalized_pairs = [
        (
            _project(normalization, pair.fit_source_points),
            _project(normalization, pair.fit_target_points),
        )
        for pair in evidence
    ]

    def residual_function(vector: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        poses = _poses_from_vector(vector)
        residuals = []
        for pair, (source_points, target_points) in zip(
            evidence,
            normalized_pairs,
            strict=True,
        ):
            source_global = _project(poses[pair.source_frame - 1], source_points)
            target_global = _project(poses[pair.target_frame - 1], target_points)
            residuals.append(((source_global - target_global) * image_width).ravel())
        return np.concatenate(residuals)

    residual_count = sum(len(pair.fit_source_points) * 2 for pair in evidence)
    sparsity = lil_matrix(
        (residual_count, (FRAME_COUNT - 1) * PARAMETERS_PER_FREE_POSE),
        dtype=np.int8,
    )
    row = 0
    for pair in evidence:
        count = len(pair.fit_source_points) * 2
        for frame in (pair.source_frame - 1, pair.target_frame - 1):
            if frame:
                start = (frame - 1) * PARAMETERS_PER_FREE_POSE
                sparsity[row : row + count, start : start + PARAMETERS_PER_FREE_POSE] = 1
        row += count

    # scipy-stubs 1.15.3 models this public function as a module.
    optimized = optimize.least_squares(  # type: ignore[operator]
        residual_function,
        initial,
        jac_sparsity=sparsity.tocsr(),
        method="trf",
        loss="linear",
        x_scale="jac",
        max_nfev=profile.maximum_solver_evaluations,
        ftol=1e-9,
        xtol=1e-9,
        gtol=1e-9,
    )
    optimized_vector = np.asarray(optimized.x, dtype=np.float64)
    normalized_poses = _poses_from_vector(optimized_vector)
    pixel_poses = [inverse_normalization @ pose @ normalization for pose in normalized_poses]
    pixel_poses = [pose / pose[2, 2] for pose in pixel_poses]

    failures = []
    for index, pose in enumerate(pixel_poses, start=1):
        condition = float(np.linalg.cond(pose))
        if not math.isfinite(condition) or condition > profile.maximum_condition_number:
            failures.append(f"frame {index}: projective transform is ill-conditioned")

    pair_validations = []
    all_validation_residuals: list[float] = []
    for pair in evidence:
        pair_failures = []
        validation_count = len(pair.validation_source_points)
        if validation_count < profile.minimum_validation_points_per_pair:
            pair_failures.append("insufficient held-out evidence")
            median_px = p95_px = maximum_px = None
        else:
            source_global = _project(
                normalized_poses[pair.source_frame - 1],
                _project(normalization, pair.validation_source_points),
            )
            target_global = _project(
                normalized_poses[pair.target_frame - 1],
                _project(normalization, pair.validation_target_points),
            )
            residuals = np.linalg.norm(source_global - target_global, axis=1) * image_width
            median_px = float(np.median(residuals))
            p95_px = float(np.percentile(residuals, 95))
            maximum_px = float(np.max(residuals))
            all_validation_residuals.extend(float(value) for value in residuals)
            if median_px > profile.maximum_validation_median_px:
                pair_failures.append("held-out median exceeds profile limit")
            if p95_px > profile.maximum_validation_p95_px:
                pair_failures.append("held-out 95th percentile exceeds profile limit")
            if maximum_px > profile.maximum_validation_px:
                pair_failures.append("held-out maximum exceeds profile limit")
        pair_validation = ProjectivePairValidation(
            source_frame=pair.source_frame,
            target_frame=pair.target_frame,
            is_loop_closure=pair.source_frame == FRAME_COUNT,
            fit_count=len(pair.fit_source_points),
            validation_count=validation_count,
            validation_median_px=median_px,
            validation_p95_px=p95_px,
            validation_maximum_px=maximum_px,
            passed=not pair_failures,
            failure_reasons=tuple(pair_failures),
        )
        pair_validations.append(pair_validation)
        failures.extend(f"{pair.pair_name}: {reason}" for reason in pair_failures)

    if not optimized.success:
        failures.append(f"optimizer failed: {optimized.message}")
    overall_median: float | None
    overall_p95: float | None
    overall_maximum: float | None
    if all_validation_residuals:
        residual_array = np.asarray(all_validation_residuals)
        overall_median = float(np.median(residual_array))
        overall_p95 = float(np.percentile(residual_array, 95))
        overall_maximum = float(np.max(residual_array))
    else:
        overall_median = None
        overall_p95 = None
        overall_maximum = None
    matrices = tuple(
        cast(
            Matrix3x3,
            tuple(tuple(float(value) for value in row_values) for row_values in pose),
        )
        for pose in pixel_poses
    )
    passed = not failures
    return ProjectiveReconstructionResult(
        profile_id=profile.profile_id,
        passed=passed,
        optimizer_succeeded=bool(optimized.success),
        optimizer_message=str(optimized.message),
        optimizer_cost=float(optimized.cost),
        diagnostic_frame_to_reference_matrices=matrices,
        frame_to_reference_matrices=matrices if passed else None,
        pair_validations=tuple(pair_validations),
        validation_median_px=overall_median,
        validation_p95_px=overall_p95,
        validation_maximum_px=overall_maximum,
        failure_reasons=tuple(failures),
    )
