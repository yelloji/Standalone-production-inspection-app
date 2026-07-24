"""Automatic preview center-completion safety tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from backend.core.paths import ApplicationPaths
from backend.domain.center_completion import (
    CenterAssetContract,
    CenterCompletionProfile,
    CenterStrategy,
)
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import (
    CalibrationContract,
    CalibrationState,
    Point2D,
    RoiRectangle,
)
from backend.reconstruction.preview_center import apply_center_completion_to_preview


def test_upper_completion_fills_only_enclosed_no_data_pixels(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(
        resource_root=tmp_path,
        data_root=tmp_path / "data",
    )
    paths.ensure_data_layout()
    preview_path = paths.resolve_data_path("completed/demo/reconstructed-preview.png")
    preview_path.parent.mkdir(parents=True)
    preview = np.zeros((512, 512, 3), dtype=np.uint8)
    cv2.circle(preview, (256, 256), 230, (30, 80, 120), -1)
    cv2.circle(preview, (256, 256), 180, (0, 0, 0), -1)
    assert cv2.imwrite(str(preview_path), preview)

    reference_path = paths.resolve_data_path("configuration/center-references/upper.png")
    reference_path.parent.mkdir(parents=True)
    reference = np.full((100, 100, 3), (45, 55, 65), dtype=np.uint8)
    cv2.circle(reference, (65, 50), 6, (230, 230, 230), -1)
    assert cv2.imwrite(str(reference_path), reference)
    digest = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    profile = CenterCompletionProfile(
        profile_id="upper-test-v1",
        side=DiscSide.UPPER,
        strategy=CenterStrategy.UPPER_BLACK_PLATE,
        asset=CenterAssetContract(
            asset_id="upper-test-asset-v1",
            relative_path="configuration/center-references/upper.png",
            sha256=digest,
            source_center=Point2D(x=50.0, y=50.0),
            source_radius_px=45.0,
            marker_center=Point2D(x=65.0, y=50.0),
            black_plate_only=True,
            includes_silver_screens=False,
        ),
    )
    calibration = CalibrationContract(
        acquisition_id="demo",
        side=DiscSide.UPPER,
        state=CalibrationState.VALIDATED,
        input_width=512,
        input_height=512,
        output_width=512,
        output_height=512,
        usable_source_roi=RoiRectangle(x=0, y=0, width=512, height=512),
        source_disc_center=Point2D(x=256.0, y=256.0),
        output_disc_center=Point2D(x=256.0, y=256.0),
        inner_radius=180.0,
        outer_radius=230.0,
        reference_ray_degrees=90.0,
        source_to_calibrated_matrix=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        calibrated_to_source_matrix=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
    )

    result = apply_center_completion_to_preview(
        paths,
        preview_relative_path="completed/demo/reconstructed-preview.png",
        source_to_preview_matrix=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        calibration=calibration,
        profile=profile,
    )

    completed = cv2.imread(str(preview_path), cv2.IMREAD_COLOR)
    assert completed is not None
    acquired = np.any(preview != 0, axis=2)
    assert np.array_equal(completed[acquired], preview[acquired])
    assert result.filled_pixels > 90_000
    assert result.acquired_pixels_changed == 0
    assert np.any(completed[256, 256] != 0)
