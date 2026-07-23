"""Deterministic spatial separation of fit and held-out reconstruction evidence."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

PointArray = npt.NDArray[np.float64]


class DenseEvidenceFailure(ValueError):
    """Raised when dense evidence cannot support independent validation."""


def _points(value: npt.ArrayLike, name: str) -> PointArray:
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise DenseEvidenceFailure(f"{name} must be an N x 2 point array")
    if not np.isfinite(points).all():
        raise DenseEvidenceFailure(f"{name} must contain only finite coordinates")
    result = points.copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class DensePairEvidence:
    source_frame: int
    target_frame: int
    fit_source_points: PointArray
    fit_target_points: PointArray
    validation_source_points: PointArray
    validation_target_points: PointArray

    def __post_init__(self) -> None:
        for field_name in (
            "fit_source_points",
            "fit_target_points",
            "validation_source_points",
            "validation_target_points",
        ):
            object.__setattr__(self, field_name, _points(getattr(self, field_name), field_name))
        if len(self.fit_source_points) != len(self.fit_target_points):
            raise DenseEvidenceFailure("fit source and target counts must match")
        if len(self.validation_source_points) != len(self.validation_target_points):
            raise DenseEvidenceFailure("validation source and target counts must match")
        if len(self.fit_source_points) < 4:
            raise DenseEvidenceFailure("projective fitting requires at least four fit points")

    @property
    def pair_name(self) -> str:
        return f"{self.source_frame}->{self.target_frame}"


def _bounded_indices(indices: npt.NDArray[np.int64], maximum: int) -> npt.NDArray[np.int64]:
    if len(indices) <= maximum:
        return indices
    positions = np.linspace(0, len(indices) - 1, maximum, dtype=np.int64)
    return indices[positions]


def split_spatial_evidence(
    *,
    source_frame: int,
    target_frame: int,
    source_points: npt.ArrayLike,
    target_points: npt.ArrayLike,
    tile_size: int = 256,
    validation_stride: int = 5,
    maximum_fit_points: int = 300,
    maximum_validation_points: int = 100,
) -> DensePairEvidence:
    """Reserve spatially ordered evidence before any projective fit."""

    source = _points(source_points, "source_points")
    target = _points(target_points, "target_points")
    if len(source) != len(target):
        raise DenseEvidenceFailure("source and target correspondence counts must match")
    if len(source) < 10:
        raise DenseEvidenceFailure("at least ten correspondences are required for fit/validation")
    if tile_size <= 0 or validation_stride < 2:
        raise DenseEvidenceFailure("spatial split parameters are outside the safe range")
    if maximum_fit_points < 4 or maximum_validation_points < 1:
        raise DenseEvidenceFailure("evidence limits are outside the safe range")

    order = np.lexsort(
        (
            source[:, 0],
            source[:, 1],
            np.floor(source[:, 0] / tile_size),
            np.floor(source[:, 1] / tile_size),
        )
    )
    ordinal = np.arange(len(order))
    validation = order[ordinal % validation_stride == 0]
    fit = order[ordinal % validation_stride != 0]
    fit = _bounded_indices(fit.astype(np.int64), maximum_fit_points)
    validation = _bounded_indices(validation.astype(np.int64), maximum_validation_points)
    if len(validation) < 2:
        raise DenseEvidenceFailure("spatial split produced insufficient held-out evidence")
    return DensePairEvidence(
        source_frame=source_frame,
        target_frame=target_frame,
        fit_source_points=source[fit],
        fit_target_points=target[fit],
        validation_source_points=source[validation],
        validation_target_points=target[validation],
    )
