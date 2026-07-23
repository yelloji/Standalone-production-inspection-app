"""Create small deterministic image acquisitions for intake tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def create_acquisition_images(
    root: Path,
    *,
    width: int = 32,
    height: int = 24,
    formats: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    root.mkdir(parents=True)
    selected_formats = formats or ("PNG",) * 16
    if len(selected_formats) != 16:
        raise ValueError("test acquisition requires exactly 16 formats")

    names: list[str] = []
    extensions = {"JPEG": ".jpg", "PNG": ".png", "TIFF": ".tif"}
    for index, image_format in enumerate(selected_formats, start=1):
        name = f"camera_{17 - index:02d}{extensions[image_format]}"
        color = (
            (index * 13) % 256,
            (index * 29) % 256,
            (index * 47) % 256,
        )
        Image.new("RGB", (width, height), color).save(
            root / name,
            format=image_format,
            quality=95,
        )
        names.append(name)
    return tuple(names)
