"""Add account_states table for Account Manager

Revision ID: 003_add_account_states
Revises: 002_add_author_phone
Create Date: 2025-06-26 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '003_add_account_states'
down_revision = '002_add_author_phone'
branch_labels = None
depends_on = None


def upgrade():
    # Create account_states table
    op.create_table(
        'account_states',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        
        # Account identification
        sa.Column('account_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        
        # Current status
        sa.Column('status', sa.String(20), default='free', nullable=False, index=True),
        
        # Task assignment
        sa.Column('current_task_id', sa.String(100), nullable=True, index=True),
        
        # Blocking/timing information
        sa.Column('blocked_until', sa.DateTime(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), default=func.now(), nullable=False),
        sa.Column('last_flood_wait', sa.DateTime(), nullable=True),
        
        # Account metadata
        sa.Column('account_info', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_tasks_completed', sa.Integer(), default=0),
        sa.Column('total_flood_waits', sa.Integer(), default=0),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=func.now(), onupdate=func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('account_states') 