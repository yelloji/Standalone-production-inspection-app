"""Bounded global fine registration with explicit loop-closure failure."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt

from backend.domain.reconstruction import (
    CalibrationContract,
    Matrix3x3,
    RegistrationEvidence,
    RegistrationMethod,
    TransformSetContract,
)
from backend.reconstruction.calibration import PairMatchAttempt, PairObservation

FRAME_COUNT = 16
NOMINAL_STEP_DEGREES = 22.5
MAX_PAIR_ANGLE_DEVIATION_DEGREES = 2.0
MIN_SCALE = 0.995
MAX_SCALE = 1.005
MIN_INLIERS = 5
MAX_FEATURE_RESIDUAL_PX = 4.0
MAX_CENTER_DEVIATION_PX = 150.0
MAX_FRAME_CORRECTION_DEGREES = 2.0
MAX_LOOP_RESIDUAL_PX = 4.0
MIN_CONFIDENCE = 0.35


@dataclass(frozen=True, slots=True)
class PairRegistrationResult:
    source_frame: int
    target_frame: int
    is_loop_closure: bool
    passed: bool
    measured_step_degrees: float | None
    step_correction_degrees: float | None
    scale: float | None
    evidence_count: int
    median_residual_px: float | None
    center_deviation_px: float | None
    confidence: float
    reason: str | None


@dataclass(frozen=True, slots=True)
class FineRegistrationResult:
    passed: bool
    pair_results: tuple[PairRegistrationResult, ...]
    frame_corrections_degrees: tuple[float, ...]
    corrected_transforms: TransformSetContract | None
    maximum_frame_correction_degrees: float | None
    maximum_loop_residual_px: float | None
    failure_reasons: tuple[str, ...]


def _expected_target(source_frame: int) -> int:
    return source_frame + 1 if source_frame < FRAME_COUNT else 1


def _failure(
    attempt: PairMatchAttempt,
    reason: str,
    observation: PairObservation | None = None,
    center_deviation: float | None = None,
) -> PairRegistrationResult:
    return PairRegistrationResult(
        source_frame=attempt.source_frame,
        target_frame=attempt.target_frame,
        is_loop_closure=attempt.source_frame == FRAME_COUNT,
        passed=False,
        measured_step_degrees=(-observation.angle_degrees if observation is not None else None),
        step_correction_degrees=None,
        scale=observation.scale if observation is not None else None,
        evidence_count=observation.inlier_count if observation is not None else 0,
        median_residual_px=(observation.median_residual_px if observation is not None else None),
        center_deviation_px=center_deviation,
        confidence=0.0,
        reason=reason,
    )


def _confidence(observation: PairObservation, angle_deviation: float) -> float:
    inlier_score = min(1.0, observation.inlier_count / 30.0)
    residual_score = max(0.0, 1.0 - observation.median_residual_px / MAX_FEATURE_RESIDUAL_PX)
    angle_score = max(0.0, 1.0 - angle_deviation / MAX_PAIR_ANGLE_DEVIATION_DEGREES)
    return 0.45 * inlier_score + 0.35 * residual_score + 0.20 * angle_score


def assess_pair_attempts(
    attempts: tuple[PairMatchAttempt, ...] | list[PairMatchAttempt],
    calibration: CalibrationContract,
) -> tuple[PairRegistrationResult, ...]:
    """Validate every measured neighbor edge without inventing weak evidence."""

    if len(attempts) != FRAME_COUNT:
        raise ValueError("fine registration requires exactly 16 neighbor attempts")
    results: list[PairRegistrationResult] = []
    for position, attempt in enumerate(attempts, start=1):
        expected_target = _expected_target(position)
        if attempt.source_frame != position or attempt.target_frame != expected_target:
            results.append(
                _failure(attempt, "pair order does not match the 16-frame acquisition cycle")
            )
            continue
        observation = attempt.observation
        if observation is None:
            results.append(
                _failure(attempt, attempt.rejection_reason or "no registration evidence")
            )
            continue
        if (
            observation.source_frame != attempt.source_frame
            or observation.target_frame != attempt.target_frame
        ):
            results.append(
                _failure(attempt, "observation pair does not match its attempt", observation)
            )
            continue

        measured_step = -observation.angle_degrees
        angle_deviation = abs(measured_step - NOMINAL_STEP_DEGREES)
        try:
            pair_center = observation.rotation_center()
            center_deviation = math.hypot(
                pair_center[0] - calibration.source_disc_center.x,
                pair_center[1] - calibration.source_disc_center.y,
            )
        except ValueError as error:
            results.append(_failure(attempt, str(error), observation))
            continue

        reason: str | None = None
        if angle_deviation > MAX_PAIR_ANGLE_DEVIATION_DEGREES:
            reason = "pair angle correction exceeds +/-2 degrees"
        elif not MIN_SCALE <= observation.scale <= MAX_SCALE:
            reason = "pair scale violates the fixed-camera bound"
        elif observation.inlier_count < MIN_INLIERS:
            reason = "fewer than five robust correspondences"
        elif observation.median_residual_px > MAX_FEATURE_RESIDUAL_PX:
            reason = "feature residual exceeds 4 pixels"
        elif center_deviation > MAX_CENTER_DEVIATION_PX:
            reason = "pair rotation center disagrees with fixed calibration"
        confidence = _confidence(observation, angle_deviation)
        if reason is None and confidence < MIN_CONFIDENCE:
            reason = "registration confidence is below 0.35"
        if reason is not None:
            results.append(_failure(attempt, reason, observation, center_deviation))
            continue

        results.append(
            PairRegistrationResult(
                source_frame=position,
                target_frame=expected_target,
                is_loop_closure=position == FRAME_COUNT,
                passed=True,
                measured_step_degrees=measured_step,
                step_correction_degrees=measured_step - NOMINAL_STEP_DEGREES,
                scale=observation.scale,
                evidence_count=observation.inlier_count,
                median_residual_px=observation.median_residual_px,
                center_deviation_px=center_deviation,
                confidence=confidence,
                reason=None,
            )
        )
    return tuple(results)


def _solve_global_corrections(
    pair_results: tuple[PairRegistrationResult, ...],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    rows: list[npt.NDArray[np.float64]] = []
    targets: list[float] = []
    weights: list[float] = []
    for result in pair_results:
        if result.step_correction_degrees is None:
            raise ValueError("cannot solve a registration graph with missing corrections")
        row = np.zeros(FRAME_COUNT, dtype=np.float64)
        row[result.target_frame - 1] = 1.0
        row[result.source_frame - 1] -= 1.0
        rows.append(row)
        targets.append(result.step_correction_degrees)
        weights.append(max(result.confidence, 1e-6))
    anchor = np.zeros(FRAME_COUNT, dtype=np.float64)
    anchor[0] = 1.0
    rows.append(anchor)
    targets.append(0.0)
    weights.append(1000.0)
    matrix = np.asarray(rows)
    target = np.asarray(targets)
    root_weights = np.sqrt(np.asarray(weights))
    corrections = np.linalg.lstsq(
        matrix * root_weights[:, None],
        target * root_weights,
        rcond=None,
    )[0]
    residuals = np.asarray(
        [
            corrections[result.target_frame - 1]
            - corrections[result.source_frame - 1]
            - cast(float, result.step_correction_degrees)
            for result in pair_results
        ]
    )
    return corrections, residuals


def _output_rotation(
    calibration: CalibrationContract,
    angle_degrees: float,
) -> Matrix3x3:
    radians = math.radians(angle_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    center_x = calibration.output_disc_center.x
    center_y = calibration.output_disc_center.y
    return (
        (cosine, -sine, center_x - cosine * center_x + sine * center_y),
        (sine, cosine, center_y - sine * center_x - cosine * center_y),
        (0.0, 0.0, 1.0),
    )


def _matrix_multiply(left: Matrix3x3, right: Matrix3x3) -> Matrix3x3:
    result = np.asarray(left, dtype=np.float64) @ np.asarray(right, dtype=np.float64)
    return cast(
        Matrix3x3,
        tuple(tuple(float(value) for value in row) for row in result),
    )


def refine_nominal_transforms(
    nominal: TransformSetContract,
    calibration: CalibrationContract,
    attempts: tuple[PairMatchAttempt, ...] | list[PairMatchAttempt],
) -> FineRegistrationResult:
    """Solve one globally closed correction graph or return an explicit failure."""

    if nominal.acquisition_id != calibration.acquisition_id:
        raise ValueError("nominal transforms and calibration acquisition IDs do not match")
    pair_results = assess_pair_attempts(attempts, calibration)
    failures = [
        f"{item.source_frame}->{item.target_frame}: {item.reason}"
        for item in pair_results
        if not item.passed
    ]
    if failures:
        return FineRegistrationResult(False, pair_results, (), None, None, None, tuple(failures))

    corrections, edge_residuals_degrees = _solve_global_corrections(pair_results)
    maximum_correction = float(np.max(np.abs(corrections)))
    residuals_px = np.abs(np.radians(edge_residuals_degrees)) * calibration.outer_radius
    maximum_loop_residual = float(np.max(residuals_px))
    if maximum_correction > MAX_FRAME_CORRECTION_DEGREES:
        failures.append(
            f"global solution requires {maximum_correction:.6f} degrees; "
            f"limit is {MAX_FRAME_CORRECTION_DEGREES:.1f}"
        )
    if maximum_loop_residual > MAX_LOOP_RESIDUAL_PX:
        failures.append(
            f"global loop residual reaches {maximum_loop_residual:.6f} pixels; "
            f"limit is {MAX_LOOP_RESIDUAL_PX:.1f}"
        )
    correction_values = tuple(float(value) for value in corrections)
    if failures:
        return FineRegistrationResult(
            False,
            pair_results,
            correction_values,
            None,
            maximum_correction,
            maximum_loop_residual,
            tuple(failures),
        )

    incoming = {item.target_frame: item for item in pair_results}
    corrected = []
    for transform, correction in zip(nominal.transforms, corrections, strict=True):
        evidence = incoming[transform.frame_position]
        correction_matrix = _output_rotation(calibration, float(correction))
        inverse_correction = _output_rotation(calibration, float(-correction))
        data = transform.model_dump(mode="python")
        data.update(
            {
                "fine_angle_correction_degrees": float(correction),
                "source_to_output_matrix": _matrix_multiply(
                    correction_matrix,
                    transform.source_to_output_matrix,
                ),
                "output_to_source_matrix": _matrix_multiply(
                    transform.output_to_source_matrix,
                    inverse_correction,
                ),
                "evidence": RegistrationEvidence(
                    method=RegistrationMethod.TEXTURE,
                    confidence=evidence.confidence,
                    evidence_count=evidence.evidence_count,
                    median_residual_px=evidence.median_residual_px,
                ),
            }
        )
        corrected.append(type(transform).model_validate(data))
    transform_set_data = nominal.model_dump(mode="python")
    transform_set_data["transforms"] = tuple(corrected)
    corrected_set = TransformSetContract.model_validate(transform_set_data)
    return FineRegistrationResult(
        True,
        pair_results,
        correction_values,
        corrected_set,
        maximum_correction,
        maximum_loop_residual,
        (),
    )
