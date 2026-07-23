"""Create the production metadata foundation.

Revision ID: 0001_metadata_foundation
Revises:
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_metadata_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_bundles",
        sa.Column("model_bundle_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("manifest_path", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('imported', 'verifying', 'valid', 'approved', 'active', "
            "'retired', 'rejected')",
            name="ck_model_bundles_model_bundle_state",
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_model_bundles_model_bundle_sha256_length",
        ),
        sa.PrimaryKeyConstraint("model_bundle_id", name="pk_model_bundles"),
        sa.UniqueConstraint("manifest_path", name="uq_model_bundles_manifest_path"),
    )
    op.create_index(
        "ix_model_bundles_state_created_at",
        "model_bundles",
        ["state", "created_at"],
    )

    op.create_table(
        "pipeline_snapshots",
        sa.Column("pipeline_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("pipeline_id", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("model_bundle_id", sa.String(length=128), nullable=False),
        sa.Column("contract_path", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('draft', 'testing', 'validated', 'approved', 'active', "
            "'retired', 'rejected', 'archived')",
            name="ck_pipeline_snapshots_pipeline_snapshot_state",
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_pipeline_snapshots_pipeline_snapshot_revision_positive",
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_pipeline_snapshots_pipeline_snapshot_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["model_bundle_id"],
            ["model_bundles.model_bundle_id"],
            name="fk_pipeline_snapshots_model_bundle_id_model_bundles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "pipeline_snapshot_id",
            name="pk_pipeline_snapshots",
        ),
        sa.UniqueConstraint(
            "contract_path",
            name="uq_pipeline_snapshots_contract_path",
        ),
        sa.UniqueConstraint(
            "pipeline_id",
            "revision",
            name="uq_pipeline_snapshots_pipeline_revision",
        ),
    )
    op.create_index(
        "ix_pipeline_snapshots_state_created_at",
        "pipeline_snapshots",
        ["state", "created_at"],
    )

    op.create_table(
        "inspection_runs",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("acquisition_id", sa.String(length=128), nullable=False),
        sa.Column("pipeline_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_inspection_runs_inspection_run_status",
        ),
        sa.CheckConstraint(
            "source IN ('offline', 'online')",
            name="ck_inspection_runs_inspection_run_source",
        ),
        sa.CheckConstraint(
            "side IN ('upper', 'lower', 'not_applicable')",
            name="ck_inspection_runs_inspection_run_side",
        ),
        sa.ForeignKeyConstraint(
            ["pipeline_snapshot_id"],
            ["pipeline_snapshots.pipeline_snapshot_id"],
            name="fk_inspection_runs_pipeline_snapshot_id_pipeline_snapshots",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_inspection_runs"),
    )
    op.create_index(
        "ix_inspection_runs_acquisition_id",
        "inspection_runs",
        ["acquisition_id"],
    )
    op.create_index(
        "ix_inspection_runs_status_created_at",
        "inspection_runs",
        ["status", "created_at"],
    )

    op.create_table(
        "source_frames",
        sa.Column("source_frame_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "frame_index >= 0",
            name="ck_source_frames_source_frame_index_nonnegative",
        ),
        sa.CheckConstraint(
            "width >= 1",
            name="ck_source_frames_source_frame_width_positive",
        ),
        sa.CheckConstraint(
            "height >= 1",
            name="ck_source_frames_source_frame_height_positive",
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_source_frames_source_frame_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inspection_runs.run_id"],
            name="fk_source_frames_run_id_inspection_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_frame_id", name="pk_source_frames"),
        sa.UniqueConstraint(
            "run_id",
            "frame_index",
            name="uq_source_frames_run_frame_index",
        ),
        sa.UniqueConstraint(
            "run_id",
            "relative_path",
            name="uq_source_frames_run_relative_path",
        ),
    )
    op.create_index(
        "ix_source_frames_run_frame_index",
        "source_frames",
        ["run_id", "frame_index"],
    )

    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_artifacts_artifact_size_nonnegative",
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_artifacts_artifact_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inspection_runs.run_id"],
            name="fk_artifacts_run_id_inspection_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artifact_id", name="pk_artifacts"),
        sa.UniqueConstraint(
            "relative_path",
            name="uq_artifacts_relative_path",
        ),
    )
    op.create_index(
        "ix_artifacts_run_kind",
        "artifacts",
        ["run_id", "kind"],
    )


def downgrade() -> None:
    raise RuntimeError("Production database migrations are additive-only")
