"""Deterministic SAHI slicing, preprocessing, mapping, and merge tests."""

from __future__ import annotations

import numpy as np
import pytest

from backend.domain.model_bundle import PreprocessingManifest, SahiManifest
from backend.inference.sahi import (
    SahiExecutionConfiguration,
    SahiProcessingError,
    SliceDetection,
    build_slice_windows,
    iter_sahi_batches,
    map_and_merge_detections,
)


def _configuration(
    *,
    batch_size: int = 1,
    color_order: str = "RGB",
    scale: float = 1.0,
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0),
    standard_deviation: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> SahiExecutionConfiguration:
    return SahiExecutionConfiguration(
        manifest=SahiManifest(
            slice_width=1312,
            slice_height=1312,
            overlap_width_ratio=0.5,
            overlap_height_ratio=0.5,
            validated_batch_sizes=(1, 2, 4),
        ),
        preprocessing=PreprocessingManifest.model_validate(
            {
                "schema_version": 1,
                "layout": "NCHW",
                "input_element_type": "float16",
                "color_order": color_order,
                "scale": scale,
                "mean": mean,
                "standard_deviation": standard_deviation,
            }
        ),
        batch_size=batch_size,
        class_count=2,
        merge_overlap_threshold=0.5,
    )


def test_production_geometry_has_exact_row_major_63_window_plan() -> None:
    windows = build_slice_windows(
        source_frame_index=7,
        source_width=6560,
        source_height=4948,
    )

    assert len(windows) == 63
    assert [window.x for window in windows[:9]] == [
        0,
        656,
        1312,
        1968,
        2624,
        3280,
        3936,
        4592,
        5248,
    ]
    assert windows[0].y == 0
    assert windows[-1].x == 5248
    assert windows[-1].y == 3636
    assert windows[-1].valid_width == 1312
    assert windows[-1].valid_height == 1312
    assert [window.slice_index for window in windows] == list(range(63))
    assert all(window.source_frame_index == 7 for window in windows)


def test_small_image_is_deterministically_padded_and_preprocessed_in_memory() -> None:
    image = np.zeros((2, 3, 3), dtype=np.uint8)
    image[0, 0] = (10, 20, 30)
    configuration = _configuration(
        color_order="BGR",
        scale=0.5,
        mean=(1.0, 2.0, 3.0),
        standard_deviation=(2.0, 2.0, 2.0),
    )

    batches = list(iter_sahi_batches(image, source_frame_index=0, configuration=configuration))

    assert len(batches) == 1
    batch = batches[0]
    assert batch.windows[0].valid_width == 3
    assert batch.windows[0].valid_height == 2
    assert batch.tensor.shape == (1, 3, 1312, 1312)
    assert batch.tensor.dtype == np.float16
    assert not batch.tensor.flags.writeable
    assert batch.tensor[0, :, 0, 0].tolist() == [7.0, 4.0, 1.0]
    assert batch.tensor[0, :, 100, 100].tolist() == [-0.5, -1.0, -1.5]


def test_batches_are_bounded_ordered_and_keep_final_partial_batch() -> None:
    image = np.zeros((1312, 2000, 3), dtype=np.uint8)

    batches = list(
        iter_sahi_batches(
            image,
            source_frame_index=2,
            configuration=_configuration(batch_size=2),
        )
    )

    assert len(batches) == 2
    assert [batch.batch_index for batch in batches] == [0, 1]
    assert [len(batch.windows) for batch in batches] == [2, 1]
    assert [window.slice_index for batch in batches for window in batch.windows] == [0, 1, 2]
    assert batches[0].tensor.shape[0] == 2
    assert batches[1].tensor.shape[0] == 1


def test_boundary_crack_partial_and_complete_views_merge_to_full_source_extent() -> None:
    windows = build_slice_windows(
        source_frame_index=3,
        source_width=2000,
        source_height=1312,
    )
    detections = (
        SliceDetection(
            slice_index=0,
            class_index=0,
            confidence=0.80,
            x1=1000.0,
            y1=100.0,
            x2=1312.0,
            y2=120.0,
        ),
        SliceDetection(
            slice_index=2,
            class_index=0,
            confidence=0.95,
            x1=312.0,
            y1=100.0,
            x2=712.0,
            y2=120.0,
        ),
    )

    merged = map_and_merge_detections(
        windows,
        detections,
        source_width=2000,
        source_height=1312,
        class_count=2,
        overlap_threshold=0.5,
    )

    assert len(merged) == 1
    crack = merged[0]
    assert (crack.x1, crack.y1, crack.x2, crack.y2) == (1000.0, 100.0, 1400.0, 120.0)
    assert crack.confidence == 0.95
    assert crack.contributing_slice_indices == (0, 2)


def test_vertical_boundary_crack_merges_without_losing_length() -> None:
    windows = build_slice_windows(
        source_frame_index=4,
        source_width=1312,
        source_height=2000,
    )
    detections = (
        SliceDetection(0, 0, 0.82, 300.0, 1000.0, 325.0, 1312.0),
        SliceDetection(2, 0, 0.96, 300.0, 312.0, 325.0, 712.0),
    )

    merged = map_and_merge_detections(
        windows,
        detections,
        source_width=1312,
        source_height=2000,
        class_count=1,
        overlap_threshold=0.5,
    )

    assert len(merged) == 1
    assert (merged[0].x1, merged[0].y1, merged[0].x2, merged[0].y2) == (
        300.0,
        1000.0,
        325.0,
        1400.0,
    )
    assert merged[0].contributing_slice_indices == (0, 2)


def test_merge_is_class_aware_deterministic_and_preserves_separate_defects() -> None:
    windows = build_slice_windows(
        source_frame_index=0,
        source_width=2000,
        source_height=1312,
    )
    detections = (
        SliceDetection(0, 1, 0.7, 1000.0, 100.0, 1200.0, 130.0),
        SliceDetection(2, 0, 0.9, 312.0, 100.0, 512.0, 130.0),
        SliceDetection(0, 0, 0.8, 1000.0, 100.0, 1200.0, 130.0),
        SliceDetection(0, 0, 0.6, 100.0, 300.0, 180.0, 340.0),
    )

    forward = map_and_merge_detections(
        windows,
        detections,
        source_width=2000,
        source_height=1312,
        class_count=2,
        overlap_threshold=0.5,
    )
    reverse = map_and_merge_detections(
        windows,
        tuple(reversed(detections)),
        source_width=2000,
        source_height=1312,
        class_count=2,
        overlap_threshold=0.5,
    )

    assert forward == reverse
    assert len(forward) == 3
    assert [item.class_index for item in forward] == [0, 0, 1]
    assert forward[1].contributing_slice_indices == (0, 2)


def test_detections_in_padding_are_discarded_and_partial_boxes_are_clipped() -> None:
    windows = build_slice_windows(
        source_frame_index=0,
        source_width=800,
        source_height=600,
    )
    detections = (
        SliceDetection(0, 0, 0.9, 900.0, 100.0, 1000.0, 200.0),
        SliceDetection(0, 0, 0.8, 750.0, 550.0, 900.0, 700.0),
    )

    mapped = map_and_merge_detections(
        windows,
        detections,
        source_width=800,
        source_height=600,
        class_count=1,
        overlap_threshold=0.5,
    )

    assert len(mapped) == 1
    assert (mapped[0].x1, mapped[0].y1, mapped[0].x2, mapped[0].y2) == (
        750.0,
        550.0,
        800.0,
        600.0,
    )


def test_invalid_profile_source_and_decoded_identity_are_rejected() -> None:
    manifest = SahiManifest(
        slice_width=1312,
        slice_height=1312,
        overlap_width_ratio=0.25,
        overlap_height_ratio=0.5,
        validated_batch_sizes=(1,),
    )
    with pytest.raises(ValueError, match="50-percent"):
        SahiExecutionConfiguration(
            manifest=manifest,
            preprocessing=_configuration().preprocessing,
            batch_size=1,
            class_count=1,
            merge_overlap_threshold=0.5,
        )

    with pytest.raises(SahiProcessingError, match="uint8"):
        list(
            iter_sahi_batches(
                np.zeros((10, 10, 3), dtype=np.float32),
                source_frame_index=0,
                configuration=_configuration(),
            )
        )

    windows = build_slice_windows(source_frame_index=0, source_width=1312, source_height=1312)
    with pytest.raises(SahiProcessingError, match="unknown slice"):
        map_and_merge_detections(
            windows,
            (SliceDetection(99, 0, 0.5, 1.0, 1.0, 2.0, 2.0),),
            source_width=1312,
            source_height=1312,
            class_count=1,
            overlap_threshold=0.5,
        )
    with pytest.raises(SahiProcessingError, match="class"):
        map_and_merge_detections(
            windows,
            (SliceDetection(0, 2, 0.5, 1.0, 1.0, 2.0, 2.0),),
            source_width=1312,
            source_height=1312,
            class_count=1,
            overlap_threshold=0.5,
        )
