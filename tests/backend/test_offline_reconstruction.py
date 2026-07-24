"""Offline reconstruction source-order contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from backend.services.offline_reconstruction import OfflineReconstructionError, _ordered_images


def _image(path: Path) -> None:
    Image.new("RGB", (32, 24), "black").save(path)


def test_orders_numeric_prefixes_without_lexicographic_mistakes(tmp_path: Path) -> None:
    for position in range(16, 0, -1):
        _image(tmp_path / f"{position}RGB-compensated.jpg")
    ordered = _ordered_images(tmp_path)
    assert [path.name for path in ordered] == [
        f"{position}RGB-compensated.jpg" for position in range(1, 17)
    ]


def test_rejects_missing_duplicate_or_unnumbered_acquisition(tmp_path: Path) -> None:
    for position in range(1, 16):
        _image(tmp_path / f"{position}.jpg")
    with pytest.raises(OfflineReconstructionError, match="exactly 16"):
        _ordered_images(tmp_path)
    _image(tmp_path / "unpositioned.jpg")
    with pytest.raises(OfflineReconstructionError, match="must start"):
        _ordered_images(tmp_path)
