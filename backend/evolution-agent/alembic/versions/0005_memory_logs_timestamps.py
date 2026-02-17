"""add timestamps to memory_logs

Revision ID: 0005_memory_logs_timestamps
Revises: 0004_strategies_unique_active
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_memory_logs_timestamps"
down_revision = "0004_strategies_unique_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем стандартные временные поля в memory_logs, как и в других таблицах.
    op.add_column(
        "memory_logs",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "memory_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("memory_logs", "updated_at")
    op.drop_column("memory_logs", "created_at")

