"""add posts.updated_at

Revision ID: 0003_add_posts_updated_at
Revises: 0002_add_strategies_updated_at
Create Date: 2026-02-16

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_posts_updated_at"
down_revision = "0002_add_strategies_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("posts", "updated_at")

