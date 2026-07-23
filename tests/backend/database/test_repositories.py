"""Repository, transaction, constraint, and metadata validation tests."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.database.engine import transaction
from backend.database.records import ArtifactMetadata, ModelBundleMetadata
from backend.database.repositories import MetadataRepository
from tests.backend.database.factories import (
    CHECKSUM,
    NOW,
    artifact,
    inspection_run,
    model_bundle,
    pipeline_snapshot,
    source_frame,
)


def seed_run(repository: MetadataRepository) -> None:
    repository.add_model_bundle(model_bundle())
    repository.add_pipeline_snapshot(pipeline_snapshot())
    repository.add_run(inspection_run())


def test_repository_round_trip_and_frame_order(
    session_factory: sessionmaker[Session],
) -> None:
    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        seed_run(repository)
        repository.add_source_frame(source_frame(2))
        repository.add_source_frame(source_frame(0))
        repository.add_source_frame(source_frame(1))
        repository.add_artifact(artifact())

    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        assert repository.get_model_bundle("model-v1") == model_bundle()
        assert repository.get_pipeline_snapshot("pipeline-upper-r1") == pipeline_snapshot()
        assert repository.get_run("run-001") == inspection_run()
        assert [frame.frame_index for frame in repository.list_source_frames("run-001")] == [
            0,
            1,
            2,
        ]
        assert repository.list_artifacts("run-001") == (artifact(),)
        assert repository.get_run("run-001").created_at.tzinfo is not None  # type: ignore[union-attr]


def test_transaction_rolls_back_all_changes_on_error(
    session_factory: sessionmaker[Session],
) -> None:
    with (
        pytest.raises(RuntimeError, match="simulated"),
        transaction(session_factory) as session,
    ):
        repository = MetadataRepository(session)
        repository.add_model_bundle(model_bundle())
        raise RuntimeError("simulated failure")

    with transaction(session_factory) as session:
        assert MetadataRepository(session).get_model_bundle("model-v1") is None


def test_foreign_keys_and_unique_frame_index_are_enforced(
    session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(IntegrityError), transaction(session_factory) as session:
        MetadataRepository(session).add_run(inspection_run(pipeline_snapshot_id="missing-pipeline"))

    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        seed_run(repository)
        repository.add_source_frame(source_frame(0))

    with pytest.raises(IntegrityError), transaction(session_factory) as session:
        MetadataRepository(session).add_source_frame(
            source_frame(0),
        )


def test_database_constraints_reject_invalid_state(
    session_factory: sessionmaker[Session],
) -> None:
    invalid = ModelBundleMetadata(
        model_bundle_id="invalid-model",
        display_name="Invalid",
        model_version="1",
        state="unknown",
        manifest_path="models/invalid/manifest.json",
        sha256=CHECKSUM,
        created_at=NOW,
    )

    with pytest.raises(IntegrityError), transaction(session_factory) as session:
        MetadataRepository(session).add_model_bundle(invalid)


@pytest.mark.parametrize(
    ("path", "checksum", "created_at"),
    [
        ("C:/fixed/artifact.tif", CHECKSUM, NOW),
        ("completed/artifact.tif", "bad", NOW),
        ("completed/artifact.tif", CHECKSUM, datetime(2026, 7, 23)),
    ],
)
def test_metadata_rejects_unsafe_paths_checksums_and_timestamps(
    path: str,
    checksum: str,
    created_at: datetime,
) -> None:
    with pytest.raises(ValueError):
        ArtifactMetadata(
            artifact_id="invalid-artifact",
            run_id="run-001",
            kind="diagnostic",
            relative_path=path,
            sha256=checksum,
            size_bytes=1,
            media_type="application/octet-stream",
            created_at=created_at,
        )


def test_metadata_normalizes_portable_relative_paths() -> None:
    value = artifact()
    normalized = ArtifactMetadata(
        artifact_id=value.artifact_id,
        run_id=value.run_id,
        kind=value.kind,
        relative_path=f"  {value.relative_path}  ",
        sha256=value.sha256,
        size_bytes=value.size_bytes,
        media_type=value.media_type,
        created_at=value.created_at,
    )

    assert normalized.relative_path == value.relative_path
