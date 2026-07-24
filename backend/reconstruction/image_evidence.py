"""Deterministic image registration for adjacent frames in a 16-image cycle."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import cv2
import numpy as np
import numpy.typing as npt
from PIL import Image, UnidentifiedImageError

from backend.reconstruction.dense_evidence import DensePairEvidence, split_spatial_evidence

FRAME_COUNT = 16
ProgressCallback = Callable[[int, int], None]
CancellationCheck = Callable[[], bool]
RegistrationChannel = Literal["gray", "blue", "green", "red", "saturation"]


class ImageEvidenceFailure(RuntimeError):
    """Raised when source images cannot produce trustworthy registration evidence."""


class ImageEvidenceCancelled(ImageEvidenceFailure):
    """Raised when a caller cancels evidence extraction."""


@dataclass(frozen=True, slots=True)
class ImageEvidenceProfile:
    profile_id: str = "brake-disc-image-evidence-v1"
    working_scale: float = 0.25
    excluded_top_fraction: float = 0.18
    feature_channel: RegistrationChannel = "gray"
    flow_channels: tuple[RegistrationChannel, ...] = ("gray",)
    sift_feature_count: int = 14_000
    sift_contrast_threshold: float = 0.01
    sift_edge_threshold: float = 15.0
    descriptor_ratio: float = 0.78
    initial_ransac_threshold_px: float = 5.0
    maximum_dense_corners: int = 1_600
    dense_quality_level: float = 0.003
    dense_minimum_distance_px: float = 15.0
    maximum_flow_displacement_px: float = 10.0
    maximum_round_trip_error_px: float = 0.5
    maximum_flow_error: float = 35.0
    refined_ransac_threshold_px: float = 0.75
    minimum_initial_inliers: int = 12
    minimum_dense_inliers: int = 20

    def __post_init__(self) -> None:
        if not 0.05 <= self.working_scale <= 1.0:
            raise ValueError("image-evidence working scale is outside the safe range")
        if not 0.0 <= self.excluded_top_fraction < 0.8:
            raise ValueError("excluded top fraction is outside the safe range")
        supported_channels = {"gray", "blue", "green", "red", "saturation"}
        if (
            self.feature_channel not in supported_channels
            or not self.flow_channels
            or len(set(self.flow_channels)) != len(self.flow_channels)
            or any(channel not in supported_channels for channel in self.flow_channels)
        ):
            raise ValueError("unsupported image-evidence feature channel")
        if self.sift_feature_count < 100 or self.maximum_dense_corners < 40:
            raise ValueError("image-evidence feature limits are too small")
        if not 0.0 < self.descriptor_ratio < 1.0:
            raise ValueError("descriptor ratio must be between zero and one")
        if self.minimum_initial_inliers < 4 or self.minimum_dense_inliers < 10:
            raise ValueError("image-evidence inlier limits are too small")


@dataclass(frozen=True, slots=True)
class PairEvidenceDiagnostic:
    source_frame: int
    target_frame: int
    descriptor_matches: int
    initial_inliers: int
    tracked_corners: int
    dense_inliers: int


@dataclass(frozen=True, slots=True)
class CycleImageEvidence:
    profile_id: str
    image_width: int
    image_height: int
    pairs: tuple[DensePairEvidence, ...]
    diagnostics: tuple[PairEvidenceDiagnostic, ...]


def _validated_images(paths: Sequence[Path]) -> tuple[tuple[Path, ...], int, int]:
    if len(paths) != FRAME_COUNT:
        raise ImageEvidenceFailure("image registration requires exactly 16 ordered images")
    resolved: list[Path] = []
    expected_size: tuple[int, int] | None = None
    for position, candidate in enumerate(paths, start=1):
        if not candidate.is_absolute():
            raise ImageEvidenceFailure(f"frame {position} path must be absolute")
        if candidate.is_symlink() or not candidate.is_file():
            raise ImageEvidenceFailure(f"frame {position} is missing or linked")
        path = candidate.resolve()
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as decoded:
                decoded.load()
                size = decoded.size
        except (OSError, UnidentifiedImageError) as error:
            raise ImageEvidenceFailure(f"frame {position} cannot be decoded") from error
        if expected_size is None:
            expected_size = size
        elif size != expected_size:
            raise ImageEvidenceFailure("all 16 source images must have identical dimensions")
        resolved.append(path)
    assert expected_size is not None
    return tuple(resolved), expected_size[0], expected_size[1]


def _read_registration_plane(
    path: Path,
    frame: int,
    channel: RegistrationChannel,
) -> npt.NDArray[np.uint8]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ImageEvidenceFailure(f"OpenCV could not decode frame {frame}")
    if channel == "gray":
        plane = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif channel == "saturation":
        plane = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    else:
        plane = image[:, :, {"blue": 0, "green": 1, "red": 2}[channel]]
    return cast(npt.NDArray[np.uint8], plane)


def _surface_mask(
    height: int,
    width: int,
    excluded_top_fraction: float,
) -> npt.NDArray[np.uint8]:
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[int(height * excluded_top_fraction) :, :] = 255
    return mask


def _feature_sets(
    paths: tuple[Path, ...],
    profile: ImageEvidenceProfile,
) -> tuple[tuple[tuple[cv2.KeyPoint, ...], npt.NDArray[np.float32]], ...]:
    sift = cv2.SIFT_create(  # type: ignore[attr-defined]
        nfeatures=profile.sift_feature_count,
        contrastThreshold=profile.sift_contrast_threshold,
        edgeThreshold=profile.sift_edge_threshold,
    )
    features: list[tuple[tuple[cv2.KeyPoint, ...], npt.NDArray[np.float32]]] = []
    for frame, path in enumerate(paths, start=1):
        gray = _read_registration_plane(path, frame, profile.feature_channel)
        small = cv2.resize(
            gray,
            None,
            fx=profile.working_scale,
            fy=profile.working_scale,
            interpolation=cv2.INTER_AREA,
        )
        mask = _surface_mask(
            small.shape[0],
            small.shape[1],
            profile.excluded_top_fraction,
        )
        keypoints, descriptors = sift.detectAndCompute(small, mask)
        if descriptors is None or keypoints is None or len(keypoints) < 4:
            raise ImageEvidenceFailure(f"frame {frame} has insufficient visual features")
        features.append((tuple(keypoints), np.asarray(descriptors, dtype=np.float32)))
    return tuple(features)


def _dense_correspondences(
    *,
    source_path: Path,
    target_path: Path,
    source_frame: int,
    target_frame: int,
    homography: npt.NDArray[np.float64],
    width: int,
    height: int,
    channel: RegistrationChannel,
    profile: ImageEvidenceProfile,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], int]:
    source_plane = _read_registration_plane(source_path, source_frame, channel)
    target_plane = _read_registration_plane(target_path, target_frame, channel)
    warped_source = cv2.warpPerspective(
        source_plane,
        homography,
        (width, height),
        flags=cv2.INTER_LINEAR,
    )
    source_surface = _surface_mask(height, width, profile.excluded_top_fraction)
    warped_surface = cv2.warpPerspective(
        source_surface,
        homography,
        (width, height),
        flags=cv2.INTER_NEAREST,
    )
    overlap_mask = cv2.bitwise_and(
        warped_surface,
        _surface_mask(height, width, profile.excluded_top_fraction),
    )
    target_corners = cv2.goodFeaturesToTrack(
        target_plane,
        maxCorners=profile.maximum_dense_corners,
        qualityLevel=profile.dense_quality_level,
        minDistance=profile.dense_minimum_distance_px,
        mask=overlap_mask,
        blockSize=7,
        useHarrisDetector=False,
    )
    tracked_corners = 0 if target_corners is None else len(target_corners)
    empty = np.empty((0, 2), dtype=np.float64)
    if target_corners is None or tracked_corners < 40:
        return empty, empty, tracked_corners
    warped_matches, forward_status, forward_error = cv2.calcOpticalFlowPyrLK(
        target_plane,
        warped_source,
        target_corners,
        target_corners.copy(),
        winSize=(31, 31),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.001),
        flags=cv2.OPTFLOW_USE_INITIAL_FLOW,
    )
    if warped_matches is None or forward_status is None or forward_error is None:
        return empty, empty, tracked_corners
    returned_target, backward_status, backward_error = cv2.calcOpticalFlowPyrLK(
        warped_source,
        target_plane,
        warped_matches,
        target_corners.copy(),
        winSize=(31, 31),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.001),
        flags=cv2.OPTFLOW_USE_INITIAL_FLOW,
    )
    if returned_target is None or backward_status is None or backward_error is None:
        return empty, empty, tracked_corners
    displacement = np.linalg.norm(warped_matches[:, 0] - target_corners[:, 0], axis=1)
    round_trip = np.linalg.norm(returned_target[:, 0] - target_corners[:, 0], axis=1)
    retained = (
        forward_status.ravel().astype(bool)
        & backward_status.ravel().astype(bool)
        & np.isfinite(displacement)
        & np.isfinite(round_trip)
        & (displacement <= profile.maximum_flow_displacement_px)
        & (round_trip <= profile.maximum_round_trip_error_px)
        & (forward_error.ravel() <= profile.maximum_flow_error)
        & (backward_error.ravel() <= profile.maximum_flow_error)
    )
    dense_target = target_corners[retained, 0].astype(np.float64)
    dense_warped_source = warped_matches[retained].astype(np.float64)
    if len(dense_target) < 10:
        return empty, empty, tracked_corners
    dense_source = cv2.perspectiveTransform(
        dense_warped_source.astype(np.float32),
        np.linalg.inv(homography),
    )[:, 0].astype(np.float64)
    _, dense_mask = cv2.findHomography(
        dense_source,
        dense_target,
        cv2.USAC_MAGSAC,
        profile.refined_ransac_threshold_px,
        maxIters=50_000,
        confidence=0.9999,
    )
    if dense_mask is None:
        return empty, empty, tracked_corners
    dense_inliers = dense_mask.ravel().astype(bool)
    return dense_source[dense_inliers], dense_target[dense_inliers], tracked_corners


def _register_pair(
    *,
    source_frame: int,
    target_frame: int,
    source_path: Path,
    target_path: Path,
    source_features: tuple[tuple[cv2.KeyPoint, ...], npt.NDArray[np.float32]],
    target_features: tuple[tuple[cv2.KeyPoint, ...], npt.NDArray[np.float32]],
    width: int,
    height: int,
    profile: ImageEvidenceProfile,
) -> tuple[DensePairEvidence, PairEvidenceDiagnostic]:
    source_keypoints, source_descriptors = source_features
    target_keypoints, target_descriptors = target_features
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    raw_matches = matcher.knnMatch(source_descriptors, target_descriptors, k=2)
    matches = [
        first
        for candidates in raw_matches
        if len(candidates) == 2
        for first, second in [candidates]
        if first.distance < profile.descriptor_ratio * second.distance
    ]
    if len(matches) < profile.minimum_initial_inliers:
        raise ImageEvidenceFailure(
            f"{source_frame}->{target_frame}: insufficient descriptor matches "
            f"({len(matches)} found, {profile.minimum_initial_inliers} required)"
        )
    source_points = (
        np.asarray([source_keypoints[item.queryIdx].pt for item in matches], dtype=np.float64)
        / profile.working_scale
    )
    target_points = (
        np.asarray([target_keypoints[item.trainIdx].pt for item in matches], dtype=np.float64)
        / profile.working_scale
    )
    homography, initial_mask = cv2.findHomography(
        source_points,
        target_points,
        cv2.RANSAC,
        profile.initial_ransac_threshold_px,
        maxIters=20_000,
        confidence=0.999,
    )
    initial_inliers = int(np.count_nonzero(initial_mask)) if initial_mask is not None else 0
    if homography is None or initial_inliers < profile.minimum_initial_inliers:
        raise ImageEvidenceFailure(
            f"{source_frame}->{target_frame}: insufficient initial homography inliers "
            f"({initial_inliers} found, {profile.minimum_initial_inliers} required)"
        )
    homography_matrix = np.asarray(homography, dtype=np.float64)

    best_source: npt.NDArray[np.float64] = np.empty((0, 2), dtype=np.float64)
    best_target: npt.NDArray[np.float64] = np.empty((0, 2), dtype=np.float64)
    tracked_corners = 0
    for channel in profile.flow_channels:
        candidate_source, candidate_target, candidate_corners = _dense_correspondences(
            source_path=source_path,
            target_path=target_path,
            source_frame=source_frame,
            target_frame=target_frame,
            homography=homography_matrix,
            width=width,
            height=height,
            channel=channel,
            profile=profile,
        )
        tracked_corners = max(tracked_corners, candidate_corners)
        if len(candidate_source) > len(best_source):
            best_source, best_target = candidate_source, candidate_target
    dense_inlier_count = len(best_source)
    if dense_inlier_count < profile.minimum_dense_inliers:
        raise ImageEvidenceFailure(
            f"{source_frame}->{target_frame}: insufficient dense subpixel correspondences "
            f"({dense_inlier_count} found, {profile.minimum_dense_inliers} required)"
        )
    evidence = split_spatial_evidence(
        source_frame=source_frame,
        target_frame=target_frame,
        source_points=best_source,
        target_points=best_target,
    )
    return evidence, PairEvidenceDiagnostic(
        source_frame=source_frame,
        target_frame=target_frame,
        descriptor_matches=len(matches),
        initial_inliers=initial_inliers,
        tracked_corners=tracked_corners,
        dense_inliers=dense_inlier_count,
    )


def extract_cycle_image_evidence(
    ordered_paths: Sequence[Path],
    *,
    profile: ImageEvidenceProfile | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancellationCheck | None = None,
) -> CycleImageEvidence:
    """Extract fit and independently held-out evidence for all 16 neighbor joins."""

    selected_profile = profile or ImageEvidenceProfile()
    paths, width, height = _validated_images(ordered_paths)
    cv2.setRNGSeed(0)
    feature_sets = _feature_sets(paths, selected_profile)
    pairs: list[DensePairEvidence] = []
    diagnostics: list[PairEvidenceDiagnostic] = []
    for source_index in range(FRAME_COUNT):
        if cancelled is not None and cancelled():
            raise ImageEvidenceCancelled("image-evidence extraction cancelled by caller")
        target_index = (source_index + 1) % FRAME_COUNT
        evidence, diagnostic = _register_pair(
            source_frame=source_index + 1,
            target_frame=target_index + 1,
            source_path=paths[source_index],
            target_path=paths[target_index],
            source_features=feature_sets[source_index],
            target_features=feature_sets[target_index],
            width=width,
            height=height,
            profile=selected_profile,
        )
        pairs.append(evidence)
        diagnostics.append(diagnostic)
        if progress is not None:
            progress(source_index + 1, FRAME_COUNT)
    return CycleImageEvidence(
        profile_id=selected_profile.profile_id,
        image_width=width,
        image_height=height,
        pairs=tuple(pairs),
        diagnostics=tuple(diagnostics),
    )
