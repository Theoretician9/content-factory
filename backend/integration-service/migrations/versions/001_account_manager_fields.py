"""Add Account Manager fields to telegram_sessions

Revision ID: 001_account_manager_fields
Revises: 
Create Date: 2025-01-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_account_manager_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Account Manager fields to telegram_sessions table"""
    
    # Add Account Manager status and locking fields
    op.add_column('telegram_sessions', sa.Column('status', sa.String(20), nullable=False, server_default='active'))
    op.add_column('telegram_sessions', sa.Column('locked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('telegram_sessions', sa.Column('locked_by', sa.String(100), nullable=True))
    op.add_column('telegram_sessions', sa.Column('locked_until', sa.TIMESTAMP(timezone=True), nullable=True))
    
    # Add daily limits and usage counters
    op.add_column('telegram_sessions', sa.Column('used_invites_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('telegram_sessions', sa.Column('used_messages_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('telegram_sessions', sa.Column('contacts_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('telegram_sessions', sa.Column('per_channel_invites', postgresql.JSONB(), nullable=False, server_default='{}'))
    
    # Add flood and ban management fields
    op.add_column('telegram_sessions', sa.Column('flood_wait_until', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('telegram_sessions', sa.Column('blocked_until', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('telegram_sessions', sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'))
    
    # Add timing fields
    op.add_column('telegram_sessions', sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('telegram_sessions', sa.Column('reset_at', sa.TIMESTAMP(timezone=True), nullable=False, 
                  server_default=sa.text("(CURRENT_DATE + INTERVAL '1 day')")))
    
    # Create indexes for performance
    op.create_index('idx_telegram_sessions_status', 'telegram_sessions', ['status'])
    op.create_index('idx_telegram_sessions_locked', 'telegram_sessions', ['locked'], 
                    postgresql_where=sa.text('locked = true'))
    op.create_index('idx_telegram_sessions_user_status', 'telegram_sessions', ['user_id', 'status'])
    op.create_index('idx_telegram_sessions_flood_wait', 'telegram_sessions', ['flood_wait_until'], 
                    postgresql_where=sa.text('flood_wait_until IS NOT NULL'))
    op.create_index('idx_telegram_sessions_reset_at', 'telegram_sessions', ['reset_at'])
    
    # Create constraint for status values
    op.create_check_constraint(
        'ck_telegram_sessions_status',
        'telegram_sessions', 
        sa.text("status IN ('active', 'flood_wait', 'blocked', 'disabled')")
    )


def downgrade() -> None:
    """Remove Account Manager fields from telegram_sessions table"""
    
    # Drop indexes first
    op.drop_index('idx_telegram_sessions_reset_at', table_name='telegram_sessions')
    op.drop_index('idx_telegram_sessions_flood_wait', table_name='telegram_sessions')
    op.drop_index('idx_telegram_sessions_user_status', table_name='telegram_sessions')
    op.drop_index('idx_telegram_sessions_locked', table_name='telegram_sessions')
    op.drop_index('idx_telegram_sessions_status', table_name='telegram_sessions')
    
    # Drop constraint
    op.drop_constraint('ck_telegram_sessions_status', 'telegram_sessions', type_='check')
    
    # Drop columns
    op.drop_column('telegram_sessions', 'reset_at')
    op.drop_column('telegram_sessions', 'last_used_at')
    op.drop_column('telegram_sessions', 'error_count')
    op.drop_column('telegram_sessions', 'blocked_until')
    op.drop_column('telegram_sessions', 'flood_wait_until')
    op.drop_column('telegram_sessions', 'per_channel_invites')
    op.drop_column('telegram_sessions', 'contacts_today')
    op.drop_column('telegram_sessions', 'used_messages_today')
    op.drop_column('telegram_sessions', 'used_invites_today')
    op.drop_column('telegram_sessions', 'locked_until')
    op.drop_column('telegram_sessions', 'locked_by')
    op.drop_column('telegram_sessions', 'locked')
    op.drop_column('telegram_sessions', 'status')