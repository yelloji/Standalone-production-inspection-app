"""Pure geometry for upper plate and lower cyclic screen center completion."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

import numpy as np
import numpy.typing as npt
from scipy import signal

from backend.domain.center_completion import (
    CenterCompletionProfile,
    CenterStrategy,
)
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import Point2D

Affine2x3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
]


class CenterCompletionFailure(ValueError):
    """Raised when center placement evidence cannot support a safe plan."""


@dataclass(frozen=True, slots=True)
class AngularCorrespondence:
    source_angle_degrees: float
    target_angle_degrees: float
    residual_degrees: float


@dataclass(frozen=True, slots=True)
class FlashDetectionResult:
    angles_degrees: tuple[float, ...]
    peak_scores: tuple[float, ...]
    peak_prominences: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CenterCompletionPlan:
    profile_id: str
    side: DiscSide
    strategy: CenterStrategy
    rotation_degrees: float
    scale: float
    source_to_output_affine: Affine2x3
    target_center: Point2D
    target_radius_px: float
    marker_base_rotation_degrees: float
    cyclic_shift: int | None
    median_absolute_angular_residual_degrees: float | None
    maximum_absolute_angular_residual_degrees: float | None
    correspondences: tuple[AngularCorrespondence, ...]
    preserve_acquired_pixels: bool
    reference_pixels_inference_eligible: bool
    allow_approved_screen_replacement: bool


def _normalize_angle(angle: float) -> float:
    return angle % 360.0


def _circular_difference(left: float, right: float) -> float:
    return (left - right + 180.0) % 360.0 - 180.0


def _marker_base_rotation(
    profile: CenterCompletionProfile,
    image_one_start_ray_degrees: float,
) -> float:
    asset = profile.asset
    marker_angle = math.degrees(
        math.atan2(
            asset.marker_center.y - asset.source_center.y,
            asset.marker_center.x - asset.source_center.x,
        )
    )
    return _circular_difference(image_one_start_ray_degrees, marker_angle)


def _affine(
    profile: CenterCompletionProfile,
    target_center: Point2D,
    target_radius_px: float,
    rotation_degrees: float,
) -> tuple[Affine2x3, float]:
    if not math.isfinite(target_radius_px) or target_radius_px <= 0:
        raise CenterCompletionFailure("target opening radius must be finite and positive")
    asset = profile.asset
    scale = target_radius_px / asset.source_radius_px
    radians = math.radians(rotation_degrees)
    cosine = math.cos(radians) * scale
    sine = math.sin(radians) * scale
    translate_x = target_center.x - cosine * asset.source_center.x + sine * asset.source_center.y
    translate_y = target_center.y - sine * asset.source_center.x - cosine * asset.source_center.y
    matrix = (
        (cosine, -sine, translate_x),
        (sine, cosine, translate_y),
    )
    return matrix, scale


def plan_upper_center_completion(
    profile: CenterCompletionProfile,
    *,
    image_one_start_ray_degrees: float,
    target_center: Point2D,
    target_opening_radius_px: float,
) -> CenterCompletionPlan:
    """Align the upper black plate marker to the image-1 start ray."""

    if profile.side is not DiscSide.UPPER:
        raise CenterCompletionFailure("upper planning requires an upper profile")
    rotation = _marker_base_rotation(profile, image_one_start_ray_degrees)
    affine, scale = _affine(
        profile,
        target_center,
        target_opening_radius_px,
        rotation,
    )
    return CenterCompletionPlan(
        profile_id=profile.profile_id,
        side=profile.side,
        strategy=profile.strategy,
        rotation_degrees=rotation,
        scale=scale,
        source_to_output_affine=affine,
        target_center=target_center,
        target_radius_px=target_opening_radius_px,
        marker_base_rotation_degrees=rotation,
        cyclic_shift=None,
        median_absolute_angular_residual_degrees=None,
        maximum_absolute_angular_residual_degrees=None,
        correspondences=(),
        preserve_acquired_pixels=profile.preserve_acquired_pixels,
        reference_pixels_inference_eligible=profile.reference_pixels_inference_eligible,
        allow_approved_screen_replacement=profile.allow_approved_screen_replacement,
    )


def _validated_angles(
    values: tuple[float, ...] | list[float],
    expected_count: int,
    name: str,
) -> tuple[float, ...]:
    if len(values) != expected_count:
        raise CenterCompletionFailure(f"{name} requires exactly {expected_count} angles")
    normalized = tuple(_normalize_angle(float(value)) for value in values)
    if not all(math.isfinite(value) for value in normalized):
        raise CenterCompletionFailure(f"{name} angles must be finite")
    rounded = {round(value, 9) for value in normalized}
    if len(rounded) != expected_count:
        raise CenterCompletionFailure(f"{name} angles must be unique")
    return tuple(sorted(normalized))


def detect_flash_angles(
    angular_scores: npt.ArrayLike,
    *,
    expected_count: int = 10,
    smoothing_width_degrees: int = 11,
    minimum_peak_distance_degrees: int = 15,
    minimum_prominence: float = 2.0,
) -> FlashDetectionResult:
    """Detect circular flash peaks from a 360-bin acquired-pixel score profile."""

    scores = np.asarray(angular_scores, dtype=np.float64)
    if scores.shape != (360,) or not np.isfinite(scores).all():
        raise CenterCompletionFailure(
            "flash detection requires exactly 360 finite angular score bins"
        )
    if expected_count < 1 or expected_count > 360:
        raise CenterCompletionFailure("expected flash count is outside the safe range")
    if (
        smoothing_width_degrees < 1
        or smoothing_width_degrees > 31
        or smoothing_width_degrees % 2 == 0
    ):
        raise CenterCompletionFailure("flash smoothing width must be an odd value from 1 to 31")
    if minimum_peak_distance_degrees < 1 or minimum_prominence <= 0:
        raise CenterCompletionFailure("flash peak thresholds must be positive")

    half_width = smoothing_width_degrees // 2
    padded = np.concatenate((scores[-half_width:], scores, scores[:half_width]))
    kernel = np.ones(smoothing_width_degrees, dtype=np.float64) / smoothing_width_degrees
    smoothed = np.convolve(padded, kernel, mode="valid")
    tripled = np.tile(smoothed, 3)
    peaks, properties = signal.find_peaks(
        tripled,
        distance=minimum_peak_distance_degrees,
        prominence=minimum_prominence,
    )
    central = (peaks >= 360) & (peaks < 720)
    central_peaks = peaks[central] - 360
    prominences = np.asarray(properties["prominences"], dtype=np.float64)[central]
    if len(central_peaks) < expected_count:
        raise CenterCompletionFailure(
            f"flash detector found {len(central_peaks)} peaks; expected {expected_count}"
        )
    ranking = sorted(
        range(len(central_peaks)),
        key=lambda index: (
            -prominences[index],
            -smoothed[central_peaks[index]],
            int(central_peaks[index]),
        ),
    )[:expected_count]
    selected = sorted(ranking, key=lambda index: int(central_peaks[index]))
    return FlashDetectionResult(
        angles_degrees=tuple(float(central_peaks[index]) for index in selected),
        peak_scores=tuple(float(smoothed[central_peaks[index]]) for index in selected),
        peak_prominences=tuple(float(prominences[index]) for index in selected),
    )


def plan_lower_center_completion(
    profile: CenterCompletionProfile,
    *,
    image_one_start_ray_degrees: float,
    detected_flash_angles_degrees: tuple[float, ...] | list[float],
    target_center: Point2D,
    target_opening_radius_px: float,
) -> CenterCompletionPlan:
    """Solve cyclic screen/flash correspondence and one shared assembly rotation."""

    if profile.side is not DiscSide.LOWER:
        raise CenterCompletionFailure("lower planning requires a lower profile")
    source_angles = _validated_angles(
        list(profile.asset.source_screen_angles_degrees),
        10,
        "source screen evidence",
    )
    target_angles = _validated_angles(
        detected_flash_angles_degrees,
        10,
        "detected flash evidence",
    )
    coarse_rotation = _marker_base_rotation(profile, image_one_start_ray_degrees)
    candidates: list[tuple[float, float, int, float, tuple[float, ...], tuple[float, ...]]] = []
    for cyclic_shift in range(10):
        shifted_target = target_angles[cyclic_shift:] + target_angles[:cyclic_shift]
        differences = tuple(
            _circular_difference(target, source)
            for source, target in zip(source_angles, shifted_target, strict=True)
        )
        raw_rotation = median(differences)
        symmetry_period = 360.0 / len(source_angles)
        symmetry_steps = round((coarse_rotation - raw_rotation) / symmetry_period)
        rotation = _normalize_angle(raw_rotation + symmetry_steps * symmetry_period)
        residuals = tuple(
            _circular_difference(source + raw_rotation, target)
            for source, target in zip(source_angles, shifted_target, strict=True)
        )
        score = median(abs(value) for value in residuals)
        maximum = max(abs(value) for value in residuals)
        candidates.append((score, maximum, cyclic_shift, rotation, residuals, shifted_target))
    score, maximum, shift, rotation, residuals, shifted_target = min(
        candidates,
        key=lambda item: (
            item[0],
            item[1],
            abs(_circular_difference(item[3], coarse_rotation)),
            item[2],
        ),
    )
    if score > profile.maximum_median_angular_residual_degrees:
        raise CenterCompletionFailure(
            "screen/flash median angular residual exceeds the profile limit"
        )
    if maximum > profile.maximum_angular_residual_degrees:
        raise CenterCompletionFailure(
            "screen/flash maximum angular residual exceeds the profile limit"
        )
    affine, scale = _affine(
        profile,
        target_center,
        target_opening_radius_px,
        rotation,
    )
    correspondences = tuple(
        AngularCorrespondence(
            source_angle_degrees=source,
            target_angle_degrees=target,
            residual_degrees=residual,
        )
        for source, target, residual in zip(
            source_angles,
            shifted_target,
            residuals,
            strict=True,
        )
    )
    return CenterCompletionPlan(
        profile_id=profile.profile_id,
        side=profile.side,
        strategy=profile.strategy,
        rotation_degrees=float(rotation),
        scale=scale,
        source_to_output_affine=affine,
        target_center=target_center,
        target_radius_px=target_opening_radius_px,
        marker_base_rotation_degrees=coarse_rotation,
        cyclic_shift=shift,
        median_absolute_angular_residual_degrees=float(score),
        maximum_absolute_angular_residual_degrees=float(maximum),
        correspondences=correspondences,
        preserve_acquired_pixels=profile.preserve_acquired_pixels,
        reference_pixels_inference_eligible=profile.reference_pixels_inference_eligible,
        allow_approved_screen_replacement=profile.allow_approved_screen_replacement,
    )
