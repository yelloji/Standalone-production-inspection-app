"""Evidence-driven fixed-camera calibration geometry."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import (
    CalibrationContract,
    CalibrationState,
    Point2D,
    RoiRectangle,
)

FRAME_COUNT = 16
EXPECTED_ROTATION_DEGREES = -22.5
MAX_ANGLE_DEVIATION_DEGREES = 2.0
MIN_SCALE = 0.995
MAX_SCALE = 1.005
MIN_INLIER_COUNT = 5
MAX_MEDIAN_RESIDUAL_PX = 4.0
MIN_ACCEPTED_PAIRS = 5
MAX_CENTER_DEVIATION_PX = 250.0

Affine2x3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
]


class CalibrationFailure(ValueError):
    """Raised when evidence cannot safely establish one calibration."""


@dataclass(frozen=True, slots=True)
class PairObservation:
    source_frame: int
    target_frame: int
    angle_degrees: float
    scale: float
    affine_matrix: Affine2x3
    inlier_count: int
    median_residual_px: float

    def __post_init__(self) -> None:
        numbers = (
            self.angle_degrees,
            self.scale,
            self.median_residual_px,
            *(number for row in self.affine_matrix for number in row),
        )
        if not all(math.isfinite(number) for number in numbers):
            raise CalibrationFailure("pair observation values must be finite")
        if self.scale <= 0 or self.inlier_count < 0 or self.median_residual_px < 0:
            raise CalibrationFailure("pair observation evidence is invalid")

    def rotation_center(self) -> tuple[float, float]:
        """Solve ``translation = (identity - linear) * center``."""

        r00, r01, tx = self.affine_matrix[0]
        r10, r11, ty = self.affine_matrix[1]
        a00, a01 = 1.0 - r00, -r01
        a10, a11 = -r10, 1.0 - r11
        determinant = a00 * a11 - a01 * a10
        if abs(determinant) < 1e-9:
            raise CalibrationFailure("pair transform cannot define a finite rotation center")
        center_x = (tx * a11 - a01 * ty) / determinant
        center_y = (a00 * ty - tx * a10) / determinant
        if not math.isfinite(center_x) or not math.isfinite(center_y):
            raise CalibrationFailure("pair transform produced a non-finite rotation center")
        return center_x, center_y


@dataclass(frozen=True, slots=True)
class PairMatchAttempt:
    source_frame: int
    target_frame: int
    observation: PairObservation | None
    rejection_reason: str | None = None

    @property
    def pair_name(self) -> str:
        return f"{self.source_frame}->{self.target_frame}"


@dataclass(frozen=True, slots=True)
class CalibrationEstimate:
    calibration: CalibrationContract
    accepted_pairs: tuple[str, ...]
    rejected_pairs: tuple[str, ...]
    center_spread_px: float
    median_pair_residual_px: float


def _expected_target(source_frame: int) -> int:
    return source_frame + 1 if source_frame < FRAME_COUNT else 1


def _rejection_reason(observation: PairObservation) -> str | None:
    if observation.target_frame != _expected_target(observation.source_frame):
        return "not an adjacent acquisition pair"
    if abs(observation.angle_degrees - EXPECTED_ROTATION_DEGREES) > MAX_ANGLE_DEVIATION_DEGREES:
        return "rotation is outside the calibrated 22.5-degree bound"
    if not MIN_SCALE <= observation.scale <= MAX_SCALE:
        return "scale is outside the fixed-camera bound"
    if observation.inlier_count < MIN_INLIER_COUNT:
        return "insufficient robust correspondences"
    if observation.median_residual_px > MAX_MEDIAN_RESIDUAL_PX:
        return "median residual exceeds the calibration threshold"
    return None


def _robust_common_center(
    attempts: Sequence[PairMatchAttempt],
) -> tuple[tuple[float, float], tuple[PairObservation, ...], tuple[str, ...], float]:
    candidates: list[tuple[PairObservation, tuple[float, float]]] = []
    rejected: list[str] = []
    for attempt in attempts:
        observation = attempt.observation
        if observation is None:
            rejected.append(f"{attempt.pair_name}: {attempt.rejection_reason or 'no transform'}")
            continue
        reason = _rejection_reason(observation)
        if reason is not None:
            rejected.append(f"{attempt.pair_name}: {reason}")
            continue
        try:
            candidates.append((observation, observation.rotation_center()))
        except CalibrationFailure as error:
            rejected.append(f"{attempt.pair_name}: {error}")

    if len(candidates) < MIN_ACCEPTED_PAIRS:
        raise CalibrationFailure(
            f"only {len(candidates)} reliable neighbor pairs; "
            f"at least {MIN_ACCEPTED_PAIRS} are required"
        )

    median_x = median(center[0] for _, center in candidates)
    median_y = median(center[1] for _, center in candidates)
    distances = [math.hypot(center[0] - median_x, center[1] - median_y) for _, center in candidates]
    robust_limit = min(
        MAX_CENTER_DEVIATION_PX,
        max(25.0, 3.0 * median(distances)),
    )
    retained: list[tuple[PairObservation, tuple[float, float]]] = []
    for candidate, distance in zip(candidates, distances, strict=True):
        observation, _ = candidate
        if distance <= robust_limit:
            retained.append(candidate)
        else:
            rejected.append(
                f"{observation.source_frame}->{observation.target_frame}: "
                "rotation center is an outlier"
            )
    if len(retained) < MIN_ACCEPTED_PAIRS:
        raise CalibrationFailure("too few neighbor pairs agree on one fixed rotation center")

    final_x = median(center[0] for _, center in retained)
    final_y = median(center[1] for _, center in retained)
    spread = max(math.hypot(center[0] - final_x, center[1] - final_y) for _, center in retained)
    return (
        (final_x, final_y),
        tuple(observation for observation, _ in retained),
        tuple(rejected),
        spread,
    )


def _ray_rectangle_interval(
    center: tuple[float, float],
    roi: RoiRectangle,
    angle_radians: float,
) -> tuple[float, float]:
    direction = (math.cos(angle_radians), math.sin(angle_radians))
    lower, upper = 0.0, math.inf
    for origin, component, minimum, maximum in (
        (center[0], direction[0], float(roi.x), float(roi.x + roi.width)),
        (center[1], direction[1], float(roi.y), float(roi.y + roi.height)),
    ):
        if abs(component) < 1e-12:
            if origin < minimum or origin > maximum:
                raise CalibrationFailure("calibration sector ray does not intersect the source ROI")
            continue
        first = (minimum - origin) / component
        second = (maximum - origin) / component
        lower = max(lower, min(first, second))
        upper = min(upper, max(first, second))
    if upper <= lower or upper <= 0:
        raise CalibrationFailure("calibration sector ray does not intersect the source ROI")
    return lower, upper


def _continuous_radial_band(
    center: tuple[float, float],
    roi: RoiRectangle,
    reference_ray_degrees: float,
) -> tuple[float, float]:
    half_sector = math.radians(22.5 / 2.0)
    reference = math.radians(reference_ray_degrees)
    sample_count = 4097
    intervals = [
        _ray_rectangle_interval(
            center,
            roi,
            reference - half_sector + (2.0 * half_sector * index / (sample_count - 1)),
        )
        for index in range(sample_count)
    ]
    inner = math.ceil(max(item[0] for item in intervals) + 2.0)
    outer = math.floor(min(item[1] for item in intervals) - 2.0)
    if outer <= inner:
        raise CalibrationFailure("source ROI has no continuously covered 22.5-degree radial band")
    return float(inner), float(outer)


def build_calibration(
    *,
    acquisition_id: str,
    side: DiscSide,
    attempts: Sequence[PairMatchAttempt],
    input_width: int,
    input_height: int,
    usable_source_roi: RoiRectangle,
) -> CalibrationEstimate:
    """Build deterministic native-pixel calibration from measured pair evidence."""

    if input_width <= 0 or input_height <= 0:
        raise CalibrationFailure("input dimensions must be positive")
    if len(attempts) != FRAME_COUNT:
        raise CalibrationFailure("calibration requires all 16 neighbor-pair attempts")
    center, accepted, rejected, spread = _robust_common_center(attempts)
    roi_center = (
        usable_source_roi.x + usable_source_roi.width / 2.0,
        usable_source_roi.y + usable_source_roi.height / 2.0,
    )
    reference_ray = (
        math.degrees(math.atan2(roi_center[1] - center[1], roi_center[0] - center[0])) % 360.0
    )
    inner_radius, outer_radius = _continuous_radial_band(
        center,
        usable_source_roi,
        reference_ray,
    )
    output_radius = math.ceil(outer_radius) + 1
    output_center = (float(output_radius), float(output_radius))
    translate_x = output_center[0] - center[0]
    translate_y = output_center[1] - center[1]
    forward = (
        (1.0, 0.0, translate_x),
        (0.0, 1.0, translate_y),
        (0.0, 0.0, 1.0),
    )
    inverse = (
        (1.0, 0.0, -translate_x),
        (0.0, 1.0, -translate_y),
        (0.0, 0.0, 1.0),
    )
    calibration = CalibrationContract(
        acquisition_id=acquisition_id,
        side=side,
        state=CalibrationState.VALIDATED,
        input_width=input_width,
        input_height=input_height,
        output_width=2 * output_radius + 1,
        output_height=2 * output_radius + 1,
        usable_source_roi=usable_source_roi,
        source_disc_center=Point2D(x=center[0], y=center[1]),
        output_disc_center=Point2D(x=output_center[0], y=output_center[1]),
        inner_radius=inner_radius,
        outer_radius=outer_radius,
        reference_ray_degrees=reference_ray,
        source_to_calibrated_matrix=forward,
        calibrated_to_source_matrix=inverse,
    )
    return CalibrationEstimate(
        calibration=calibration,
        accepted_pairs=tuple(
            f"{observation.source_frame}->{observation.target_frame}" for observation in accepted
        ),
        rejected_pairs=rejected,
        center_spread_px=spread,
        median_pair_residual_px=median(observation.median_residual_px for observation in accepted),
    )
