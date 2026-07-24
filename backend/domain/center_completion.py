"""Versioned contracts for side-specific reconstruction center completion."""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from backend.domain.contracts import ContractModel, DiscSide
from backend.domain.reconstruction import Point2D
from backend.domain.value_objects import ContractIdentifier, SafeRelativePath, Sha256Hex


class CenterStrategy(str, Enum):
    UPPER_BLACK_PLATE = "upper_black_plate"
    LOWER_COMPLETE_ASSEMBLY = "lower_complete_assembly"


class PixelProvenance(IntEnum):
    NO_DATA = 0
    ACQUIRED = 1
    REFERENCE_FILL = 2
    APPROVED_SCREEN_REPLACEMENT = 3


class CenterAssetContract(ContractModel):
    schema_version: Literal[1] = 1
    asset_id: ContractIdentifier
    relative_path: SafeRelativePath
    sha256: Sha256Hex
    source_center: Point2D
    source_radius_px: Annotated[float, Field(gt=0)]
    marker_center: Point2D
    black_plate_only: bool
    includes_silver_screens: bool
    source_screen_angles_degrees: tuple[Annotated[float, Field(ge=0, lt=360)], ...] = ()

    @model_validator(mode="after")
    def validate_asset_components(self) -> CenterAssetContract:
        if self.black_plate_only:
            if self.includes_silver_screens or self.source_screen_angles_degrees:
                raise ValueError("black-plate-only asset cannot include silver screens")
        else:
            if not self.includes_silver_screens:
                raise ValueError("complete center assembly must include silver screens")
            if len(self.source_screen_angles_degrees) != 10:
                raise ValueError("lower center assembly requires exactly ten screen angles")
            if len(set(self.source_screen_angles_degrees)) != 10:
                raise ValueError("lower screen angles must be unique")
        return self


class CenterCompletionProfile(ContractModel):
    schema_version: Literal[1] = 1
    profile_id: ContractIdentifier
    side: DiscSide
    strategy: CenterStrategy
    asset: CenterAssetContract
    maximum_median_angular_residual_degrees: Annotated[float, Field(gt=0, le=180)] = 3.0
    maximum_angular_residual_degrees: Annotated[float, Field(gt=0, le=180)] = 8.0
    preserve_acquired_pixels: Literal[True] = True
    reference_pixels_inference_eligible: Literal[False] = False
    allow_approved_screen_replacement: bool = False
    commissioned_rotation_offset_degrees: (
        Annotated[
            float,
            Field(ge=-180, le=180),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_side_strategy(self) -> CenterCompletionProfile:
        if self.side is DiscSide.UPPER:
            if self.strategy is not CenterStrategy.UPPER_BLACK_PLATE:
                raise ValueError("upper profile requires the black-plate strategy")
            if not self.asset.black_plate_only:
                raise ValueError("upper profile requires a black-plate-only asset")
            if self.allow_approved_screen_replacement:
                raise ValueError("upper profile cannot replace acquired screen pixels")
            if self.commissioned_rotation_offset_degrees is not None:
                raise ValueError("upper profile cannot define a lower rotation offset")
        elif self.side is DiscSide.LOWER:
            if self.strategy is not CenterStrategy.LOWER_COMPLETE_ASSEMBLY:
                raise ValueError("lower profile requires the complete-assembly strategy")
            if self.asset.black_plate_only or not self.asset.includes_silver_screens:
                raise ValueError("lower profile requires the complete assembly and screens")
        else:
            raise ValueError("center completion profile side must be upper or lower")
        if self.maximum_median_angular_residual_degrees > self.maximum_angular_residual_degrees:
            raise ValueError("median angular limit cannot exceed the maximum limit")
        return self
