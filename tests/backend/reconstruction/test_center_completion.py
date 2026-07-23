"""Side-specific center completion and cyclic alignment tests."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from backend.domain.center_completion import (
    CenterAssetContract,
    CenterCompletionProfile,
    CenterStrategy,
    PixelProvenance,
)
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import Point2D
from backend.reconstruction.center_completion import (
    CenterCompletionFailure,
    CenterCompletionPlan,
    detect_flash_angles,
    plan_lower_center_completion,
    plan_upper_center_completion,
)


def upper_asset() -> CenterAssetContract:
    return CenterAssetContract(
        asset_id="upper-black-plate-v1",
        relative_path="configuration/center-assets/upper.png",
        sha256="1" * 64,
        source_center=Point2D(x=3955.9, y=2055.4),
        source_radius_px=1458.1,
        marker_center=Point2D(x=3295.0, y=2514.0),
        black_plate_only=True,
        includes_silver_screens=False,
    )


def lower_asset() -> CenterAssetContract:
    return CenterAssetContract(
        asset_id="lower-complete-assembly-v1",
        relative_path="configuration/center-assets/lower.png",
        sha256="2" * 64,
        source_center=Point2D(x=2397.0, y=4017.0),
        source_radius_px=1854.6,
        marker_center=Point2D(x=2290.0, y=3175.0),
        black_plate_only=False,
        includes_silver_screens=True,
        source_screen_angles_degrees=(
            27.0,
            63.0,
            99.0,
            135.0,
            172.0,
            207.0,
            244.0,
            280.0,
            316.0,
            351.0,
        ),
    )


def upper_profile() -> CenterCompletionProfile:
    return CenterCompletionProfile(
        profile_id="upper-center-v1",
        side=DiscSide.UPPER,
        strategy=CenterStrategy.UPPER_BLACK_PLATE,
        asset=upper_asset(),
    )


def lower_profile() -> CenterCompletionProfile:
    return CenterCompletionProfile(
        profile_id="lower-center-v1",
        side=DiscSide.LOWER,
        strategy=CenterStrategy.LOWER_COMPLETE_ASSEMBLY,
        asset=lower_asset(),
        allow_approved_screen_replacement=True,
    )


def _map_center(
    plan: CenterCompletionPlan,
    source_center: Point2D,
) -> tuple[float, float]:
    matrix = plan.source_to_output_affine
    return (
        matrix[0][0] * source_center.x + matrix[0][1] * source_center.y + matrix[0][2],
        matrix[1][0] * source_center.x + matrix[1][1] * source_center.y + matrix[1][2],
    )


def test_upper_plan_uses_only_marker_plate_geometry_and_preserves_acquired_pixels() -> None:
    target = Point2D(x=15700.0, y=15800.0)
    plan = plan_upper_center_completion(
        upper_profile(),
        image_one_start_ray_degrees=79.867,
        target_center=target,
        target_opening_radius_px=10828.944,
    )
    marker_angle = math.degrees(math.atan2(2514.0 - 2055.4, 3295.0 - 3955.9))
    expected_rotation = (79.867 - marker_angle + 180.0) % 360.0 - 180.0
    assert plan.rotation_degrees == pytest.approx(expected_rotation)
    assert plan.scale == pytest.approx(10828.944 / 1458.1)
    assert _map_center(plan, upper_asset().source_center) == pytest.approx((target.x, target.y))
    assert plan.preserve_acquired_pixels
    assert not plan.reference_pixels_inference_eligible
    assert not plan.allow_approved_screen_replacement
    assert plan.correspondences == ()


def test_lower_proof_angles_solve_one_shared_rotation_without_hardcoding() -> None:
    plan = plan_lower_center_completion(
        lower_profile(),
        image_one_start_ray_degrees=79.767,
        detected_flash_angles_degrees=(
            12.0,
            46.0,
            77.0,
            118.0,
            148.0,
            190.0,
            222.0,
            262.0,
            292.0,
            329.0,
        ),
        target_center=Point2D(x=15800.0, y=15900.0),
        target_opening_radius_px=10500.0,
    )
    assert plan.rotation_degrees == pytest.approx(160.0)
    assert plan.median_absolute_angular_residual_degrees == pytest.approx(2.0)
    assert plan.maximum_absolute_angular_residual_degrees is not None
    assert plan.maximum_absolute_angular_residual_degrees <= 8.0
    assert len(plan.correspondences) == 10
    assert plan.allow_approved_screen_replacement
    assert _map_center(plan, lower_asset().source_center) == pytest.approx((15800.0, 15900.0))


def test_flash_detector_finds_exactly_ten_circular_acquired_peaks() -> None:
    expected = (12, 46, 77, 118, 148, 190, 222, 262, 292, 329)
    scores = np.zeros(360, dtype=np.float64)
    for angle in expected:
        for offset, value in ((-1, 40.0), (0, 100.0), (1, 40.0)):
            scores[(angle + offset) % 360] = value
    result = detect_flash_angles(
        scores,
        smoothing_width_degrees=3,
        minimum_prominence=10.0,
    )
    assert result.angles_degrees == pytest.approx(expected)
    assert len(result.peak_scores) == 10
    assert min(result.peak_prominences) >= 10.0


def test_flash_detector_rejects_bad_profile_or_insufficient_peaks() -> None:
    with pytest.raises(CenterCompletionFailure, match="360 finite"):
        detect_flash_angles(np.zeros(359))
    with pytest.raises(CenterCompletionFailure, match="found 0"):
        detect_flash_angles(np.zeros(360))


def test_lower_rotation_is_measured_from_current_evidence_not_fixed_to_160() -> None:
    source = lower_asset().source_screen_angles_degrees
    target = tuple(sorted((angle + 123.0) % 360.0 for angle in source))
    plan = plan_lower_center_completion(
        lower_profile(),
        image_one_start_ray_degrees=25.757,
        detected_flash_angles_degrees=target,
        target_center=Point2D(x=1000.0, y=1200.0),
        target_opening_radius_px=500.0,
    )
    assert plan.rotation_degrees == pytest.approx(123.0)
    assert plan.median_absolute_angular_residual_degrees == pytest.approx(0.0)
    assert plan.maximum_absolute_angular_residual_degrees == pytest.approx(0.0)


def test_lower_alignment_rejects_missing_duplicate_or_bad_residual_evidence() -> None:
    with pytest.raises(CenterCompletionFailure, match="exactly 10"):
        plan_lower_center_completion(
            lower_profile(),
            image_one_start_ray_degrees=79.767,
            detected_flash_angles_degrees=[index * 36.0 for index in range(9)],
            target_center=Point2D(x=1000.0, y=1200.0),
            target_opening_radius_px=500.0,
        )
    with pytest.raises(CenterCompletionFailure, match="unique"):
        plan_lower_center_completion(
            lower_profile(),
            image_one_start_ray_degrees=79.767,
            detected_flash_angles_degrees=[0.0] * 10,
            target_center=Point2D(x=1000.0, y=1200.0),
            target_opening_radius_px=500.0,
        )
    irregular = [0.0, 12.0, 49.0, 83.0, 121.0, 169.0, 201.0, 250.0, 302.0, 347.0]
    with pytest.raises(CenterCompletionFailure, match="residual"):
        plan_lower_center_completion(
            lower_profile(),
            image_one_start_ray_degrees=79.767,
            detected_flash_angles_degrees=irregular,
            target_center=Point2D(x=1000.0, y=1200.0),
            target_opening_radius_px=500.0,
        )


def test_profiles_reject_wrong_side_assets_and_components() -> None:
    bad_asset = upper_asset().model_dump(mode="python")
    bad_asset["includes_silver_screens"] = True
    with pytest.raises(ValidationError, match="cannot include silver screens"):
        CenterAssetContract.model_validate(bad_asset)
    with pytest.raises(ValidationError, match="upper profile"):
        CenterCompletionProfile(
            profile_id="bad",
            side=DiscSide.UPPER,
            strategy=CenterStrategy.LOWER_COMPLETE_ASSEMBLY,
            asset=lower_asset(),
        )
    with pytest.raises(CenterCompletionFailure, match="upper profile"):
        plan_upper_center_completion(
            lower_profile(),
            image_one_start_ray_degrees=0.0,
            target_center=Point2D(x=0.0, y=0.0),
            target_opening_radius_px=1.0,
        )


def test_provenance_values_keep_acquired_and_reference_pixels_distinct() -> None:
    values = {item.value for item in PixelProvenance}
    assert values == {0, 1, 2, 3}
