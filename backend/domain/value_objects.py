"""Validated primitive values shared by production contracts and storage."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated

from pydantic import AfterValidator, StringConstraints

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_UNSAFE_WINDOWS_CHARACTERS = re.compile(r'[<>:"|?*\x00-\x1f]')
_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


def normalize_relative_path(value: str) -> str:
    """Return a portable stored path or reject unsafe/machine-specific input."""

    candidate = value.strip()
    if not candidate:
        raise ValueError("relative path must not be empty")
    if "\\" in candidate:
        raise ValueError("relative path must use forward slashes")
    if PureWindowsPath(candidate).drive or PurePosixPath(candidate).is_absolute():
        raise ValueError("absolute or drive-qualified paths are not allowed")

    raw_parts = candidate.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("relative path contains an unsafe traversal segment")
    path = PurePosixPath(candidate)

    for part in path.parts:
        if part.endswith((" ", ".")):
            raise ValueError("path components must not end with a space or period")
        if _UNSAFE_WINDOWS_CHARACTERS.search(part):
            raise ValueError("relative path contains a Windows-unsafe character")
        if part.split(".", maxsplit=1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise ValueError("relative path contains a Windows-reserved name")

    return path.as_posix()


SafeRelativePath = Annotated[str, AfterValidator(normalize_relative_path)]
Sha256Hex = Annotated[
    str,
    StringConstraints(pattern=_SHA256_PATTERN, to_lower=True),
]
ContractIdentifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=_IDENTIFIER_PATTERN,
        strip_whitespace=True,
    ),
]
