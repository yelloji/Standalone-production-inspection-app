"""Approved center-reference import and integrity tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from backend.core.paths import ApplicationPaths
from backend.domain.contracts import DiscSide
from backend.domain.reconstruction import Point2D
from backend.services import center_reference_library
from backend.services.center_reference_library import (
    ApprovedCenterReference,
    CenterReferenceLibrary,
)


def test_imports_verified_reference_into_portable_data(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    source = tmp_path / "approved.jpg"
    Image.new("RGB", (120, 80), (20, 30, 40)).save(source, format="JPEG")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    approved = ApprovedCenterReference(
        side=DiscSide.UPPER,
        profile_id="test-upper-v1",
        asset_id="test-upper-asset-v1",
        relative_path="configuration/center-references/upper.jpg",
        expected_sha256=digest,
        expected_width=120,
        expected_height=80,
        source_center=Point2D(x=60.0, y=40.0),
        source_radius_px=30.0,
        marker_center=Point2D(x=70.0, y=40.0),
    )
    monkeypatch.setitem(  # type: ignore[attr-defined]
        center_reference_library.APPROVED_CENTER_REFERENCES,
        DiscSide.UPPER,
        approved,
    )
    paths = ApplicationPaths.resolve(
        resource_root=tmp_path,
        data_root=tmp_path / "data",
    )
    paths.ensure_data_layout()
    library = CenterReferenceLibrary(paths)

    before = library.status(DiscSide.UPPER)
    assert not before.installed
    installed = library.install(DiscSide.UPPER, source)

    assert installed.installed
    assert installed.sha256 == digest
    assert paths.resolve_data_path(installed.relative_path).read_bytes() == source.read_bytes()
    profile = library.require_profile(DiscSide.UPPER)
    assert profile.profile_id == "test-upper-v1"
    assert profile.asset.sha256 == digest
