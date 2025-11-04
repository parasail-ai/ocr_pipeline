"""add_is_public_to_schema_definitions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-03 17:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_public column to schema_definitions table."""
    # Add is_public column with default False
    op.add_column('schema_definitions', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove is_public column from schema_definitions table."""
    op.drop_column('schema_definitions', 'is_public')
