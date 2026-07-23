"""Prediction projection, provenance clipping, and 16-view deduplication tests."""

from __future__ import annotations

import numpy as np
import pytest

from backend.domain.center_completion import PixelProvenance
from backend.inference.projection import (
    FrameProjection,
    PredictionProjectionError,
    ProjectionConfiguration,
    SourceMask,
    SourcePrediction,
    project_and_deduplicate_predictions,
)

IDENTITY = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


def _projections(
    matrix: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ] = IDENTITY,
) -> tuple[FrameProjection, ...]:
    return tuple(
        FrameProjection(
            source_frame_index=index,
            source_width=100,
            source_height=100,
            source_to_canvas_matrix=matrix,
        )
        for index in range(16)
    )


def _configuration(
    *,
    class_count: int = 2,
    maximum_pixels: int = 10_000,
    maximum_total_pixels: int = 100_000,
) -> ProjectionConfiguration:
    return ProjectionConfiguration(
        class_count=class_count,
        duplicate_overlap_threshold=0.5,
        maximum_footprint_pixels=maximum_pixels,
        maximum_total_footprint_pixels=maximum_total_pixels,
    )


def _prediction(
    frame: int,
    *,
    identifier: str | None = None,
    class_index: int = 0,
    box: tuple[float, float, float, float] = (20.0, 20.0, 40.0, 40.0),
    polygon: tuple[tuple[float, float], ...] | None = None,
    mask: SourceMask | None = None,
) -> SourcePrediction:
    return SourcePrediction(
        source_prediction_id=identifier or f"source-{frame:02d}",
        source_frame_index=frame,
        class_index=class_index,
        confidence=0.8 + frame / 100,
        box=box,
        contributing_slice_indices=(frame, frame + 1),
        polygon=polygon,
        mask=mask,
    )


def test_sixteen_duplicate_views_become_one_disc_result_with_all_evidence() -> None:
    provenance = np.full((100, 100), PixelProvenance.ACQUIRED.value, dtype=np.uint8)
    predictions = tuple(_prediction(frame) for frame in range(16))

    result = project_and_deduplicate_predictions(
        predictions,
        _projections(),
        provenance,
        _configuration(),
    )

    assert len(result) == 1
    disc = result[0]
    assert disc.class_index == 0
    assert disc.confidence == pytest.approx(0.95)
    assert disc.disc_box == (20.0, 20.0, 40.0, 40.0)
    assert disc.acquired_footprint.values.shape == (20, 20)
    assert len(disc.evidence_links) == 16
    assert [link.source_frame_index for link in disc.evidence_links] == list(range(16))
    assert all(link.contributing_slice_indices for link in disc.evidence_links)


def test_reference_pixels_clip_geometry_and_reference_only_result_is_discarded() -> None:
    provenance = np.full((100, 100), PixelProvenance.REFERENCE_FILL.value, dtype=np.uint8)
    provenance[:, :30] = PixelProvenance.ACQUIRED.value

    clipped = project_and_deduplicate_predictions(
        (_prediction(0),),
        _projections(),
        provenance,
        _configuration(),
    )
    discarded = project_and_deduplicate_predictions(
        (_prediction(0, box=(40.0, 20.0, 60.0, 40.0)),),
        _projections(),
        provenance,
        _configuration(),
    )

    assert len(clipped) == 1
    assert clipped[0].disc_box == (20.0, 20.0, 30.0, 40.0)
    assert np.all(clipped[0].acquired_footprint.values)
    assert discarded == ()


def test_polygon_and_sparse_mask_follow_saved_projective_transform() -> None:
    matrix = (
        (1.0, 0.0, 10.0),
        (0.0, 1.0, 20.0),
        (0.001, 0.0, 1.0),
    )
    provenance = np.full((140, 140), PixelProvenance.ACQUIRED.value, dtype=np.uint8)
    mask_values = np.zeros((10, 10), dtype=np.bool_)
    mask_values[2:8, 3:7] = True
    prediction = _prediction(
        0,
        box=(5.0, 6.0, 15.0, 16.0),
        polygon=((5.0, 6.0), (15.0, 6.0), (10.0, 16.0)),
        mask=SourceMask(x=5, y=6, values=mask_values),
    )

    result = project_and_deduplicate_predictions(
        (prediction,),
        _projections(matrix),
        provenance,
        _configuration(),
    )

    assert len(result) == 1
    projected = result[0]
    assert projected.projected_polygon[0] == pytest.approx((15.0 / 1.005, 26.0 / 1.005))
    assert np.count_nonzero(projected.acquired_footprint.values) > 0
    assert projected.disc_box[0] >= 0
    assert projected.evidence_links[0].source_prediction_id == "source-00"


def test_deduplication_is_deterministic_and_strictly_class_aware() -> None:
    provenance = np.full((100, 100), PixelProvenance.ACQUIRED.value, dtype=np.uint8)
    predictions = (
        _prediction(0, identifier="crack-a", class_index=0),
        _prediction(1, identifier="crack-b", class_index=0),
        _prediction(2, identifier="mark-a", class_index=1),
    )

    forward = project_and_deduplicate_predictions(
        predictions,
        _projections(),
        provenance,
        _configuration(),
    )
    reverse = project_and_deduplicate_predictions(
        tuple(reversed(predictions)),
        _projections(),
        provenance,
        _configuration(),
    )

    assert [
        (
            item.disc_prediction_id,
            item.class_index,
            item.disc_box,
            item.evidence_links,
        )
        for item in forward
    ] == [
        (
            item.disc_prediction_id,
            item.class_index,
            item.disc_box,
            item.evidence_links,
        )
        for item in reverse
    ]
    assert all(
        np.array_equal(first.acquired_footprint.values, second.acquired_footprint.values)
        for first, second in zip(forward, reverse, strict=True)
    )
    assert len(forward) == 2
    assert [item.class_index for item in forward] == [0, 1]
    assert len(forward[0].evidence_links) == 2
    assert len(forward[1].evidence_links) == 1


def test_nonoverlapping_same_class_defects_remain_separate() -> None:
    provenance = np.full((100, 100), PixelProvenance.ACQUIRED.value, dtype=np.uint8)
    predictions = (
        _prediction(0, identifier="left", box=(5.0, 5.0, 15.0, 15.0)),
        _prediction(1, identifier="right", box=(70.0, 70.0, 80.0, 80.0)),
    )

    result = project_and_deduplicate_predictions(
        predictions,
        _projections(),
        provenance,
        _configuration(),
    )

    assert len(result) == 2
    assert [item.disc_box for item in result] == [
        (5.0, 5.0, 15.0, 15.0),
        (70.0, 70.0, 80.0, 80.0),
    ]


def test_invalid_provenance_frame_class_identity_and_bounds_are_rejected() -> None:
    provenance = np.full((100, 100), PixelProvenance.ACQUIRED.value, dtype=np.uint8)
    invalid_provenance = provenance.copy()
    invalid_provenance[0, 0] = 99
    with pytest.raises(PredictionProjectionError, match="provenance"):
        project_and_deduplicate_predictions(
            (_prediction(0),),
            _projections(),
            invalid_provenance,
            _configuration(),
        )
    with pytest.raises(PredictionProjectionError, match="0 through 15"):
        project_and_deduplicate_predictions(
            (_prediction(0),),
            _projections()[:-1],
            provenance,
            _configuration(),
        )
    with pytest.raises(PredictionProjectionError, match="class"):
        project_and_deduplicate_predictions(
            (_prediction(0, class_index=2),),
            _projections(),
            provenance,
            _configuration(),
        )
    with pytest.raises(PredictionProjectionError, match="outside"):
        project_and_deduplicate_predictions(
            (_prediction(0, box=(90.0, 90.0, 110.0, 110.0)),),
            _projections(),
            provenance,
            _configuration(),
        )
    duplicate = _prediction(0, identifier="duplicate")
    with pytest.raises(PredictionProjectionError, match="identifiers"):
        project_and_deduplicate_predictions(
            (duplicate, duplicate),
            _projections(),
            provenance,
            _configuration(),
        )


def test_oversized_projected_footprint_fails_before_large_allocation() -> None:
    provenance = np.full((100, 100), PixelProvenance.ACQUIRED.value, dtype=np.uint8)

    with pytest.raises(PredictionProjectionError, match="safe bound"):
        project_and_deduplicate_predictions(
            (_prediction(0, box=(10.0, 10.0, 90.0, 90.0)),),
            _projections(),
            provenance,
            _configuration(maximum_pixels=100),
        )

    with pytest.raises(PredictionProjectionError, match="total memory"):
        project_and_deduplicate_predictions(
            (
                _prediction(0, identifier="first", box=(0.0, 0.0, 10.0, 10.0)),
                _prediction(1, identifier="second", box=(20.0, 20.0, 30.0, 30.0)),
            ),
            _projections(),
            provenance,
            _configuration(maximum_pixels=100, maximum_total_pixels=150),
        )
