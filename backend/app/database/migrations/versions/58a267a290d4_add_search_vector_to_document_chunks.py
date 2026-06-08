"""add_search_vector_to_document_chunks

Revision ID: 58a267a290d4
Revises: ca5dacebc29b
Create Date: 2026-06-08 20:41:19.744148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58a267a290d4'
down_revision: Union[str, Sequence[str], None] = 'ca5dacebc29b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
            GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
    """)
    op.execute("""
        CREATE INDEX ix_document_chunks_search_vector
        ON document_chunks USING GIN (search_vector)
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector")
    op.execute("ALTER TABLE document_chunks DROP COLUMN search_vector")