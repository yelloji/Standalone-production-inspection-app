"""Deterministic bounded SAHI slicing, source mapping, and class-aware merge."""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from backend.domain.model_bundle import PreprocessingManifest, SahiManifest

SLICE_SIZE = 1312
INITIAL_OVERLAP = 0.5


class SahiProcessingError(ValueError):
    """Raised when slicing or decoded detections violate the pipeline contract."""


@dataclass(frozen=True, slots=True)
class SahiExecutionConfiguration:
    manifest: SahiManifest
    preprocessing: PreprocessingManifest
    batch_size: int
    class_count: int
    merge_overlap_threshold: float
    padding_value: int = 0

    def __post_init__(self) -> None:
        if self.manifest.slice_width != SLICE_SIZE or self.manifest.slice_height != SLICE_SIZE:
            raise ValueError("production SAHI slices must be 1312 x 1312")
        if (
            self.manifest.overlap_width_ratio != INITIAL_OVERLAP
            or self.manifest.overlap_height_ratio != INITIAL_OVERLAP
        ):
            raise ValueError("current production SAHI profile requires 50-percent overlap")
        if self.batch_size not in self.manifest.validated_batch_sizes:
            raise ValueError("SAHI batch size is not validated by the model bundle")
        if self.preprocessing.input_element_type != "float16":
            raise ValueError("SAHI preprocessing must produce FP16 input")
        if self.class_count < 1:
            raise ValueError("SAHI requires at least one model class")
        if not 0.0 < self.merge_overlap_threshold <= 1.0:
            raise ValueError("merge overlap threshold must be in (0, 1]")
        if self.padding_value < 0 or self.padding_value > 255:
            raise ValueError("padding value must be an unsigned 8-bit value")


@dataclass(frozen=True, slots=True)
class SliceWindow:
    source_frame_index: int
    slice_index: int
    x: int
    y: int
    valid_width: int
    valid_height: int

    def __post_init__(self) -> None:
        if self.source_frame_index < 0 or self.slice_index < 0:
            raise ValueError("frame and slice indices must be nonnegative")
        if self.x < 0 or self.y < 0:
            raise ValueError("slice origin must be nonnegative")
        if not 1 <= self.valid_width <= SLICE_SIZE:
            raise ValueError("slice valid width is outside the supported range")
        if not 1 <= self.valid_height <= SLICE_SIZE:
            raise ValueError("slice valid height is outside the supported range")


@dataclass(frozen=True, slots=True)
class SahiBatch:
    batch_index: int
    windows: tuple[SliceWindow, ...]
    tensor: npt.NDArray[np.float16]

    def __post_init__(self) -> None:
        if self.batch_index < 0 or not self.windows:
            raise ValueError("SAHI batch identity is invalid")
        if self.tensor.dtype != np.dtype(np.float16):
            raise ValueError("SAHI batch tensor must be FP16")
        if self.tensor.shape != (len(self.windows), 3, SLICE_SIZE, SLICE_SIZE):
            raise ValueError("SAHI batch tensor geometry differs from its windows")
        if not self.tensor.flags.c_contiguous or self.tensor.flags.writeable:
            raise ValueError("SAHI batch tensor must be contiguous and read-only")


@dataclass(frozen=True, slots=True)
class SliceDetection:
    slice_index: int
    class_index: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        values = (self.confidence, self.x1, self.y1, self.x2, self.y2)
        if self.slice_index < 0 or self.class_index < 0:
            raise ValueError("slice and class indices must be nonnegative")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("slice detection values must be finite")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("slice detection confidence must be in [0, 1]")
        if self.x1 < 0.0 or self.y1 < 0.0 or self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("slice detection box is invalid")
        if self.x2 > SLICE_SIZE or self.y2 > SLICE_SIZE:
            raise ValueError("slice detection lies outside the model tile")


@dataclass(frozen=True, slots=True)
class SourceDetection:
    source_frame_index: int
    class_index: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    contributing_slice_indices: tuple[int, ...]


def build_slice_windows(
    *,
    source_frame_index: int,
    source_width: int,
    source_height: int,
) -> tuple[SliceWindow, ...]:
    """Create deterministic row-major windows with far edges anchored."""

    if source_frame_index < 0 or source_width < 1 or source_height < 1:
        raise SahiProcessingError("source frame identity and dimensions must be positive")
    x_positions = _axis_positions(source_width)
    y_positions = _axis_positions(source_height)
    windows: list[SliceWindow] = []
    for y in y_positions:
        for x in x_positions:
            windows.append(
                SliceWindow(
                    source_frame_index=source_frame_index,
                    slice_index=len(windows),
                    x=x,
                    y=y,
                    valid_width=min(SLICE_SIZE, source_width - x),
                    valid_height=min(SLICE_SIZE, source_height - y),
                )
            )
    return tuple(windows)


def iter_sahi_batches(
    image: npt.NDArray[np.uint8],
    *,
    source_frame_index: int,
    configuration: SahiExecutionConfiguration,
) -> Iterator[SahiBatch]:
    """Yield bounded preprocessed batches without writing slice images."""

    if image.dtype != np.dtype(np.uint8) or image.ndim != 3 or image.shape[2] != 3:
        raise SahiProcessingError("SAHI source image must be H x W x 3 uint8")
    source_height, source_width = image.shape[:2]
    windows = build_slice_windows(
        source_frame_index=source_frame_index,
        source_width=source_width,
        source_height=source_height,
    )
    for batch_index, offset in enumerate(range(0, len(windows), configuration.batch_size)):
        selected = windows[offset : offset + configuration.batch_size]
        tensor = np.empty((len(selected), 3, SLICE_SIZE, SLICE_SIZE), dtype=np.float16)
        for index, window in enumerate(selected):
            raw_tile = np.full(
                (SLICE_SIZE, SLICE_SIZE, 3),
                configuration.padding_value,
                dtype=np.uint8,
            )
            raw_tile[: window.valid_height, : window.valid_width] = image[
                window.y : window.y + window.valid_height,
                window.x : window.x + window.valid_width,
            ]
            tensor[index] = _preprocess_tile(raw_tile, configuration.preprocessing)
        tensor.setflags(write=False)
        yield SahiBatch(batch_index=batch_index, windows=selected, tensor=tensor)


def map_and_merge_detections(
    windows: Sequence[SliceWindow],
    detections: Sequence[SliceDetection],
    *,
    source_width: int,
    source_height: int,
    class_count: int,
    overlap_threshold: float,
) -> tuple[SourceDetection, ...]:
    """Clip padding, map to source pixels, then merge same-class overlap."""

    if source_width < 1 or source_height < 1 or class_count < 1:
        raise SahiProcessingError("source dimensions and class count must be positive")
    if not 0.0 < overlap_threshold <= 1.0:
        raise SahiProcessingError("overlap threshold must be in (0, 1]")
    by_index = {window.slice_index: window for window in windows}
    if len(by_index) != len(windows):
        raise SahiProcessingError("slice window indices must be unique")

    mapped = []
    for detection in detections:
        window = by_index.get(detection.slice_index)
        if window is None:
            raise SahiProcessingError("detection references an unknown slice")
        if detection.class_index >= class_count:
            raise SahiProcessingError("detection class is outside the model class range")
        local_x1 = min(max(detection.x1, 0.0), float(window.valid_width))
        local_y1 = min(max(detection.y1, 0.0), float(window.valid_height))
        local_x2 = min(max(detection.x2, 0.0), float(window.valid_width))
        local_y2 = min(max(detection.y2, 0.0), float(window.valid_height))
        if local_x2 <= local_x1 or local_y2 <= local_y1:
            continue
        mapped.append(
            SourceDetection(
                source_frame_index=window.source_frame_index,
                class_index=detection.class_index,
                confidence=detection.confidence,
                x1=float(min(source_width, window.x + local_x1)),
                y1=float(min(source_height, window.y + local_y1)),
                x2=float(min(source_width, window.x + local_x2)),
                y2=float(min(source_height, window.y + local_y2)),
                contributing_slice_indices=(window.slice_index,),
            )
        )
    return _merge_source_detections(mapped, overlap_threshold)


def _axis_positions(length: int) -> tuple[int, ...]:
    if length <= SLICE_SIZE:
        return (0,)
    stride = SLICE_SIZE // 2
    final = length - SLICE_SIZE
    positions = list(range(0, final + 1, stride))
    if positions[-1] != final:
        positions.append(final)
    return tuple(positions)


def _preprocess_tile(
    raw_tile: npt.NDArray[np.uint8],
    preprocessing: PreprocessingManifest,
) -> npt.NDArray[np.float16]:
    pixels = raw_tile
    if preprocessing.color_order == "BGR":
        pixels = raw_tile[..., ::-1]
    normalized = pixels.astype(np.float32)
    normalized *= np.float32(preprocessing.scale)
    normalized -= np.asarray(preprocessing.mean, dtype=np.float32)
    normalized /= np.asarray(preprocessing.standard_deviation, dtype=np.float32)
    return np.asarray(normalized.transpose(2, 0, 1), dtype=np.float16)


def _merge_source_detections(
    detections: Sequence[SourceDetection],
    threshold: float,
) -> tuple[SourceDetection, ...]:
    pending = sorted(
        detections,
        key=lambda item: (
            item.source_frame_index,
            item.class_index,
            -item.confidence,
            item.x1,
            item.y1,
            item.x2,
            item.y2,
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
                same_group = (
                    candidate.source_frame_index == current.source_frame_index
                    and candidate.class_index == current.class_index
                )
                if same_group and _overlap_score(current, candidate) >= threshold:
                    current = SourceDetection(
                        source_frame_index=current.source_frame_index,
                        class_index=current.class_index,
                        confidence=max(current.confidence, candidate.confidence),
                        x1=min(current.x1, candidate.x1),
                        y1=min(current.y1, candidate.y1),
                        x2=max(current.x2, candidate.x2),
                        y2=max(current.y2, candidate.y2),
                        contributing_slice_indices=tuple(
                            sorted(
                                set(current.contributing_slice_indices)
                                | set(candidate.contributing_slice_indices)
                            )
                        ),
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
                item.source_frame_index,
                item.class_index,
                item.x1,
                item.y1,
                -item.confidence,
            ),
        )
    )


def _overlap_score(first: SourceDetection, second: SourceDetection) -> float:
    intersection_width = max(0.0, min(first.x2, second.x2) - max(first.x1, second.x1))
    intersection_height = max(0.0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection = intersection_width * intersection_height
    if intersection <= 0.0:
        return 0.0
    first_area = (first.x2 - first.x1) * (first.y2 - first.y1)
    second_area = (second.x2 - second.x1) * (second.y2 - second.y1)
    union = first_area + second_area - intersection
    return max(intersection / union, intersection / min(first_area, second_area))
