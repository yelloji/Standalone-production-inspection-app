"""Project source predictions, clip to acquired provenance, and deduplicate."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw

from backend.domain.center_completion import PixelProvenance
from backend.domain.reconstruction import Matrix3x3
from backend.reconstruction.placement import map_points


class PredictionProjectionError(ValueError):
    """Raised when prediction geometry or provenance is unsafe."""


@dataclass(frozen=True, slots=True)
class SourceMask:
    x: int
    y: int
    values: npt.NDArray[np.bool_]

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("source mask origin must be nonnegative")
        if self.values.dtype != np.dtype(np.bool_) or self.values.ndim != 2:
            raise ValueError("source mask must be a two-dimensional boolean array")
        if self.values.size == 0 or not np.any(self.values):
            raise ValueError("source mask must contain at least one positive pixel")
        immutable = np.array(self.values, dtype=np.bool_, copy=True, order="C")
        immutable.setflags(write=False)
        object.__setattr__(self, "values", immutable)


@dataclass(frozen=True, slots=True)
class SourcePrediction:
    source_prediction_id: str
    source_frame_index: int
    class_index: int
    confidence: float
    box: tuple[float, float, float, float]
    contributing_slice_indices: tuple[int, ...]
    polygon: tuple[tuple[float, float], ...] | None = None
    mask: SourceMask | None = None

    def __post_init__(self) -> None:
        if not self.source_prediction_id.strip():
            raise ValueError("source prediction identifier must not be empty")
        if self.source_frame_index < 0 or self.class_index < 0:
            raise ValueError("source frame and class indices must be nonnegative")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("source prediction confidence must be in [0, 1]")
        x1, y1, x2, y2 = self.box
        if (
            not all(math.isfinite(value) for value in self.box)
            or x1 < 0.0
            or y1 < 0.0
            or x2 <= x1
            or y2 <= y1
        ):
            raise ValueError("source prediction box is invalid")
        if not self.contributing_slice_indices or any(
            index < 0 for index in self.contributing_slice_indices
        ):
            raise ValueError("source prediction requires nonnegative slice evidence")
        if len(set(self.contributing_slice_indices)) != len(self.contributing_slice_indices):
            raise ValueError("source prediction slice evidence must be unique")
        if self.polygon is not None:
            if len(self.polygon) < 3:
                raise ValueError("source prediction polygon requires at least three points")
            if not all(math.isfinite(coordinate) for point in self.polygon for coordinate in point):
                raise ValueError("source prediction polygon must be finite")


@dataclass(frozen=True, slots=True)
class FrameProjection:
    source_frame_index: int
    source_width: int
    source_height: int
    source_to_canvas_matrix: Matrix3x3

    def __post_init__(self) -> None:
        if self.source_frame_index < 0 or self.source_width < 1 or self.source_height < 1:
            raise ValueError("frame projection identity and dimensions are invalid")
        matrix = np.asarray(self.source_to_canvas_matrix, dtype=np.float64)
        if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
            raise ValueError("frame projection requires a finite 3 x 3 matrix")
        if abs(np.linalg.det(matrix)) < 1e-12:
            raise ValueError("frame projection matrix must be invertible")


@dataclass(frozen=True, slots=True)
class ProjectionConfiguration:
    class_count: int
    duplicate_overlap_threshold: float
    maximum_footprint_pixels: int = 4_194_304
    maximum_total_footprint_pixels: int = 67_108_864

    def __post_init__(self) -> None:
        if self.class_count < 1:
            raise ValueError("projection requires at least one class")
        if not 0.0 < self.duplicate_overlap_threshold <= 1.0:
            raise ValueError("duplicate threshold must be in (0, 1]")
        if self.maximum_footprint_pixels < 1:
            raise ValueError("maximum footprint pixels must be positive")
        if self.maximum_total_footprint_pixels < self.maximum_footprint_pixels:
            raise ValueError("total footprint bound must cover at least one footprint")


@dataclass(frozen=True, slots=True)
class PredictionEvidenceLink:
    source_prediction_id: str
    source_frame_index: int
    source_box: tuple[float, float, float, float]
    contributing_slice_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AcquiredFootprint:
    x: int
    y: int
    values: npt.NDArray[np.bool_]

    def __post_init__(self) -> None:
        immutable = np.array(self.values, dtype=np.bool_, copy=True, order="C")
        if immutable.ndim != 2 or immutable.size == 0 or not np.any(immutable):
            raise ValueError("acquired footprint must contain positive pixels")
        immutable.setflags(write=False)
        object.__setattr__(self, "values", immutable)


@dataclass(frozen=True, slots=True)
class ProjectedPrediction:
    disc_prediction_id: str
    class_index: int
    confidence: float
    disc_box: tuple[float, float, float, float]
    projected_polygon: tuple[tuple[float, float], ...]
    acquired_footprint: AcquiredFootprint
    evidence_links: tuple[PredictionEvidenceLink, ...]


def project_and_deduplicate_predictions(
    predictions: tuple[SourcePrediction, ...],
    frame_projections: tuple[FrameProjection, ...],
    provenance: npt.NDArray[np.uint8],
    configuration: ProjectionConfiguration,
) -> tuple[ProjectedPrediction, ...]:
    """Project all evidence and merge duplicate acquired footprints by class."""

    if provenance.dtype != np.dtype(np.uint8) or provenance.ndim != 2:
        raise PredictionProjectionError("provenance must be a two-dimensional uint8 map")
    _validate_provenance_values(provenance)
    projection_by_frame = {
        projection.source_frame_index: projection for projection in frame_projections
    }
    if sorted(projection_by_frame) != list(range(16)):
        raise PredictionProjectionError("projection requires unique frame indices 0 through 15")
    prediction_ids = [prediction.source_prediction_id for prediction in predictions]
    if len(set(prediction_ids)) != len(prediction_ids):
        raise PredictionProjectionError("source prediction identifiers must be unique")

    projected = []
    total_footprint_pixels = 0
    for prediction in predictions:
        if prediction.class_index >= configuration.class_count:
            raise PredictionProjectionError("prediction class is outside the model range")
        frame = projection_by_frame.get(prediction.source_frame_index)
        if frame is None:
            raise PredictionProjectionError("prediction references an unknown frame")
        _validate_source_bounds(prediction, frame)
        item = _project_prediction(prediction, frame, provenance, configuration)
        if item is not None:
            total_footprint_pixels += item.acquired_footprint.values.size
            if total_footprint_pixels > configuration.maximum_total_footprint_pixels:
                raise PredictionProjectionError(
                    "projected prediction footprints exceed the total memory bound"
                )
            projected.append(item)
    return _deduplicate(projected, configuration)


def _project_prediction(
    prediction: SourcePrediction,
    frame: FrameProjection,
    provenance: npt.NDArray[np.uint8],
    configuration: ProjectionConfiguration,
) -> ProjectedPrediction | None:
    source_polygon = (
        prediction.polygon if prediction.polygon is not None else _box_polygon(prediction.box)
    )
    mapped_polygon_array = map_points(
        frame.source_to_canvas_matrix,
        np.asarray(source_polygon, dtype=np.float64),
    )
    mapped_polygon = tuple((float(point[0]), float(point[1])) for point in mapped_polygon_array)
    if prediction.mask is None:
        origin_x, origin_y, footprint = _rasterize_polygon(
            mapped_polygon,
            provenance.shape[1],
            provenance.shape[0],
            configuration.maximum_footprint_pixels,
        )
    else:
        origin_x, origin_y, footprint = _warp_source_mask(
            prediction.mask,
            frame.source_to_canvas_matrix,
            provenance.shape[1],
            provenance.shape[0],
            configuration.maximum_footprint_pixels,
        )
    if footprint.size == 0:
        return None
    acquired = (
        provenance[
            origin_y : origin_y + footprint.shape[0],
            origin_x : origin_x + footprint.shape[1],
        ]
        == PixelProvenance.ACQUIRED.value
    )
    footprint &= acquired
    trimmed = _trim_footprint(origin_x, origin_y, footprint)
    if trimmed is None:
        return None
    acquired_footprint = AcquiredFootprint(*trimmed)
    box = _footprint_box(acquired_footprint)
    link = PredictionEvidenceLink(
        source_prediction_id=prediction.source_prediction_id,
        source_frame_index=prediction.source_frame_index,
        source_box=prediction.box,
        contributing_slice_indices=prediction.contributing_slice_indices,
    )
    return ProjectedPrediction(
        disc_prediction_id=_prediction_id(prediction.class_index, (link,)),
        class_index=prediction.class_index,
        confidence=prediction.confidence,
        disc_box=box,
        projected_polygon=mapped_polygon,
        acquired_footprint=acquired_footprint,
        evidence_links=(link,),
    )


def _rasterize_polygon(
    polygon: tuple[tuple[float, float], ...],
    canvas_width: int,
    canvas_height: int,
    maximum_pixels: int,
) -> tuple[int, int, npt.NDArray[np.bool_]]:
    bounds = _clipped_bounds(polygon, canvas_width, canvas_height)
    if bounds is None:
        return 0, 0, np.zeros((0, 0), dtype=np.bool_)
    left, top, right, bottom = bounds
    _enforce_footprint_limit(right - left, bottom - top, maximum_pixels)
    image = Image.new("L", (right - left, bottom - top), 0)
    ImageDraw.Draw(image).polygon(
        [(x - left, y - top) for x, y in polygon],
        fill=255,
    )
    return left, top, np.asarray(image, dtype=np.uint8) > 0


def _warp_source_mask(
    source_mask: SourceMask,
    source_to_canvas_matrix: Matrix3x3,
    canvas_width: int,
    canvas_height: int,
    maximum_pixels: int,
) -> tuple[int, int, npt.NDArray[np.bool_]]:
    height, width = source_mask.values.shape
    mask_to_source = np.asarray(
        (
            (1.0, 0.0, source_mask.x),
            (0.0, 1.0, source_mask.y),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    mask_to_canvas = np.asarray(source_to_canvas_matrix, dtype=np.float64) @ mask_to_source
    corners = map_points(
        mask_to_canvas,
        np.asarray(((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))),
    )
    polygon = tuple((float(point[0]), float(point[1])) for point in corners)
    bounds = _clipped_bounds(polygon, canvas_width, canvas_height)
    if bounds is None:
        return 0, 0, np.zeros((0, 0), dtype=np.bool_)
    left, top, right, bottom = bounds
    _enforce_footprint_limit(right - left, bottom - top, maximum_pixels)
    canvas_to_mask = np.linalg.inv(mask_to_canvas)
    local_to_canvas = np.asarray(
        ((1.0, 0.0, left), (0.0, 1.0, top), (0.0, 0.0, 1.0)),
        dtype=np.float64,
    )
    coefficients = canvas_to_mask @ local_to_canvas
    coefficients /= coefficients[2, 2]
    pil_coefficients = (
        float(coefficients[0, 0]),
        float(coefficients[0, 1]),
        float(coefficients[0, 2]),
        float(coefficients[1, 0]),
        float(coefficients[1, 1]),
        float(coefficients[1, 2]),
        float(coefficients[2, 0]),
        float(coefficients[2, 1]),
    )
    image = Image.fromarray(source_mask.values.astype(np.uint8) * 255)
    warped = image.transform(
        (right - left, bottom - top),
        Image.Transform.PERSPECTIVE,
        pil_coefficients,
        resample=Image.Resampling.NEAREST,
        fillcolor=0,
    )
    return left, top, np.asarray(warped, dtype=np.uint8) > 0


def _deduplicate(
    predictions: list[ProjectedPrediction],
    configuration: ProjectionConfiguration,
) -> tuple[ProjectedPrediction, ...]:
    pending = sorted(
        predictions,
        key=lambda item: (
            item.class_index,
            -item.confidence,
            item.disc_box,
            item.disc_prediction_id,
        ),
    )
    merged = []
    while pending:
        current = pending.pop(0)
        changed = True
        while changed:
            changed = False
            retained = []
            for candidate in pending:
                if (
                    candidate.class_index == current.class_index
                    and _footprint_overlap(current, candidate)
                    >= configuration.duplicate_overlap_threshold
                ):
                    current = _merge_pair(
                        current,
                        candidate,
                        configuration.maximum_footprint_pixels,
                    )
                    changed = True
                else:
                    retained.append(candidate)
            pending = retained
        merged.append(current)
    return tuple(
        sorted(
            merged,
            key=lambda item: (
                item.class_index,
                item.disc_box,
                -item.confidence,
                item.disc_prediction_id,
            ),
        )
    )


def _merge_pair(
    first: ProjectedPrediction,
    second: ProjectedPrediction,
    maximum_pixels: int,
) -> ProjectedPrediction:
    left = min(first.acquired_footprint.x, second.acquired_footprint.x)
    top = min(first.acquired_footprint.y, second.acquired_footprint.y)
    right = max(
        first.acquired_footprint.x + first.acquired_footprint.values.shape[1],
        second.acquired_footprint.x + second.acquired_footprint.values.shape[1],
    )
    bottom = max(
        first.acquired_footprint.y + first.acquired_footprint.values.shape[0],
        second.acquired_footprint.y + second.acquired_footprint.values.shape[0],
    )
    _enforce_footprint_limit(right - left, bottom - top, maximum_pixels)
    values = np.zeros((bottom - top, right - left), dtype=np.bool_)
    for footprint in (first.acquired_footprint, second.acquired_footprint):
        y = footprint.y - top
        x = footprint.x - left
        values[y : y + footprint.values.shape[0], x : x + footprint.values.shape[1]] |= (
            footprint.values
        )
    combined = AcquiredFootprint(left, top, values)
    links = tuple(
        sorted(
            first.evidence_links + second.evidence_links,
            key=lambda item: (item.source_frame_index, item.source_prediction_id),
        )
    )
    polygon = _convex_hull(first.projected_polygon + second.projected_polygon)
    return ProjectedPrediction(
        disc_prediction_id=_prediction_id(first.class_index, links),
        class_index=first.class_index,
        confidence=max(first.confidence, second.confidence),
        disc_box=_footprint_box(combined),
        projected_polygon=polygon,
        acquired_footprint=combined,
        evidence_links=links,
    )


def _footprint_overlap(first: ProjectedPrediction, second: ProjectedPrediction) -> float:
    a = first.acquired_footprint
    b = second.acquired_footprint
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.x + a.values.shape[1], b.x + b.values.shape[1])
    bottom = min(a.y + a.values.shape[0], b.y + b.values.shape[0])
    if right <= left or bottom <= top:
        return 0.0
    a_crop = a.values[top - a.y : bottom - a.y, left - a.x : right - a.x]
    b_crop = b.values[top - b.y : bottom - b.y, left - b.x : right - b.x]
    intersection = int(np.count_nonzero(a_crop & b_crop))
    if intersection == 0:
        return 0.0
    a_area = int(np.count_nonzero(a.values))
    b_area = int(np.count_nonzero(b.values))
    union = a_area + b_area - intersection
    return max(intersection / union, intersection / min(a_area, b_area))


def _validate_source_bounds(prediction: SourcePrediction, frame: FrameProjection) -> None:
    points = list(_box_polygon(prediction.box))
    if prediction.polygon is not None:
        points.extend(prediction.polygon)
    if any(
        x < 0.0 or y < 0.0 or x > frame.source_width or y > frame.source_height for x, y in points
    ):
        raise PredictionProjectionError("prediction geometry lies outside its source frame")
    if prediction.mask is not None and (
        prediction.mask.x + prediction.mask.values.shape[1] > frame.source_width
        or prediction.mask.y + prediction.mask.values.shape[0] > frame.source_height
    ):
        raise PredictionProjectionError("prediction mask lies outside its source frame")


def _clipped_bounds(
    polygon: tuple[tuple[float, float], ...],
    canvas_width: int,
    canvas_height: int,
) -> tuple[int, int, int, int] | None:
    left = max(0, math.floor(min(point[0] for point in polygon)))
    top = max(0, math.floor(min(point[1] for point in polygon)))
    right = min(canvas_width, math.ceil(max(point[0] for point in polygon)))
    bottom = min(canvas_height, math.ceil(max(point[1] for point in polygon)))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _trim_footprint(
    origin_x: int,
    origin_y: int,
    values: npt.NDArray[np.bool_],
) -> tuple[int, int, npt.NDArray[np.bool_]] | None:
    rows, columns = np.nonzero(values)
    if not len(rows):
        return None
    left = int(columns.min())
    right = int(columns.max()) + 1
    top = int(rows.min())
    bottom = int(rows.max()) + 1
    return origin_x + left, origin_y + top, values[top:bottom, left:right]


def _footprint_box(footprint: AcquiredFootprint) -> tuple[float, float, float, float]:
    return (
        float(footprint.x),
        float(footprint.y),
        float(footprint.x + footprint.values.shape[1]),
        float(footprint.y + footprint.values.shape[0]),
    )


def _box_polygon(
    box: tuple[float, float, float, float],
) -> tuple[tuple[float, float], ...]:
    x1, y1, x2, y2 = box
    return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))


def _enforce_footprint_limit(width: int, height: int, maximum_pixels: int) -> None:
    if width < 1 or height < 1 or width * height > maximum_pixels:
        raise PredictionProjectionError("projected footprint exceeds its safe bound")


def _validate_provenance_values(provenance: npt.NDArray[np.uint8]) -> None:
    allowed = {item.value for item in PixelProvenance}
    rows_per_chunk = max(1, 1_048_576 // max(1, provenance.shape[1]))
    for row in range(0, provenance.shape[0], rows_per_chunk):
        values = np.unique(provenance[row : row + rows_per_chunk])
        if not set(int(value) for value in values).issubset(allowed):
            raise PredictionProjectionError("provenance contains an unknown pixel value")


def _prediction_id(
    class_index: int,
    links: tuple[PredictionEvidenceLink, ...],
) -> str:
    identity = "|".join(f"{link.source_frame_index}:{link.source_prediction_id}" for link in links)
    digest = hashlib.sha256(f"{class_index}|{identity}".encode()).hexdigest()[:24]
    return f"disc-prediction-{digest}"


def _convex_hull(
    points: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    unique = sorted(set(points))
    if len(unique) <= 2:
        return cast(tuple[tuple[float, float], ...], tuple(unique))

    def cross(
        origin: tuple[float, float],
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (
            second[0] - origin[0]
        )

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return tuple(lower[:-1] + upper[:-1])
