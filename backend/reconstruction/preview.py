"""Bounded atomic preview rendering for reconstruction review workflows."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from backend.core.paths import ApplicationPaths
from backend.reconstruction.rendering import FRAME_COUNT, RenderFrame


class ReconstructionPreviewFailure(RuntimeError):
    """Raised when a reconstruction preview cannot be safely published."""


@dataclass(frozen=True, slots=True)
class ReconstructionPreview:
    relative_path: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    source_canvas_width: int
    source_canvas_height: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canvas_geometry(
    frames: tuple[RenderFrame, ...],
    source_width: int,
    source_height: int,
) -> tuple[npt.NDArray[np.float64], int, int]:
    corners = np.asarray(
        (
            (0.0, 0.0),
            (source_width - 1.0, 0.0),
            (source_width - 1.0, source_height - 1.0),
            (0.0, source_height - 1.0),
        ),
        dtype=np.float64,
    ).reshape(-1, 1, 2)
    transformed = [
        cv2.perspectiveTransform(
            corners,
            np.asarray(frame.source_to_reference_matrix, dtype=np.float64),
        ).reshape(-1, 2)
        for frame in frames
    ]
    all_corners = np.vstack(transformed)
    minimum = np.floor(all_corners.min(axis=0))
    maximum = np.ceil(all_corners.max(axis=0))
    width, height = (maximum - minimum + 1).astype(int)
    if width <= 0 or height <= 0:
        raise ReconstructionPreviewFailure("reconstruction candidate has invalid canvas geometry")
    translation = np.asarray(
        (
            (1.0, 0.0, -minimum[0]),
            (0.0, 1.0, -minimum[1]),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    return translation, int(width), int(height)


def render_reconstruction_preview(
    paths: ApplicationPaths,
    *,
    frames: tuple[RenderFrame, ...],
    source_width: int,
    source_height: int,
    output_relative_path: str,
    maximum_dimension: int = 3200,
    square_size: int | None = None,
) -> ReconstructionPreview:
    """Blend all 16 uncropped frames into a bounded review PNG."""

    if [frame.position for frame in frames] != list(range(1, FRAME_COUNT + 1)):
        raise ReconstructionPreviewFailure("preview requires ordered frames 1 through 16")
    if source_width <= 0 or source_height <= 0:
        raise ReconstructionPreviewFailure("preview source dimensions must be positive")
    if maximum_dimension < 512 or maximum_dimension > 5000:
        raise ReconstructionPreviewFailure("preview maximum dimension is outside the safe range")
    if square_size is not None and (square_size < 512 or square_size > 5000):
        raise ReconstructionPreviewFailure("preview square size is outside the safe range")
    output = paths.resolve_data_path(output_relative_path)
    if output.suffix.casefold() != ".png":
        raise ReconstructionPreviewFailure("reconstruction preview must be a PNG")
    if output.exists():
        raise ReconstructionPreviewFailure("reconstruction preview already exists")

    translation, canvas_width, canvas_height = _canvas_geometry(
        frames,
        source_width,
        source_height,
    )
    selected_dimension = square_size if square_size is not None else maximum_dimension
    scale = min(1.0, selected_dimension / max(canvas_width, canvas_height))
    fitted_width = max(1, int(round(canvas_width * scale)))
    fitted_height = max(1, int(round(canvas_height * scale)))
    preview_width = square_size if square_size is not None else fitted_width
    preview_height = square_size if square_size is not None else fitted_height
    offset_x = (preview_width - fitted_width) / 2.0
    offset_y = (preview_height - fitted_height) / 2.0
    scale_matrix = np.asarray(
        (
            (scale, 0.0, offset_x),
            (0.0, scale, offset_y),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    accumulator = np.zeros((preview_height, preview_width, 3), dtype=np.float32)
    total_weight = np.zeros((preview_height, preview_width), dtype=np.float32)
    y_distance = np.minimum(
        np.arange(source_height) + 1,
        source_height - np.arange(source_height),
    )[:, None]
    x_distance = np.minimum(
        np.arange(source_width) + 1,
        source_width - np.arange(source_width),
    )[None, :]
    edge_extent = max(8, int(round(min(source_width, source_height) * 0.08)))
    source_weight = np.minimum(np.minimum(y_distance, x_distance), edge_extent).astype(np.float32)

    for frame in frames:
        source = paths.resolve_data_path(frame.source_relative_path)
        if not source.is_file() or source.is_symlink():
            raise ReconstructionPreviewFailure(f"preview source frame {frame.position} is missing")
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (source_height, source_width):
            raise ReconstructionPreviewFailure(
                f"preview source frame {frame.position} has invalid geometry"
            )
        transform = (
            scale_matrix
            @ translation
            @ np.asarray(frame.source_to_reference_matrix, dtype=np.float64)
        )
        warped = cv2.warpPerspective(
            image,
            transform,
            (preview_width, preview_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        weight = cv2.warpPerspective(
            source_weight,
            transform,
            (preview_width, preview_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        warped_rgb = np.asarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB), dtype=np.float32)
        weight_values = np.asarray(weight, dtype=np.float32)
        accumulator += warped_rgb * weight_values[..., None]
        total_weight += weight_values

    preview = np.zeros((preview_height, preview_width, 3), dtype=np.uint8)
    covered = total_weight > 0
    preview[covered] = np.clip(
        accumulator[covered] / total_weight[covered, None],
        0,
        255,
    ).astype(np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{output.stem}-{uuid.uuid4().hex}.tmp.png")
    try:
        encoded = cv2.cvtColor(preview, cv2.COLOR_RGB2BGR)
        if not cv2.imwrite(str(staging), encoded, (cv2.IMWRITE_PNG_COMPRESSION, 3)):
            raise ReconstructionPreviewFailure("OpenCV could not encode reconstruction preview")
        with staging.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ReconstructionPreviewFailure("encoded reconstruction preview is invalid")
        os.replace(staging, output)
    finally:
        staging.unlink(missing_ok=True)
    return ReconstructionPreview(
        relative_path=paths.to_data_relative_path(output),
        sha256=_sha256(output),
        size_bytes=output.stat().st_size,
        width=preview_width,
        height=preview_height,
        source_canvas_width=canvas_width,
        source_canvas_height=canvas_height,
    )
