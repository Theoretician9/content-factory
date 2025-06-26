"""Create multi-platform parsing tables

Revision ID: 001_create_multiplatform_tables
Revises: 
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_create_multiplatform_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create multi-platform parsing tables."""
    
    # Create Platform enum with IF NOT EXISTS check
    op.execute("CREATE TYPE platform AS ENUM ('telegram', 'instagram', 'whatsapp', 'facebook') IF NOT EXISTS")
    
    # Create TaskStatus enum with IF NOT EXISTS check  
    op.execute("CREATE TYPE taskstatus AS ENUM ('pending', 'running', 'paused', 'completed', 'failed', 'waiting') IF NOT EXISTS")
    
    # Create TaskPriority enum with IF NOT EXISTS check
    op.execute("CREATE TYPE taskpriority AS ENUM ('low', 'normal', 'high') IF NOT EXISTS")
    
    # Parse Tasks table
    op.create_table(
        'parse_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('platform', postgresql.ENUM('telegram', 'instagram', 'whatsapp', 'facebook', name='platform', create_type=False), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'paused', 'completed', 'failed', 'waiting', name='taskstatus', create_type=False), nullable=False),
        sa.Column('priority', postgresql.ENUM('low', 'normal', 'high', name='taskpriority', create_type=False), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, default=0),
        sa.Column('total_items', sa.Integer(), nullable=False, default=0),
        sa.Column('processed_items', sa.Integer(), nullable=False, default=0),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('account_ids', sa.JSON(), nullable=True),
        sa.Column('current_account_id', sa.String(length=100), nullable=True),
        sa.Column('resume_data', sa.JSON(), nullable=True),
        sa.Column('output_format', sa.String(length=20), nullable=False, default='json'),
        sa.Column('include_metadata', sa.Boolean(), nullable=False, default=True),
        sa.Column('result_file_path', sa.String(length=500), nullable=True),
        sa.Column('result_count', sa.Integer(), nullable=False, default=0),
        sa.Column('celery_task_id', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for parse_tasks
    op.create_index('ix_parse_tasks_task_id', 'parse_tasks', ['task_id'], unique=True)
    op.create_index('ix_parse_tasks_user_id', 'parse_tasks', ['user_id'])
    op.create_index('ix_parse_tasks_platform', 'parse_tasks', ['platform'])
    op.create_index('ix_parse_tasks_status', 'parse_tasks', ['status'])
    op.create_index('ix_parse_tasks_priority', 'parse_tasks', ['priority'])
    op.create_index('ix_parse_tasks_celery_task_id', 'parse_tasks', ['celery_task_id'])
    
    # Parse Results table
    op.create_table(
        'parse_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('platform', postgresql.ENUM('telegram', 'instagram', 'whatsapp', 'facebook', name='platform', create_type=False), nullable=False),
        sa.Column('source_id', sa.String(length=255), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('content_id', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('author_id', sa.String(length=255), nullable=True),
        sa.Column('author_username', sa.String(length=255), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('author_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('content_created_at', sa.DateTime(), nullable=True),
        sa.Column('content_edited_at', sa.DateTime(), nullable=True),
        sa.Column('views_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('likes_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('shares_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('comments_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('reactions_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('has_media', sa.Boolean(), nullable=False, default=False),
        sa.Column('media_count', sa.Integer(), nullable=False, default=0),
        sa.Column('media_types', sa.JSON(), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('latitude', sa.String(length=50), nullable=True),
        sa.Column('longitude', sa.String(length=50), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('sentiment_score', sa.String(length=20), nullable=True),
        sa.Column('platform_data', sa.JSON(), nullable=True),
        sa.Column('urls', sa.JSON(), nullable=True),
        sa.Column('mentions', sa.JSON(), nullable=True),
        sa.Column('hashtags', sa.JSON(), nullable=True),
        sa.Column('is_forwarded', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_reply', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_edited', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, default=False),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('search_vector', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['parse_tasks.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for parse_results
    op.create_index('ix_parse_results_task_id', 'parse_results', ['task_id'])
    op.create_index('ix_parse_results_platform', 'parse_results', ['platform'])
    op.create_index('ix_parse_results_source_id', 'parse_results', ['source_id'])
    op.create_index('ix_parse_results_content_id', 'parse_results', ['content_id'])
    op.create_index('ix_parse_results_author_id', 'parse_results', ['author_id'])
    op.create_index('ix_parse_results_content_created_at', 'parse_results', ['content_created_at'])
    
    # Parse Result Media table
    op.create_table(
        'parse_result_media',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('result_id', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('media_url', sa.String(length=1000), nullable=True),
        sa.Column('local_path', sa.String(length=500), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('is_downloaded', sa.Boolean(), nullable=False, default=False),
        sa.Column('download_error', sa.Text(), nullable=True),
        sa.Column('platform_media_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['result_id'], ['parse_results.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for parse_result_media
    op.create_index('ix_parse_result_media_result_id', 'parse_result_media', ['result_id'])
    
    # Platform Chats table
    op.create_table(
        'platform_chats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('platform', postgresql.ENUM('telegram', 'instagram', 'whatsapp', 'facebook', name='platform', create_type=False), nullable=False),
        sa.Column('chat_id', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('chat_type', sa.String(length=50), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_private', sa.Boolean(), nullable=False, default=False),
        sa.Column('members_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('messages_count', sa.BigInteger(), nullable=False, default=0),
        sa.Column('platform_data', sa.JSON(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('last_parsed', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for platform_chats
    op.create_index('ix_platform_chats_platform', 'platform_chats', ['platform'])
    op.create_index('ix_platform_chats_chat_id', 'platform_chats', ['chat_id'])
    op.create_index('ix_platform_chats_username', 'platform_chats', ['username'])
    
    # Create unique constraint for platform + chat_id
    op.create_index(
        'ix_platform_chats_platform_chat_id_unique', 
        'platform_chats', 
        ['platform', 'chat_id'], 
        unique=True
    )


def downgrade() -> None:
    """Drop multi-platform parsing tables."""
    
    # Drop tables
    op.drop_table('platform_chats')
    op.drop_table('parse_result_media')
    op.drop_table('parse_results')
    op.drop_table('parse_tasks')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS taskpriority')
    op.execute('DROP TYPE IF EXISTS taskstatus')
    op.execute('DROP TYPE IF EXISTS platform')
