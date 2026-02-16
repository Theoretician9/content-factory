"""init evolution-agent schema

Revision ID: 0001_init_evolution_schema
Revises:
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_init_evolution_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums: создаём явно выше с checkfirst=True; в таблицах не создаём повторно
    calendar_status_enum = sa.Enum(
        "planned",
        "processing",
        "ready",
        "published",
        "failed",
        name="calendar_slot_status",
        create_type=False,
    )
    agent_task_status_enum = sa.Enum(
        "created",
        "running",
        "completed",
        "failed",
        name="agent_task_status",
        create_type=False,
    )

    calendar_status_enum.create(op.get_bind(), checkfirst=True)
    agent_task_status_enum.create(op.get_bind(), checkfirst=True)

    # strategies
    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("channel_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("persona_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_mix_json", postgresql.JSONB(), nullable=False),
        sa.Column("schedule_rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    # user_id и channel_id уже индексируются через index=True в create_table
    op.create_index(
        "ix_strategies_is_active",
        "strategies",
        ["is_active"],
    )
    op.create_unique_constraint(
        "uq_strategies_user_channel_active",
        "strategies",
        ["user_id", "channel_id", "is_active"],
    )

    # calendar_slots
    op.create_table(
        "calendar_slots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dt", sa.DateTime(), nullable=False),
        sa.Column("status", calendar_status_enum, nullable=False, server_default="planned"),
        sa.Column("pillar", sa.Text(), nullable=True),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_calendar_slots_user_id", "calendar_slots", ["user_id"])
    op.create_index("ix_calendar_slots_channel_id", "calendar_slots", ["channel_id"])
    op.create_index("ix_calendar_slots_dt", "calendar_slots", ["dt"])
    op.create_index("ix_calendar_slots_status", "calendar_slots", ["status"])

    # posts
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column(
            "slot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendar_slots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.JSONB(), nullable=True),
        sa.Column("cta", sa.Text(), nullable=True),
        sa.Column("meta_stats", postgresql.JSONB(), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_posts_user_id", "posts", ["user_id"])
    op.create_index("ix_posts_channel_id", "posts", ["channel_id"])
    op.create_unique_constraint("uq_posts_slot_id", "posts", ["slot_id"])

    # memory_logs
    op.create_table(
        "memory_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metrics_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_memory_logs_user_id", "memory_logs", ["user_id"])
    op.create_index("ix_memory_logs_channel_id", "memory_logs", ["channel_id"])
    op.create_index("ix_memory_logs_post_id", "memory_logs", ["post_id"])

    # agent_tasks
    op.create_table(
        "agent_tasks",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column("slot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            agent_task_status_enum,
            nullable=False,
            server_default="created",
        ),
        sa.Column("goal", sa.String(length=255), nullable=False),
        sa.Column("user_request", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_agent_tasks_user_id", "agent_tasks", ["user_id"])
    op.create_index("ix_agent_tasks_channel_id", "agent_tasks", ["channel_id"])
    op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])
    op.create_index("ix_agent_tasks_slot_id", "agent_tasks", ["slot_id"])


def downgrade() -> None:
    op.drop_table("agent_tasks")
    op.drop_table("memory_logs")
    op.drop_table("posts")
    op.drop_table("calendar_slots")
    op.drop_table("strategies")

    agent_task_status_enum = sa.Enum(
        "created",
        "running",
        "completed",
        "failed",
        name="agent_task_status",
    )
    calendar_status_enum = sa.Enum(
        "planned",
        "processing",
        "ready",
        "published",
        "failed",
        name="calendar_slot_status",
    )

    agent_task_status_enum.drop(op.get_bind(), checkfirst=True)
    calendar_status_enum.drop(op.get_bind(), checkfirst=True)

