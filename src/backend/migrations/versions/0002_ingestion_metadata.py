"""Add attachment and safe parser-audit metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0002_ingestion_metadata"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gmail_messages", sa.Column("attachment_id", sa.String(255), nullable=True))
    op.add_column("tickets", sa.Column("store_name", sa.String(255), nullable=True))
    op.add_column("tickets", sa.Column("raw_text_excerpt", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("tickets", "raw_text_excerpt")
    op.drop_column("tickets", "store_name")
    op.drop_column("gmail_messages", "attachment_id")
