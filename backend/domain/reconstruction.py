"""Strict contracts for calibrated 16-frame circular reconstruction."""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Literal, cast

from pydantic import Field, field_validator, model_validator

from backend.domain.contracts import ContractModel, DiscSide
from backend.domain.value_objects import ContractIdentifier, SafeRelativePath, Sha256Hex

FRAME_COUNT = 16
ANGLE_STEP_DEGREES = 22.5
MAX_FINE_ANGLE_CORRECTION_DEGREES = 2.0

Matrix3x3 = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


def _validate_matrix(value: Matrix3x3) -> Matrix3x3:
    if not all(math.isfinite(number) for row in value for number in row):
        raise ValueError("matrix values must be finite")
    return value


def _multiply(left: Matrix3x3, right: Matrix3x3) -> Matrix3x3:
    result = tuple(
        tuple(
            sum(left[row][index] * right[index][column] for index in range(3))
            for column in range(3)
        )
        for row in range(3)
    )
    return cast(Matrix3x3, result)


def _require_inverse(forward: Matrix3x3, inverse: Matrix3x3) -> None:
    product = _multiply(forward, inverse)
    for row in range(3):
        for column in range(3):
            expected = 1.0 if row == column else 0.0
            if not math.isclose(product[row][column], expected, abs_tol=1e-6):
                raise ValueError("forward and inverse matrices are inconsistent")


class CalibrationState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"


class RegistrationMethod(str, Enum):
    NOMINAL = "nominal"
    TEXTURE = "texture"
    HOLE_AND_TEXTURE = "hole_and_texture"
    FIXED_MODEL = "fixed_model"


class Point2D(ContractModel):
    x: float
    y: float

    @model_validator(mode="after")
    def validate_finite(self) -> Point2D:
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise ValueError("point coordinates must be finite")
        return self


class RoiRectangle(ContractModel):
    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]


class CalibrationContract(ContractModel):
    schema_version: Literal[1] = 1
    acquisition_id: ContractIdentifier
    side: DiscSide
    state: CalibrationState
    input_width: Annotated[int, Field(gt=0)]
    input_height: Annotated[int, Field(gt=0)]
    output_width: Annotated[int, Field(gt=0)]
    output_height: Annotated[int, Field(gt=0)]
    usable_source_roi: RoiRectangle
    source_disc_center: Point2D
    output_disc_center: Point2D
    inner_radius: Annotated[float, Field(ge=0)]
    outer_radius: Annotated[float, Field(gt=0)]
    reference_ray_degrees: Annotated[float, Field(ge=0, lt=360)]
    pixels_per_mm: Annotated[float, Field(gt=0)] | None = None
    source_to_calibrated_matrix: Matrix3x3
    calibrated_to_source_matrix: Matrix3x3

    _forward = field_validator("source_to_calibrated_matrix")(_validate_matrix)
    _inverse = field_validator("calibrated_to_source_matrix")(_validate_matrix)

    @model_validator(mode="after")
    def validate_geometry(self) -> CalibrationContract:
        roi = self.usable_source_roi
        if roi.x + roi.width > self.input_width or roi.y + roi.height > self.input_height:
            raise ValueError("usable source ROI must stay inside the source image")
        if self.inner_radius >= self.outer_radius:
            raise ValueError("inner radius must be smaller than outer radius")
        _require_inverse(self.source_to_calibrated_matrix, self.calibrated_to_source_matrix)
        return self


class RegistrationEvidence(ContractModel):
    method: RegistrationMethod
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence_count: Annotated[int, Field(ge=0)]
    median_residual_px: Annotated[float, Field(ge=0)] | None = None
    overlap_percent: Annotated[float, Field(ge=0, le=100)] = 0.0


class FrameTransformContract(ContractModel):
    frame_position: Annotated[int, Field(ge=1, le=FRAME_COUNT)]
    source_sha256: Sha256Hex
    nominal_angle_degrees: Annotated[float, Field(ge=0, lt=360)]
    fine_angle_correction_degrees: Annotated[
        float,
        Field(
            ge=-MAX_FINE_ANGLE_CORRECTION_DEGREES,
            le=MAX_FINE_ANGLE_CORRECTION_DEGREES,
        ),
    ] = 0.0
    source_to_output_matrix: Matrix3x3
    output_to_source_matrix: Matrix3x3
    valid_mask_relative_path: SafeRelativePath
    evidence: RegistrationEvidence

    _forward = field_validator("source_to_output_matrix")(_validate_matrix)
    _inverse = field_validator("output_to_source_matrix")(_validate_matrix)

    @model_validator(mode="after")
    def validate_transform(self) -> FrameTransformContract:
        expected = (self.frame_position - 1) * ANGLE_STEP_DEGREES
        if not math.isclose(self.nominal_angle_degrees, expected, abs_tol=1e-9):
            raise ValueError("transform angle does not match its frame position")
        _require_inverse(self.source_to_output_matrix, self.output_to_source_matrix)
        return self


class TransformSetContract(ContractModel):
    schema_version: Literal[1] = 1
    acquisition_id: ContractIdentifier
    calibration_relative_path: SafeRelativePath
    transforms: tuple[FrameTransformContract, ...]

    @model_validator(mode="after")
    def validate_complete_set(self) -> TransformSetContract:
        if [item.frame_position for item in self.transforms] != list(range(1, FRAME_COUNT + 1)):
            raise ValueError(
                "transform set must contain positions 1 through 16 exactly once in order"
            )
        if len({item.source_sha256 for item in self.transforms}) != FRAME_COUNT:
            raise ValueError("transform source hashes must be unique")
        if len({item.valid_mask_relative_path for item in self.transforms}) != FRAME_COUNT:
            raise ValueError("transform mask paths must be unique")
        return self
