"""add strategies.updated_at

Revision ID: 0002_add_strategies_updated_at
Revises: 0001_init_evolution_schema
Create Date: 2026-02-16

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_strategies_updated_at"
down_revision = "0001_init_evolution_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("strategies", "updated_at")
