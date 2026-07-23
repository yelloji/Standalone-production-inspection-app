"""Deterministic JSON serialization and content checksums."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class ChecksumMismatchError(ValueError):
    """Raised when exact bytes do not match their declared SHA-256."""


def canonical_json_bytes(value: BaseModel | Any) -> bytes:
    """Serialize a JSON-compatible value deterministically as UTF-8."""

    serializable = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    text = json.dumps(
        serializable,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    """Return the lowercase SHA-256 digest for exact bytes."""

    return hashlib.sha256(payload).hexdigest()


def canonical_checksum(value: BaseModel | Any) -> str:
    """Return the checksum of canonical JSON bytes."""

    return sha256_hex(canonical_json_bytes(value))


def verify_sha256(payload: bytes, expected: str) -> None:
    """Reject payload bytes that do not match the expected SHA-256."""

    actual = sha256_hex(payload)
    if not hmac.compare_digest(actual, expected.lower()):
        raise ChecksumMismatchError("payload SHA-256 does not match the expected checksum")


def validate_json_model(payload: bytes | str, model_type: type[ModelT]) -> ModelT:
    """Validate serialized JSON against an explicit Pydantic schema."""

    return model_type.model_validate_json(payload)
