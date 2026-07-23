"""Deterministic nominal placement for ordered circular acquisitions."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from backend.domain.acquisition import AcquisitionManifest
from backend.domain.reconstruction import (
    CalibrationContract,
    CalibrationState,
    FrameTransformContract,
    Matrix3x3,
    RegistrationEvidence,
    RegistrationMethod,
    TransformSetContract,
)
from backend.domain.value_objects import normalize_relative_path


class PlacementFailure(ValueError):
    """Raised when nominal placement violates a geometry contract."""


def _nominal_matrix(
    calibration: CalibrationContract,
    angle_degrees: float,
) -> tuple[Matrix3x3, Matrix3x3]:
    radians = math.radians(angle_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    source_x = calibration.source_disc_center.x
    source_y = calibration.source_disc_center.y
    output_x = calibration.output_disc_center.x
    output_y = calibration.output_disc_center.y
    forward = (
        (cosine, -sine, output_x - cosine * source_x + sine * source_y),
        (sine, cosine, output_y - sine * source_x - cosine * source_y),
        (0.0, 0.0, 1.0),
    )
    inverse = (
        (cosine, sine, source_x - cosine * output_x - sine * output_y),
        (-sine, cosine, source_y + sine * output_x - cosine * output_y),
        (0.0, 0.0, 1.0),
    )
    return forward, inverse


def build_nominal_transform_set(
    manifest: AcquisitionManifest,
    calibration: CalibrationContract,
    *,
    calibration_relative_path: str,
    mask_directory_relative_path: str,
) -> TransformSetContract:
    """Create the complete 16-frame nominal source-to-output transform set."""

    if manifest.acquisition_id != calibration.acquisition_id:
        raise PlacementFailure("manifest and calibration acquisition IDs do not match")
    if manifest.side is not calibration.side:
        raise PlacementFailure("manifest and calibration disc sides do not match")
    if calibration.state is not CalibrationState.VALIDATED:
        raise PlacementFailure("nominal placement requires a validated calibration")
    if manifest.expected_width != calibration.input_width:
        raise PlacementFailure("manifest width does not match calibration input width")
    if manifest.expected_height != calibration.input_height:
        raise PlacementFailure("manifest height does not match calibration input height")

    calibration_path = normalize_relative_path(calibration_relative_path)
    mask_directory = normalize_relative_path(mask_directory_relative_path)
    transforms = []
    for frame in manifest.frames:
        forward, inverse = _nominal_matrix(calibration, frame.angle_degrees)
        transforms.append(
            FrameTransformContract(
                frame_position=frame.position,
                source_sha256=frame.sha256,
                nominal_angle_degrees=frame.angle_degrees,
                source_to_output_matrix=forward,
                output_to_source_matrix=inverse,
                valid_mask_relative_path=(f"{mask_directory}/frame-{frame.position:02d}.tiff"),
                evidence=RegistrationEvidence(
                    method=RegistrationMethod.NOMINAL,
                    confidence=1.0,
                    evidence_count=0,
                ),
            )
        )
    return TransformSetContract(
        acquisition_id=manifest.acquisition_id,
        calibration_relative_path=calibration_path,
        transforms=tuple(transforms),
    )


def map_points(
    matrix: npt.ArrayLike,
    points: npt.ArrayLike,
) -> npt.NDArray[np.float64]:
    """Map an ``N x 2`` point array through a finite homogeneous matrix."""

    values = np.asarray(points, dtype=np.float64)
    transform = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2:
        raise PlacementFailure("points must be an N x 2 array")
    if transform.shape != (3, 3):
        raise PlacementFailure("transform must be a 3 x 3 matrix")
    if not np.isfinite(transform).all() or not np.isfinite(values).all():
        raise PlacementFailure("points and transform values must be finite")
    homogeneous = np.column_stack((values, np.ones(len(values), dtype=np.float64)))
    mapped = homogeneous @ transform.T
    denominator = mapped[:, 2]
    if np.any(np.abs(denominator) < 1e-12):
        raise PlacementFailure("transform maps a point to infinity")
    return mapped[:, :2] / denominator[:, None]


def frame_output_bounds(
    calibration: CalibrationContract,
    transform: FrameTransformContract,
) -> tuple[int, int, int, int]:
    """Return one transformed source ROI's clipped output bounds."""

    roi = calibration.usable_source_roi
    corners = np.asarray(
        (
            (roi.x, roi.y),
            (roi.x + roi.width, roi.y),
            (roi.x + roi.width, roi.y + roi.height),
            (roi.x, roi.y + roi.height),
        ),
        dtype=np.float64,
    )
    mapped = map_points(transform.source_to_output_matrix, corners)
    left = max(0, math.floor(float(mapped[:, 0].min())))
    top = max(0, math.floor(float(mapped[:, 1].min())))
    right = min(calibration.output_width, math.ceil(float(mapped[:, 0].max())) + 1)
    bottom = min(calibration.output_height, math.ceil(float(mapped[:, 1].max())) + 1)
    if right <= left or bottom <= top:
        raise PlacementFailure(f"frame {transform.frame_position} has no output intersection")
    return left, top, right, bottom
