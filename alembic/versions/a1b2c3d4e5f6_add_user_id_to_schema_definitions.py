"""add_user_id_to_schema_definitions

Revision ID: a1b2c3d4e5f6
Revises: 46d6eb456b90
Create Date: 2025-11-03 17:44:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9eb4490a7535'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id to schema_definitions table."""
    # Add user_id column as nullable first
    op.add_column('schema_definitions', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Get the admin user ID to assign existing schemas
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM users WHERE is_admin = true LIMIT 1"))
    admin_row = result.fetchone()
    
    if admin_row:
        admin_id = admin_row[0]
        # Set all existing schemas to belong to admin user
        conn.execute(
            sa.text("UPDATE schema_definitions SET user_id = :admin_id WHERE user_id IS NULL"),
            {"admin_id": str(admin_id)}
        )
    
    # Add index and foreign key
    op.create_index(op.f('ix_schema_definitions_user_id'), 'schema_definitions', ['user_id'], unique=False)
    op.create_foreign_key('fk_schema_definitions_user_id', 'schema_definitions', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Remove user_id from schema_definitions table."""
    op.drop_constraint('fk_schema_definitions_user_id', 'schema_definitions', type_='foreignkey')
    op.drop_index(op.f('ix_schema_definitions_user_id'), table_name='schema_definitions')
    op.drop_column('schema_definitions', 'user_id')
