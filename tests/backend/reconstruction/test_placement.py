"""Nominal angular placement tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from backend.domain.reconstruction import TransformSetContract
from backend.reconstruction.placement import (
    PlacementFailure,
    build_nominal_transform_set,
    frame_output_bounds,
    map_points,
)
from tests.backend.reconstruction.factories import acquisition_manifest, calibration


def transform_set() -> TransformSetContract:
    return build_nominal_transform_set(
        acquisition_manifest(),
        calibration(),
        calibration_relative_path="processing/acquisition-001/calibration.json",
        mask_directory_relative_path="processing/acquisition-001/masks",
    )


def test_builds_complete_nominal_transform_set() -> None:
    result = transform_set()
    assert [item.frame_position for item in result.transforms] == list(range(1, 17))
    assert [item.nominal_angle_degrees for item in result.transforms] == [
        index * 22.5 for index in range(16)
    ]
    assert len({item.valid_mask_relative_path for item in result.transforms}) == 16


def test_inverse_rotation_maps_same_physical_point_together() -> None:
    result = transform_set()
    source_center = np.asarray((100.0, -500.0))
    point_frame_one = np.asarray(((120.0, 150.0),))
    radians = math.radians(-22.5)
    rotation = np.asarray(
        (
            (math.cos(radians), -math.sin(radians)),
            (math.sin(radians), math.cos(radians)),
        )
    )
    point_frame_two = (point_frame_one - source_center) @ rotation.T + source_center
    canonical_one = map_points(
        result.transforms[0].source_to_output_matrix,
        point_frame_one,
    )
    canonical_two = map_points(
        result.transforms[1].source_to_output_matrix,
        point_frame_two,
    )
    assert canonical_two == pytest.approx(canonical_one, abs=1e-9)


def test_transforms_round_trip_and_have_clipped_bounds() -> None:
    current_calibration = calibration()
    points = np.asarray(((0.0, 100.0), (100.0, 150.0), (199.0, 199.0)))
    for transform in transform_set().transforms:
        output = map_points(transform.source_to_output_matrix, points)
        restored = map_points(transform.output_to_source_matrix, output)
        assert np.max(np.abs(restored - points)) < 1e-9
        left, top, right, bottom = frame_output_bounds(current_calibration, transform)
        assert 0 <= left < right <= current_calibration.output_width
        assert 0 <= top < bottom <= current_calibration.output_height


def test_rejects_mismatched_contracts_and_invalid_points() -> None:
    other = calibration().model_copy(update={"acquisition_id": "other"})
    with pytest.raises(PlacementFailure, match="IDs"):
        build_nominal_transform_set(
            acquisition_manifest(),
            other,
            calibration_relative_path="processing/calibration.json",
            mask_directory_relative_path="processing/masks",
        )
    with pytest.raises(PlacementFailure, match="N x 2"):
        map_points(np.eye(3), np.asarray((1.0, 2.0)))
    with pytest.raises(PlacementFailure, match="infinity"):
        map_points(((1, 0, 0), (0, 1, 0), (0, 0, 0)), ((1.0, 2.0),))
