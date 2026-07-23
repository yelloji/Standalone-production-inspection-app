"""Versioned immutable manifest for an ordered offline acquisition."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from backend.domain.contracts import DiscSide
from backend.domain.value_objects import ContractIdentifier, SafeRelativePath, Sha256Hex


class AcquisitionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AcquisitionFrameManifest(AcquisitionSchema):
    position: Annotated[int, Field(ge=1, le=16)]
    angle_degrees: Annotated[float, Field(ge=0, lt=360)]
    original_relative_path: SafeRelativePath
    owned_relative_path: SafeRelativePath
    image_format: Literal["JPEG", "PNG", "TIFF"]
    pixel_mode: Literal["L", "RGB", "RGBA", "I;16", "I;16L", "I;16B"]
    width: Annotated[int, Field(ge=1)]
    height: Annotated[int, Field(ge=1)]
    size_bytes: Annotated[int, Field(gt=0)]
    sha256: Sha256Hex


class AcquisitionManifest(AcquisitionSchema):
    schema_version: Literal[1] = 1
    acquisition_id: ContractIdentifier
    side: DiscSide
    created_at: AwareDatetime
    frame_count: Literal[16] = 16
    degrees_per_frame: float = 22.5
    expected_width: Annotated[int, Field(ge=1)]
    expected_height: Annotated[int, Field(ge=1)]
    frames: tuple[AcquisitionFrameManifest, ...]

    @model_validator(mode="after")
    def validate_sequence(self) -> AcquisitionManifest:
        if self.side not in {DiscSide.UPPER, DiscSide.LOWER}:
            raise ValueError("brake-disc acquisition side must be upper or lower")
        if self.degrees_per_frame != 22.5:
            raise ValueError("brake-disc acquisition step must be 22.5 degrees")
        if len(self.frames) != 16:
            raise ValueError("acquisition manifest requires exactly 16 frames")
        if [frame.position for frame in self.frames] != list(range(1, 17)):
            raise ValueError("frame positions must be ordered from 1 through 16")
        expected_angles = [(position - 1) * 22.5 for position in range(1, 17)]
        if [frame.angle_degrees for frame in self.frames] != expected_angles:
            raise ValueError("frame angles must follow the explicit 22.5-degree sequence")
        if len({frame.sha256 for frame in self.frames}) != 16:
            raise ValueError("acquisition frames must have unique content")
        return self


class FinalizedAcquisition(AcquisitionSchema):
    manifest: AcquisitionManifest
    manifest_relative_path: SafeRelativePath
    manifest_sha256: Sha256Hex
