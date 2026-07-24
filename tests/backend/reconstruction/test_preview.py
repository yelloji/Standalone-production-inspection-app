"""Bounded reconstruction preview rendering tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from backend.core.paths import ApplicationPaths
from backend.reconstruction.preview import (
    ReconstructionPreviewFailure,
    render_reconstruction_preview,
)
from backend.reconstruction.rendering import RenderFrame


def _frame(path: Path, position: int) -> RenderFrame:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return RenderFrame(
        position=position,
        source_relative_path=f"incoming/demo/frames/{position:02d}.png",
        source_sha256=digest,
        source_to_reference_matrix=(
            (1.0, 0.0, float((position - 1) * 2)),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
    )


def test_renders_atomic_bounded_uncropped_preview(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(
        resource_root=tmp_path,
        data_root=tmp_path / "data",
    )
    paths.ensure_data_layout()
    source = paths.resolve_data_path("incoming/demo/frames")
    source.mkdir(parents=True)
    frames = []
    for position in range(1, 17):
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        image[:, :, position % 3] = 80 + position
        cv2.circle(image, (30 + position, 40), 12, (240, 240, 240), -1)
        path = source / f"{position:02d}.png"
        Image.fromarray(image).save(path)
        frames.append(_frame(path, position))

    result = render_reconstruction_preview(
        paths,
        frames=tuple(frames),
        source_width=120,
        source_height=80,
        output_relative_path="completed/demo/reconstruction-preview.png",
        maximum_dimension=512,
    )

    output = paths.resolve_data_path(result.relative_path)
    assert output.is_file()
    assert result.width == 150
    assert result.height == 80
    assert result.source_canvas_width == 150
    assert result.sha256 == hashlib.sha256(output.read_bytes()).hexdigest()
    assert Image.open(output).size == (150, 80)
    assert not list(output.parent.glob("*.tmp.png"))


def test_rejects_overwrite_and_incomplete_frame_set(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, data_root=tmp_path / "data")
    paths.ensure_data_layout()
    with pytest.raises(ReconstructionPreviewFailure, match="ordered"):
        render_reconstruction_preview(
            paths,
            frames=(),
            source_width=120,
            source_height=80,
            output_relative_path="completed/demo/preview.png",
        )


def test_renders_exact_square_without_stretching_or_cropping(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, data_root=tmp_path / "data")
    paths.ensure_data_layout()
    source = paths.resolve_data_path("incoming/square/frames")
    source.mkdir(parents=True)
    frames = []
    for position in range(1, 17):
        path = source / f"{position:02d}.png"
        Image.new("RGB", (120, 80), (position, 30, 60)).save(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        frames.append(
            RenderFrame(
                position=position,
                source_relative_path=f"incoming/square/frames/{position:02d}.png",
                source_sha256=digest,
                source_to_reference_matrix=(
                    (1.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0),
                    (0.0, 0.0, 1.0),
                ),
            )
        )

    result = render_reconstruction_preview(
        paths,
        frames=tuple(frames),
        source_width=120,
        source_height=80,
        output_relative_path="completed/square/preview.png",
        square_size=512,
    )

    assert (result.width, result.height) == (512, 512)
    image = np.asarray(Image.open(paths.resolve_data_path(result.relative_path)))
    covered = np.any(image != 0, axis=2)
    rows, columns = np.where(covered)
    assert columns.min() == 196
    assert columns.max() == 315
    assert rows.min() == 216
    assert rows.max() == 295
