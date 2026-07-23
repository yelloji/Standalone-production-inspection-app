"""Bounded tiled reconstruction rendering and atomic artifact publication."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt
import tifffile
from PIL import Image

from backend.core.paths import ApplicationPaths
from backend.domain.center_completion import PixelProvenance
from backend.domain.reconstruction import Matrix3x3
from backend.domain.value_objects import normalize_relative_path
from backend.reconstruction.placement import map_points

FRAME_COUNT = 16
MAX_TILE_PIXELS = 1_048_576
UInt8MemMap = np.memmap[tuple[int, ...], np.dtype[np.uint8]]


class ReconstructionRenderFailure(RuntimeError):
    """Raised when rendering cannot safely publish a complete artifact set."""


class ReconstructionRenderCancelled(ReconstructionRenderFailure):
    """Raised after a caller cancellation request and staging cleanup."""


@dataclass(frozen=True, slots=True)
class RenderFrame:
    position: int
    source_relative_path: str
    source_sha256: str
    source_to_reference_matrix: Matrix3x3

    def __post_init__(self) -> None:
        normalize_relative_path(self.source_relative_path)
        if self.position < 1 or self.position > FRAME_COUNT:
            raise ValueError("render frame position must be from 1 through 16")
        if len(self.source_sha256) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in self.source_sha256
        ):
            raise ValueError("render frame requires a SHA-256 value")
        matrix = np.asarray(self.source_to_reference_matrix, dtype=np.float64)
        if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
            raise ValueError("render frame transform must be a finite 3 x 3 matrix")
        if abs(np.linalg.det(matrix)) < 1e-12:
            raise ValueError("render frame transform must be invertible")


@dataclass(frozen=True, slots=True)
class ReferenceFillLayer:
    image_relative_path: str
    image_sha256: str
    mask_relative_path: str
    mask_sha256: str
    source_to_canvas_affine: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
    ]

    def __post_init__(self) -> None:
        normalize_relative_path(self.image_relative_path)
        normalize_relative_path(self.mask_relative_path)
        for digest in (self.image_sha256, self.mask_sha256):
            if len(digest) != 64 or any(
                character not in "0123456789abcdefABCDEF" for character in digest
            ):
                raise ValueError("reference fill inputs require SHA-256 values")
        affine = np.asarray(self.source_to_canvas_affine, dtype=np.float64)
        if affine.shape != (2, 3) or not np.isfinite(affine).all():
            raise ValueError("reference affine must be a finite 2 x 3 matrix")
        if abs(np.linalg.det(affine[:, :2])) < 1e-12:
            raise ValueError("reference affine must be invertible")


@dataclass(frozen=True, slots=True)
class ReconstructionRenderRequest:
    acquisition_id: str
    frames: tuple[RenderFrame, ...]
    source_width: int
    source_height: int
    output_directory_relative_path: str
    tile_size: int = 1024
    preview_maximum_dimension: int = 2000
    reference_fill: ReferenceFillLayer | None = None

    def __post_init__(self) -> None:
        normalize_relative_path(self.output_directory_relative_path)
        if [frame.position for frame in self.frames] != list(range(1, FRAME_COUNT + 1)):
            raise ValueError("render request requires ordered frames 1 through 16")
        if self.source_width <= 0 or self.source_height <= 0:
            raise ValueError("render source dimensions must be positive")
        if self.tile_size <= 0 or self.tile_size * self.tile_size > MAX_TILE_PIXELS:
            raise ValueError("render tile size is outside the safe range")
        if self.preview_maximum_dimension < 64 or self.preview_maximum_dimension > 5000:
            raise ValueError("preview maximum dimension is outside the safe range")


@dataclass(frozen=True, slots=True)
class RenderedFile:
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ReconstructionArtifactSet:
    acquisition_id: str
    canvas_width: int
    canvas_height: int
    reconstructed_image: RenderedFile
    coverage_map: RenderedFile
    provenance_map: RenderedFile
    preview_image: RenderedFile
    transforms: RenderedFile
    report: RenderedFile
    uncovered_pixel_count: int
    maximum_coverage_count: int


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_file(path: Path, expected_sha256: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ReconstructionRenderFailure(f"render input is not a regular file: {path.name}")
    if _file_sha256(path) != expected_sha256.lower():
        raise ReconstructionRenderFailure(f"render input checksum mismatch: {path.name}")


def _canvas_geometry(
    request: ReconstructionRenderRequest,
) -> tuple[int, int, tuple[Matrix3x3, ...], tuple[tuple[int, int, int, int], ...]]:
    corners = np.asarray(
        (
            (0.0, 0.0),
            (request.source_width - 1.0, 0.0),
            (request.source_width - 1.0, request.source_height - 1.0),
            (0.0, request.source_height - 1.0),
        )
    )
    mapped_corners = []
    homogeneous_corners = np.column_stack((corners, np.ones(len(corners), dtype=np.float64)))
    for frame in request.frames:
        matrix = np.asarray(frame.source_to_reference_matrix, dtype=np.float64)
        denominators = (homogeneous_corners @ matrix.T)[:, 2]
        if not (np.all(denominators > 1e-12) or np.all(denominators < -1e-12)):
            raise ReconstructionRenderFailure(
                f"frame {frame.position} transform crosses the projective horizon"
            )
        mapped_corners.append(map_points(matrix, corners))
    combined = np.vstack(mapped_corners)
    minimum = np.floor(combined.min(axis=0))
    maximum = np.ceil(combined.max(axis=0))
    width = int(maximum[0] - minimum[0] + 1)
    height = int(maximum[1] - minimum[1] + 1)
    if width <= 0 or height <= 0:
        raise ReconstructionRenderFailure("render transforms produce an invalid canvas")
    translation = np.asarray(
        (
            (1.0, 0.0, -minimum[0]),
            (0.0, 1.0, -minimum[1]),
            (0.0, 0.0, 1.0),
        )
    )
    matrices = []
    bounds = []
    for source_matrix, frame_corners in zip(
        (frame.source_to_reference_matrix for frame in request.frames),
        mapped_corners,
        strict=True,
    ):
        canvas_matrix_array = translation @ np.asarray(source_matrix, dtype=np.float64)
        canvas_matrix = cast(
            Matrix3x3,
            tuple(tuple(float(value) for value in row) for row in canvas_matrix_array),
        )
        matrices.append(canvas_matrix)
        canvas_corners = frame_corners - minimum
        bounds.append(
            (
                math.floor(float(canvas_corners[:, 0].min())),
                math.floor(float(canvas_corners[:, 1].min())),
                math.ceil(float(canvas_corners[:, 0].max())) + 1,
                math.ceil(float(canvas_corners[:, 1].max())) + 1,
            )
        )
    return width, height, tuple(matrices), tuple(bounds)


def _pil_coefficients(
    output_to_source: npt.NDArray[np.float64],
    x_offset: int,
    y_offset: int,
) -> tuple[float, float, float, float, float, float, float, float]:
    local_to_global = np.asarray(((1.0, 0.0, x_offset), (0.0, 1.0, y_offset), (0.0, 0.0, 1.0)))
    matrix = output_to_source @ local_to_global
    matrix /= matrix[2, 2]
    return (
        float(matrix[0, 0]),
        float(matrix[0, 1]),
        float(matrix[0, 2]),
        float(matrix[1, 0]),
        float(matrix[1, 1]),
        float(matrix[1, 2]),
        float(matrix[2, 0]),
        float(matrix[2, 1]),
    )


def _warp_source_tile(
    image_path: Path,
    source_size: tuple[int, int],
    output_to_source: npt.NDArray[np.float64],
    tile: tuple[int, int, int, int],
) -> tuple[
    npt.NDArray[np.uint8],
    npt.NDArray[np.bool_],
    npt.NDArray[np.float32],
]:
    x0, y0, x1, y1 = tile
    size = (x1 - x0, y1 - y0)
    coefficients = _pil_coefficients(output_to_source, x0, y0)
    with Image.open(image_path) as source:
        source.load()
        if source.size != source_size:
            raise ReconstructionRenderFailure(f"render input geometry mismatch: {image_path.name}")
        rgb = source.convert("RGB").transform(
            size,
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.BILINEAR,
            fillcolor=(0, 0, 0),
        )
    valid_source = Image.new("L", source_size, 255)
    valid = valid_source.transform(
        size,
        Image.Transform.PERSPECTIVE,
        coefficients,
        resample=Image.Resampling.NEAREST,
        fillcolor=0,
    )
    valid_array = np.asarray(valid, dtype=np.uint8) > 0
    output_x, output_y = np.meshgrid(
        np.arange(x0, x1, dtype=np.float64),
        np.arange(y0, y1, dtype=np.float64),
    )
    denominator = (
        output_to_source[2, 0] * output_x
        + output_to_source[2, 1] * output_y
        + output_to_source[2, 2]
    )
    source_x = (
        output_to_source[0, 0] * output_x
        + output_to_source[0, 1] * output_y
        + output_to_source[0, 2]
    ) / denominator
    source_y = (
        output_to_source[1, 0] * output_x
        + output_to_source[1, 1] * output_y
        + output_to_source[1, 2]
    ) / denominator
    width, height = source_size
    weights = np.minimum.reduce(
        (
            source_x + 1.0,
            width - source_x,
            source_y + 1.0,
            height - source_y,
            np.full(source_x.shape, 512.0),
        )
    )
    weights = np.where(valid_array, np.clip(weights, 0.0, 512.0), 0.0).astype(np.float32)
    return np.asarray(rgb, dtype=np.uint8), valid_array, weights


def _warp_reference_tile(
    paths: ApplicationPaths,
    layer: ReferenceFillLayer,
    tile: tuple[int, int, int, int],
) -> tuple[npt.NDArray[np.uint8], npt.NDArray[np.bool_]]:
    image_path = paths.resolve_data_path(layer.image_relative_path)
    mask_path = paths.resolve_data_path(layer.mask_relative_path)
    x0, y0, x1, y1 = tile
    size = (x1 - x0, y1 - y0)
    affine = np.eye(3, dtype=np.float64)
    affine[:2, :] = np.asarray(layer.source_to_canvas_affine, dtype=np.float64)
    inverse = np.asarray(np.linalg.inv(affine), dtype=np.float64)
    coefficients = _pil_coefficients(inverse, x0, y0)
    with Image.open(image_path) as source:
        rgb = source.convert("RGB").transform(
            size,
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.BICUBIC,
            fillcolor=(0, 0, 0),
        )
        source_size = source.size
    with Image.open(mask_path) as source_mask:
        if source_mask.size != source_size:
            raise ReconstructionRenderFailure("reference image and mask dimensions do not match")
        mask = source_mask.convert("L").transform(
            size,
            Image.Transform.PERSPECTIVE,
            coefficients,
            resample=Image.Resampling.BILINEAR,
            fillcolor=0,
        )
    return np.asarray(rgb, dtype=np.uint8), np.asarray(mask, dtype=np.uint8) >= 128


def _rendered_file(paths: ApplicationPaths, path: Path) -> RenderedFile:
    return RenderedFile(
        relative_path=paths.to_data_relative_path(path),
        sha256=_file_sha256(path),
        size_bytes=path.stat().st_size,
    )


def _validate_tiff(
    path: Path,
    expected_shape: tuple[int, ...],
    expected_dtype: np.dtype[np.generic],
) -> None:
    with tifffile.TiffFile(path) as document:
        if not document.is_bigtiff:
            raise ReconstructionRenderFailure(f"artifact is not BigTIFF: {path.name}")
        series = document.series[0]
        if series.shape != expected_shape or series.dtype != expected_dtype:
            raise ReconstructionRenderFailure(f"artifact failed reopen validation: {path.name}")


def _close_memmap(value: UInt8MemMap | None) -> None:
    if value is None:
        return
    value.flush()
    mapped_file = getattr(value, "_mmap", None)
    if mapped_file is not None:
        mapped_file.close()


def render_reconstruction(
    paths: ApplicationPaths,
    request: ReconstructionRenderRequest,
    *,
    cancelled: Callable[[], bool] | None = None,
    free_space_bytes: Callable[[Path], int] | None = None,
) -> ReconstructionArtifactSet:
    """Render bounded tiles and atomically publish a validated artifact directory."""

    final_directory = paths.resolve_data_path(request.output_directory_relative_path)
    if final_directory.exists():
        raise ReconstructionRenderFailure("reconstruction output directory already exists")
    final_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = final_directory.parent / f".{final_directory.name}.{uuid.uuid4().hex}.staging"
    staging.mkdir()
    image_map: UInt8MemMap | None = None
    coverage_map: UInt8MemMap | None = None
    provenance_map: UInt8MemMap | None = None
    try:
        source_paths = []
        for frame in request.frames:
            source_path = paths.resolve_data_path(frame.source_relative_path)
            _verify_file(source_path, frame.source_sha256)
            source_paths.append(source_path)
        if request.reference_fill is not None:
            reference = request.reference_fill
            _verify_file(
                paths.resolve_data_path(reference.image_relative_path),
                reference.image_sha256,
            )
            _verify_file(
                paths.resolve_data_path(reference.mask_relative_path),
                reference.mask_sha256,
            )

        width, height, matrices, bounds = _canvas_geometry(request)
        estimated_bytes = int(width * height * 5 * 1.20) + 16 * 1024 * 1024
        available = (
            shutil.disk_usage(final_directory.parent).free
            if free_space_bytes is None
            else free_space_bytes(final_directory.parent)
        )
        if available < estimated_bytes:
            raise ReconstructionRenderFailure(
                f"insufficient disk space: need {estimated_bytes} bytes, have {available}"
            )

        image_path = staging / "reconstructed-disc.tif"
        coverage_path = staging / "coverage-map.tif"
        provenance_path = staging / "provenance-map.tif"
        preview_path = staging / "reconstructed-preview.png"
        transforms_path = staging / "transforms.json"
        report_path = staging / "reconstruction-report.json"
        image_map = tifffile.memmap(
            image_path,
            shape=(height, width, 3),
            dtype=np.uint8,
            photometric="rgb",
            bigtiff=True,
            metadata=None,
        )
        coverage_map = tifffile.memmap(
            coverage_path,
            shape=(height, width),
            dtype=np.uint8,
            photometric="minisblack",
            bigtiff=True,
            metadata=None,
        )
        provenance_map = tifffile.memmap(
            provenance_path,
            shape=(height, width),
            dtype=np.uint8,
            photometric="minisblack",
            bigtiff=True,
            metadata=None,
        )
        preview_scale = min(
            1.0,
            request.preview_maximum_dimension / max(width, height),
        )
        preview_size = (
            max(1, round(width * preview_scale)),
            max(1, round(height * preview_scale)),
        )
        preview = Image.new("RGB", preview_size)
        uncovered_pixels = 0
        maximum_coverage = 0
        for y0 in range(0, height, request.tile_size):
            for x0 in range(0, width, request.tile_size):
                if cancelled is not None and cancelled():
                    raise ReconstructionRenderCancelled("reconstruction cancelled by caller")
                x1 = min(x0 + request.tile_size, width)
                y1 = min(y0 + request.tile_size, height)
                tile = (x0, y0, x1, y1)
                tile_height, tile_width = y1 - y0, x1 - x0
                accumulator = np.zeros((tile_height, tile_width, 3), dtype=np.float32)
                total_weight = np.zeros((tile_height, tile_width), dtype=np.float32)
                coverage = np.zeros((tile_height, tile_width), dtype=np.uint8)
                for index, bound in enumerate(bounds):
                    left, top, right, bottom = bound
                    if right <= x0 or left >= x1 or bottom <= y0 or top >= y1:
                        continue
                    warped, valid, weights = _warp_source_tile(
                        source_paths[index],
                        (request.source_width, request.source_height),
                        np.asarray(
                            np.linalg.inv(np.asarray(matrices[index], dtype=np.float64)),
                            dtype=np.float64,
                        ),
                        tile,
                    )
                    accumulator[valid] += warped[valid] * weights[valid, None]
                    total_weight[valid] += weights[valid]
                    coverage[valid] = np.minimum(coverage[valid].astype(np.uint16) + 1, 255)
                natural = np.zeros((tile_height, tile_width, 3), dtype=np.uint8)
                acquired = coverage > 0
                natural[acquired] = np.clip(
                    accumulator[acquired] / total_weight[acquired, None],
                    0,
                    255,
                ).astype(np.uint8)
                provenance = np.where(
                    acquired,
                    PixelProvenance.ACQUIRED.value,
                    PixelProvenance.NO_DATA.value,
                ).astype(np.uint8)
                if request.reference_fill is not None:
                    reference_rgb, reference_mask = _warp_reference_tile(
                        paths,
                        request.reference_fill,
                        tile,
                    )
                    fill = (~acquired) & reference_mask
                    natural[fill] = reference_rgb[fill]
                    provenance[fill] = PixelProvenance.REFERENCE_FILL.value
                image_map[y0:y1, x0:x1] = natural
                coverage_map[y0:y1, x0:x1] = coverage
                provenance_map[y0:y1, x0:x1] = provenance
                uncovered_pixels += int(np.count_nonzero(provenance == PixelProvenance.NO_DATA))
                maximum_coverage = max(maximum_coverage, int(coverage.max(initial=0)))

                preview_box = (
                    math.floor(x0 * preview_size[0] / width),
                    math.floor(y0 * preview_size[1] / height),
                    math.ceil(x1 * preview_size[0] / width),
                    math.ceil(y1 * preview_size[1] / height),
                )
                preview_tile = Image.fromarray(natural).resize(
                    (preview_box[2] - preview_box[0], preview_box[3] - preview_box[1]),
                    Image.Resampling.BILINEAR,
                )
                preview.paste(preview_tile, preview_box[:2])
        _close_memmap(image_map)
        _close_memmap(coverage_map)
        _close_memmap(provenance_map)
        image_map = None
        coverage_map = None
        provenance_map = None
        preview.save(preview_path, format="PNG", optimize=False)

        transforms_payload = {
            "schema_version": 1,
            "acquisition_id": request.acquisition_id,
            "canvas_dimensions": [width, height],
            "source_to_canvas_matrices": matrices,
        }
        transforms_path.write_text(
            json.dumps(transforms_payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        report_payload = {
            "schema_version": 1,
            "acquisition_id": request.acquisition_id,
            "canvas_dimensions": [width, height],
            "frame_count": FRAME_COUNT,
            "tile_size": request.tile_size,
            "uncovered_pixel_count": uncovered_pixels,
            "maximum_coverage_count": maximum_coverage,
            "reference_fill_applied": request.reference_fill is not None,
            "source_crop_applied": False,
            "status": "rendered_for_validation",
        }
        report_path.write_text(
            json.dumps(report_payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        _validate_tiff(image_path, (height, width, 3), np.dtype(np.uint8))
        _validate_tiff(coverage_path, (height, width), np.dtype(np.uint8))
        _validate_tiff(provenance_path, (height, width), np.dtype(np.uint8))
        with Image.open(preview_path) as reopened_preview:
            reopened_preview.verify()
        os.replace(staging, final_directory)

        reconstructed = final_directory / image_path.name
        coverage_file = final_directory / coverage_path.name
        provenance_file = final_directory / provenance_path.name
        preview_final = final_directory / preview_path.name
        transforms = final_directory / transforms_path.name
        report = final_directory / report_path.name
        return ReconstructionArtifactSet(
            acquisition_id=request.acquisition_id,
            canvas_width=width,
            canvas_height=height,
            reconstructed_image=_rendered_file(paths, reconstructed),
            coverage_map=_rendered_file(paths, coverage_file),
            provenance_map=_rendered_file(paths, provenance_file),
            preview_image=_rendered_file(paths, preview_final),
            transforms=_rendered_file(paths, transforms),
            report=_rendered_file(paths, report),
            uncovered_pixel_count=uncovered_pixels,
            maximum_coverage_count=maximum_coverage,
        )
    except Exception:
        _close_memmap(image_map)
        _close_memmap(coverage_map)
        _close_memmap(provenance_map)
        if staging.exists():
            shutil.rmtree(staging)
        raise
