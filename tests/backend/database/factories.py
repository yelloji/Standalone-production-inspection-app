"""Consistent metadata values for database tests."""

from datetime import datetime, timezone

from backend.database.records import (
    ArtifactMetadata,
    InspectionRunMetadata,
    ModelBundleMetadata,
    PipelineSnapshotMetadata,
    SourceFrameMetadata,
)

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
CHECKSUM = "a" * 64


def model_bundle(
    model_bundle_id: str = "model-v1",
) -> ModelBundleMetadata:
    return ModelBundleMetadata(
        model_bundle_id=model_bundle_id,
        display_name="Brake Disc Crack Detector",
        model_version="1.0.0",
        state="valid",
        manifest_path=f"models/{model_bundle_id}/manifest.json",
        sha256=CHECKSUM,
        created_at=NOW,
    )


def pipeline_snapshot(
    pipeline_snapshot_id: str = "pipeline-upper-r1",
    *,
    model_bundle_id: str = "model-v1",
    revision: int = 1,
) -> PipelineSnapshotMetadata:
    return PipelineSnapshotMetadata(
        pipeline_snapshot_id=pipeline_snapshot_id,
        pipeline_id="brake-disc-upper",
        revision=revision,
        display_name="Brake Disc Upper",
        state="approved",
        model_bundle_id=model_bundle_id,
        contract_path=f"pipelines/{pipeline_snapshot_id}.json",
        sha256=CHECKSUM,
        created_at=NOW,
    )


def inspection_run(
    run_id: str = "run-001",
    *,
    pipeline_snapshot_id: str = "pipeline-upper-r1",
) -> InspectionRunMetadata:
    return InspectionRunMetadata(
        run_id=run_id,
        acquisition_id=f"acquisition-{run_id}",
        pipeline_snapshot_id=pipeline_snapshot_id,
        source="offline",
        side="upper",
        status="created",
        failure_code=None,
        created_at=NOW,
    )


def source_frame(
    frame_index: int,
    *,
    run_id: str = "run-001",
) -> SourceFrameMetadata:
    return SourceFrameMetadata(
        source_frame_id=f"{run_id}-frame-{frame_index:02d}",
        run_id=run_id,
        frame_index=frame_index,
        relative_path=f"incoming/{run_id}/{frame_index:02d}.jpg",
        sha256=CHECKSUM,
        width=8192,
        height=5464,
        created_at=NOW,
    )


def artifact(
    artifact_id: str = "artifact-001",
    *,
    run_id: str = "run-001",
) -> ArtifactMetadata:
    return ArtifactMetadata(
        artifact_id=artifact_id,
        run_id=run_id,
        kind="reconstructed_image",
        relative_path=f"completed/{run_id}/{artifact_id}.tif",
        sha256=CHECKSUM,
        size_bytes=10_000,
        media_type="image/tiff",
        created_at=NOW,
    )
