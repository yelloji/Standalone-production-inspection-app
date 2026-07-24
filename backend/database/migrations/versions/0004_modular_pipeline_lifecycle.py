"""Allow modular pipelines and guarantee one active production snapshot.

Revision ID: 0004_modular_pipeline_lifecycle
Revises: 0003_run_orchestration
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_modular_pipeline_lifecycle"
down_revision = "0003_run_orchestration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_snapshots") as batch:
        batch.alter_column(
            "model_bundle_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )
    op.create_index(
        "uq_pipeline_snapshots_single_active",
        "pipeline_snapshots",
        ["state"],
        unique=True,
        sqlite_where=sa.text("state = 'active'"),
    )


def downgrade() -> None:
    raise RuntimeError("Production database migrations are additive-only")
