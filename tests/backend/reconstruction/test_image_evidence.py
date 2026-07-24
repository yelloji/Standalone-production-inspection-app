"""Image-driven reconstruction evidence tests."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from backend.reconstruction.image_evidence import (
    ImageEvidenceFailure,
    ImageEvidenceProfile,
    extract_cycle_image_evidence,
)


def _cycle_images(root: Path) -> tuple[Path, ...]:
    rng = np.random.default_rng(42)
    texture = rng.integers(0, 256, (320, 420), dtype=np.uint8)
    texture = cv2.GaussianBlur(texture, (3, 3), 0)
    cv2.putText(texture, "BRAKE DISC", (35, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 255, 2)
    paths = []
    for index in range(16):
        matrix = cv2.getRotationMatrix2D((210, 160), index * 0.08, 1.0)
        matrix[:, 2] += (index * 0.12, -index * 0.08)
        frame = cv2.warpAffine(
            texture,
            matrix,
            (420, 320),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        path = root / f"{index + 1:02d}.png"
        Image.fromarray(frame).save(path)
        paths.append(path)
    return tuple(paths)


def test_extracts_complete_ordered_cycle_with_held_out_evidence(tmp_path: Path) -> None:
    progress: list[tuple[int, int]] = []
    result = extract_cycle_image_evidence(
        _cycle_images(tmp_path),
        profile=ImageEvidenceProfile(
            working_scale=0.5,
            excluded_top_fraction=0.0,
            sift_feature_count=2_000,
            maximum_dense_corners=300,
            dense_minimum_distance_px=5.0,
        ),
        progress=lambda completed, total: progress.append((completed, total)),
    )

    assert (result.image_width, result.image_height) == (420, 320)
    assert [(pair.source_frame, pair.target_frame) for pair in result.pairs] == [
        (position, position + 1 if position < 16 else 1) for position in range(1, 17)
    ]
    assert all(len(pair.fit_source_points) >= 8 for pair in result.pairs)
    assert all(len(pair.validation_source_points) >= 5 for pair in result.pairs)
    assert progress[-1] == (16, 16)
    assert len(result.diagnostics) == 16


def test_rejects_incomplete_or_mismatched_image_sets(tmp_path: Path) -> None:
    paths = _cycle_images(tmp_path)
    with pytest.raises(ImageEvidenceFailure, match="exactly 16"):
        extract_cycle_image_evidence(paths[:-1])

    Image.new("L", (100, 100)).save(paths[-1])
    with pytest.raises(ImageEvidenceFailure, match="identical dimensions"):
        extract_cycle_image_evidence(paths)


def test_honors_cancellation_before_registration(tmp_path: Path) -> None:
    with pytest.raises(ImageEvidenceFailure, match="cancelled"):
        extract_cycle_image_evidence(
            _cycle_images(tmp_path),
            profile=ImageEvidenceProfile(
                working_scale=0.5,
                excluded_top_fraction=0.0,
                sift_feature_count=2_000,
                maximum_dense_corners=300,
            ),
            cancelled=lambda: True,
        )
