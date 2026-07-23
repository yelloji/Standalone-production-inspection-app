"""Bounded rendering, artifact validation, cancellation, and publication tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image

from backend.core.paths import ApplicationPaths
from backend.core.serialization import sha256_hex
from backend.domain.center_completion import PixelProvenance
from backend.reconstruction.rendering import (
    ReconstructionRenderCancelled,
    ReconstructionRenderFailure,
    ReconstructionRenderRequest,
    ReferenceFillLayer,
    RenderFrame,
    render_reconstruction,
)

IDENTITY = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


def _paths(tmp_path: Path) -> ApplicationPaths:
    paths = ApplicationPaths.resolve(
        resource_root=tmp_path.resolve(),
        data_root=(tmp_path / "data").resolve(),
    )
    paths.ensure_data_layout()
    return paths


def _request(
    paths: ApplicationPaths,
    output: str = "completed/render-001",
) -> ReconstructionRenderRequest:
    frame_directory = paths.resolve_data_path("incoming/acquisition-001")
    frame_directory.mkdir(parents=True)
    frames = []
    for position in range(1, 17):
        image = np.zeros((12, 16, 3), dtype=np.uint8)
        image[..., 0] = position
        image[..., 1] = position * 2
        image[..., 2] = position * 3
        path = frame_directory / f"frame-{position:02d}.png"
        Image.fromarray(image).save(path)
        frames.append(
            RenderFrame(
                position=position,
                source_relative_path=paths.to_data_relative_path(path),
                source_sha256=sha256_hex(path.read_bytes()),
                source_to_reference_matrix=IDENTITY,
            )
        )
    return ReconstructionRenderRequest(
        acquisition_id="acquisition-001",
        frames=tuple(frames),
        source_width=16,
        source_height=12,
        output_directory_relative_path=output,
        tile_size=8,
        preview_maximum_dimension=64,
    )


def test_renders_reopens_and_atomically_publishes_complete_artifact_set(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    request = _request(paths)
    result = render_reconstruction(
        paths,
        request,
        free_space_bytes=lambda _: 1_000_000_000,
    )

    assert result.canvas_width == 16
    assert result.canvas_height == 12
    assert result.uncovered_pixel_count == 0
    assert result.maximum_coverage_count == 16
    output = paths.resolve_data_path(request.output_directory_relative_path)
    assert {path.name for path in output.iterdir()} == {
        "reconstructed-disc.tif",
        "coverage-map.tif",
        "provenance-map.tif",
        "reconstructed-preview.png",
        "transforms.json",
        "reconstruction-report.json",
    }
    for rendered in (
        result.reconstructed_image,
        result.coverage_map,
        result.provenance_map,
        result.preview_image,
        result.transforms,
        result.report,
    ):
        path = paths.resolve_data_path(rendered.relative_path)
        assert path.stat().st_size == rendered.size_bytes
        assert sha256_hex(path.read_bytes()) == rendered.sha256

    with tifffile.TiffFile(
        paths.resolve_data_path(result.reconstructed_image.relative_path)
    ) as document:
        assert document.is_bigtiff
        image = document.asarray()
    coverage = tifffile.imread(paths.resolve_data_path(result.coverage_map.relative_path))
    provenance = tifffile.imread(paths.resolve_data_path(result.provenance_map.relative_path))
    assert image.shape == (12, 16, 3)
    assert np.all(coverage == 16)
    assert np.all(provenance == PixelProvenance.ACQUIRED.value)
    assert image[0, 0].tolist() == [8, 17, 25]


def test_cancellation_removes_staging_and_never_publishes_partial_output(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    request = _request(paths)
    with pytest.raises(ReconstructionRenderCancelled):
        render_reconstruction(
            paths,
            request,
            cancelled=lambda: True,
            free_space_bytes=lambda _: 1_000_000_000,
        )
    final = paths.resolve_data_path(request.output_directory_relative_path)
    assert not final.exists()
    assert not list(final.parent.glob(".*.staging"))


def test_disk_space_gate_fails_before_artifact_allocation_and_cleans_staging(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    request = _request(paths)
    with pytest.raises(ReconstructionRenderFailure, match="insufficient disk space"):
        render_reconstruction(paths, request, free_space_bytes=lambda _: 0)
    final = paths.resolve_data_path(request.output_directory_relative_path)
    assert not final.exists()
    assert not list(final.parent.glob(".*.staging"))


def test_checksum_mismatch_and_existing_output_are_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    request = _request(paths)
    bad_frame = request.frames[0]
    bad_frames = (
        RenderFrame(
            position=1,
            source_relative_path=bad_frame.source_relative_path,
            source_sha256="0" * 64,
            source_to_reference_matrix=bad_frame.source_to_reference_matrix,
        ),
        *request.frames[1:],
    )
    bad_request = ReconstructionRenderRequest(
        acquisition_id=request.acquisition_id,
        frames=bad_frames,
        source_width=request.source_width,
        source_height=request.source_height,
        output_directory_relative_path=request.output_directory_relative_path,
        tile_size=request.tile_size,
        preview_maximum_dimension=request.preview_maximum_dimension,
    )
    with pytest.raises(ReconstructionRenderFailure, match="checksum"):
        render_reconstruction(
            paths,
            bad_request,
            free_space_bytes=lambda _: 1_000_000_000,
        )

    final = paths.resolve_data_path(request.output_directory_relative_path)
    final.mkdir(parents=True)
    with pytest.raises(ReconstructionRenderFailure, match="already exists"):
        render_reconstruction(
            paths,
            request,
            free_space_bytes=lambda _: 1_000_000_000,
        )


def test_reference_layer_fills_only_uncovered_pixels(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    base_request = _request(paths)
    translated_frames = tuple(
        RenderFrame(
            position=frame.position,
            source_relative_path=frame.source_relative_path,
            source_sha256=frame.source_sha256,
            source_to_reference_matrix=(
                (1.0, 0.0, 0.0 if frame.position <= 8 else 24.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
            ),
        )
        for frame in base_request.frames
    )
    reference_image_path = paths.resolve_data_path("configuration/reference.png")
    reference_mask_path = paths.resolve_data_path("configuration/reference-mask.png")
    reference_image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full((12, 40, 3), (200, 100, 50), dtype=np.uint8)).save(reference_image_path)
    Image.fromarray(np.full((12, 40), 255, dtype=np.uint8)).save(reference_mask_path)
    request = ReconstructionRenderRequest(
        acquisition_id=base_request.acquisition_id,
        frames=translated_frames,
        source_width=base_request.source_width,
        source_height=base_request.source_height,
        output_directory_relative_path=base_request.output_directory_relative_path,
        tile_size=base_request.tile_size,
        preview_maximum_dimension=base_request.preview_maximum_dimension,
        reference_fill=ReferenceFillLayer(
            image_relative_path=paths.to_data_relative_path(reference_image_path),
            image_sha256=sha256_hex(reference_image_path.read_bytes()),
            mask_relative_path=paths.to_data_relative_path(reference_mask_path),
            mask_sha256=sha256_hex(reference_mask_path.read_bytes()),
            source_to_canvas_affine=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ),
    )

    result = render_reconstruction(
        paths,
        request,
        free_space_bytes=lambda _: 1_000_000_000,
    )

    image = tifffile.imread(paths.resolve_data_path(result.reconstructed_image.relative_path))
    coverage = tifffile.imread(paths.resolve_data_path(result.coverage_map.relative_path))
    provenance = tifffile.imread(paths.resolve_data_path(result.provenance_map.relative_path))
    assert result.canvas_width == 40
    assert result.uncovered_pixel_count == 0
    assert coverage[6, 8] == 8
    assert provenance[6, 8] == PixelProvenance.ACQUIRED.value
    assert image[6, 8].tolist() != [200, 100, 50]
    assert coverage[6, 20] == 0
    assert provenance[6, 20] == PixelProvenance.REFERENCE_FILL.value
    assert image[6, 20].tolist() == [200, 100, 50]


def test_projective_horizon_crossing_is_rejected_without_artifacts(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    request = _request(paths)
    crossing_frame = request.frames[0]
    crossing_frames = (
        RenderFrame(
            position=crossing_frame.position,
            source_relative_path=crossing_frame.source_relative_path,
            source_sha256=crossing_frame.source_sha256,
            source_to_reference_matrix=(
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.2, 0.0, -1.0),
            ),
        ),
        *request.frames[1:],
    )
    crossing_request = ReconstructionRenderRequest(
        acquisition_id=request.acquisition_id,
        frames=crossing_frames,
        source_width=request.source_width,
        source_height=request.source_height,
        output_directory_relative_path=request.output_directory_relative_path,
        tile_size=request.tile_size,
        preview_maximum_dimension=request.preview_maximum_dimension,
    )

    with pytest.raises(ReconstructionRenderFailure, match="projective horizon"):
        render_reconstruction(
            paths,
            crossing_request,
            free_space_bytes=lambda _: 1_000_000_000,
        )

    final = paths.resolve_data_path(request.output_directory_relative_path)
    assert not final.exists()
    assert not list(final.parent.glob(".*.staging"))
