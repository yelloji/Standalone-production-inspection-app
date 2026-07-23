"""Safe staged import of directory or ZIP ONNX model bundles."""

from __future__ import annotations

import os
import shutil
import stat
import uuid
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.models import utc_now
from backend.database.records import ModelBundleMetadata
from backend.database.repositories import MetadataRepository
from backend.domain.value_objects import normalize_relative_path
from backend.services.model_validation import (
    ValidatedModelBundle,
    validate_model_bundle,
)

MAX_BUNDLE_FILES = 10_000
MAX_BUNDLE_BYTES = 20 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class ModelImportError(RuntimeError):
    """Raised when a bundle cannot be copied or registered safely."""


class ModelImportService:
    def __init__(
        self,
        *,
        paths: ApplicationPaths,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory

    def import_bundle(self, source: Path) -> ModelBundleMetadata:
        if not source.is_absolute():
            raise ModelImportError("model bundle source path must be absolute")
        if not source.exists():
            raise FileNotFoundError(source)
        if source.is_symlink():
            raise ModelImportError("model bundle source must not be a link")

        staging_root = self._paths.resolve_data_path("models/.staging")
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = staging_root / uuid.uuid4().hex
        staging.mkdir()

        final: Path | None = None
        try:
            if source.is_dir():
                _copy_directory(source, staging)
            elif source.is_file() and source.suffix.casefold() == ".zip":
                _extract_zip(source, staging)
            else:
                raise ModelImportError("model bundle source must be a directory or ZIP")

            validated = validate_model_bundle(staging)
            final = self._paths.resolve_data_path(
                f"models/{validated.model_manifest.model_bundle_id}"
            )
            if final.exists():
                raise ModelImportError("model bundle identifier is already registered")

            os.replace(staging, final)
            metadata = _metadata(final, self._paths, validated)
            try:
                with transaction(self._session_factory) as session:
                    MetadataRepository(session).add_model_bundle(metadata)
            except BaseException:
                shutil.rmtree(final, ignore_errors=True)
                raise
            return metadata
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)


def _metadata(
    final: Path,
    paths: ApplicationPaths,
    validated: ValidatedModelBundle,
) -> ModelBundleMetadata:
    manifest = validated.model_manifest
    return ModelBundleMetadata(
        model_bundle_id=manifest.model_bundle_id,
        display_name=manifest.display_name,
        model_version=manifest.model_version,
        state="valid",
        manifest_path=paths.to_data_relative_path(final / "model_manifest.json"),
        sha256=validated.model_sha256,
        created_at=utc_now(),
    )


def _copy_directory(source: Path, destination: Path) -> None:
    files = _safe_source_files(source)
    for source_file, relative_path in files:
        target = destination / Path(*relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)


def _safe_source_files(source: Path) -> tuple[tuple[Path, str], ...]:
    files: list[tuple[Path, str]] = []
    total_bytes = 0
    casefolded: set[str] = set()
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ModelImportError("links are not allowed in model bundles")
        if not path.is_file():
            continue
        relative = normalize_relative_path(path.relative_to(source).as_posix())
        if relative.casefold() in casefolded:
            raise ModelImportError("case-colliding bundle paths are not allowed")
        casefolded.add(relative.casefold())
        total_bytes += path.stat().st_size
        files.append((path, relative))
        _enforce_limits(len(files), total_bytes)
    return tuple(files)


def _extract_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        entries: list[tuple[zipfile.ZipInfo, str]] = []
        total_bytes = 0
        casefolded: set[str] = set()
        for item in archive.infolist():
            if item.is_dir():
                continue
            if item.flag_bits & 0x1:
                raise ModelImportError("encrypted ZIP entries are not supported")
            if stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK:
                raise ModelImportError("ZIP links are not allowed")
            relative = normalize_relative_path(item.filename)
            if relative.casefold() in casefolded:
                raise ModelImportError("duplicate or case-colliding ZIP paths")
            casefolded.add(relative.casefold())
            total_bytes += item.file_size
            _enforce_limits(len(entries) + 1, total_bytes)
            if (
                item.file_size > 0
                and item.compress_size == 0
                or item.compress_size > 0
                and item.file_size / item.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ModelImportError("suspicious ZIP compression ratio")
            entries.append((item, relative))

        for item, relative in entries:
            target = destination / Path(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source_stream, target.open("xb") as target_stream:
                shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)


def _enforce_limits(file_count: int, total_bytes: int) -> None:
    if file_count > MAX_BUNDLE_FILES:
        raise ModelImportError("model bundle contains too many files")
    if total_bytes > MAX_BUNDLE_BYTES:
        raise ModelImportError("model bundle is too large")
