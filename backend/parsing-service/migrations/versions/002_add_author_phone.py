"""Add author_phone column to parse_results

Revision ID: 002_add_author_phone
Revises: 001_create_multiplatform_tables
Create Date: 2025-01-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_author_phone'
down_revision = '001_create_multiplatform_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add author_phone column to parse_results table."""
    # Add author_phone column after author_name
    op.add_column('parse_results', sa.Column('author_phone', sa.String(20), nullable=True))
    
    # Add index for phone number searches
    op.create_index('idx_parse_results_author_phone', 'parse_results', ['author_phone'])


def downgrade() -> None:
    """Remove author_phone column from parse_results table."""
    # Drop index first
    op.drop_index('idx_parse_results_author_phone', table_name='parse_results')
    
    # Drop column
    op.drop_column('parse_results', 'author_phone') 