"""Guarantee a single active model bundle.

Revision ID: 0002_single_active_model
Revises: 0001_metadata_foundation
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_single_active_model"
down_revision = "0001_metadata_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_model_bundles_single_active",
        "model_bundles",
        ["state"],
        unique=True,
        sqlite_where=sa.text("state = 'active'"),
    )


def downgrade() -> None:
    raise RuntimeError("Production database migrations are additive-only")
