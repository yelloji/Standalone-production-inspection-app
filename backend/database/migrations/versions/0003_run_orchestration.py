"""Add durable run controls and stage checkpoints.

Revision ID: 0003_run_orchestration
Revises: 0002_single_active_model
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_run_orchestration"
down_revision = "0002_single_active_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_controls",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "cancellation_requested IN (0, 1)",
            name="ck_run_controls_run_control_cancellation_boolean",
        ),
        sa.CheckConstraint(
            "(lease_owner IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_run_controls_run_control_lease_complete",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inspection_runs.run_id"],
            name="fk_run_controls_run_id_inspection_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_run_controls"),
    )
    op.create_index(
        "ix_run_controls_lease_expires_at",
        "run_controls",
        ["lease_expires_at"],
        unique=False,
    )
    op.execute(
        sa.text(
            "INSERT INTO run_controls "
            "(run_id, cancellation_requested, lease_owner, lease_expires_at, updated_at) "
            "SELECT run_id, 0, NULL, NULL, created_at FROM inspection_runs"
        )
    )
    op.create_table(
        "run_stage_checkpoints",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("stage_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("evidence_path", sa.String(length=1024), nullable=True),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_run_stage_checkpoints_run_stage_checkpoint_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_run_stage_checkpoints_run_stage_checkpoint_attempt_nonnegative",
        ),
        sa.CheckConstraint(
            "(evidence_path IS NULL AND evidence_sha256 IS NULL) OR "
            "(evidence_path IS NOT NULL AND evidence_sha256 IS NOT NULL)",
            name="ck_run_stage_checkpoints_run_stage_checkpoint_evidence_complete",
        ),
        sa.CheckConstraint(
            "evidence_sha256 IS NULL OR length(evidence_sha256) = 64",
            name="ck_run_stage_checkpoints_run_stage_checkpoint_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inspection_runs.run_id"],
            name="fk_run_stage_checkpoints_run_id_inspection_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "run_id",
            "stage_name",
            name="pk_run_stage_checkpoints",
        ),
    )
    op.create_index(
        "ix_run_stage_checkpoints_run_status",
        "run_stage_checkpoints",
        ["run_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    raise RuntimeError("Production database migrations are additive-only")
