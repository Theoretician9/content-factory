"""fix strategies unique active constraint

Revision ID: 0004_strategies_unique_active
Revises: 0003_add_posts_updated_at
Create Date: 2026-02-16

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_strategies_unique_active"
down_revision = "0003_add_posts_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Снимаем старое ограничение UNIQUE(user_id, channel_id, is_active),
    # которое не позволяло иметь несколько неактивных стратегий для одного канала.
    with op.batch_alter_table("strategies") as batch_op:
        batch_op.drop_constraint("uq_strategies_user_channel_active", type_="unique")

    # Создаём частичный уникальный индекс только для активных стратегий:
    # для (user_id, channel_id) может быть не более одной записи с is_active = true.
    op.create_index(
        "ix_strategies_user_channel_active_unique",
        "strategies",
        ["user_id", "channel_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    # Откатываемся к предыдущему поведению: удаляем частичный индекс
    op.drop_index("ix_strategies_user_channel_active_unique", table_name="strategies")

    # И восстанавливаем старое ограничение UNIQUE(user_id, channel_id, is_active)
    with op.batch_alter_table("strategies") as batch_op:
        batch_op.create_unique_constraint(
            "uq_strategies_user_channel_active",
            ["user_id", "channel_id", "is_active"],
        )

