"""Create the local-first domain schema.

Revision ID: 0001_initial
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("gmail_messages", sa.Column("id", sa.String(36), primary_key=True), sa.Column("provider_message_id", sa.String(255), nullable=False), sa.Column("thread_id", sa.String(255)), sa.Column("sender", sa.String(320), nullable=False), sa.Column("subject", sa.String(998)), sa.Column("received_at_utc", sa.DateTime(timezone=True)), sa.Column("attachment_filename", sa.String(255), nullable=False), sa.Column("attachment_size_bytes", sa.BigInteger(), nullable=False), sa.Column("attachment_sha256", sa.String(64), nullable=False), sa.Column("original_pdf_path", sa.String(1024), nullable=False), sa.Column("parse_status", sa.String(16), nullable=False), sa.Column("parser_version", sa.String(32)), sa.Column("parse_error_code", sa.String(64)), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("provider_message_id"))
    op.create_index("ix_gmail_messages_received_at", "gmail_messages", ["received_at_utc"])
    op.create_index("ix_gmail_messages_sha256", "gmail_messages", ["attachment_sha256"])
    op.create_table("products", sa.Column("id", sa.String(36), primary_key=True), sa.Column("canonical_name", sa.String(255), nullable=False), sa.Column("normalization_key", sa.String(255), nullable=False), sa.Column("comparable_basis", sa.String(8), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("normalization_key", "comparable_basis", name="uq_products_normalization_basis"))
    op.create_table("sync_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("mode", sa.String(16), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("started_at_utc", sa.DateTime(timezone=True)), sa.Column("finished_at_utc", sa.DateTime(timezone=True)), sa.Column("query", sa.String(2000)), sa.Column("matched_messages", sa.Integer(), nullable=False, server_default="0"), sa.Column("imported_tickets", sa.Integer(), nullable=False, server_default="0"), sa.Column("skipped_duplicates", sa.Integer(), nullable=False, server_default="0"), sa.Column("partial_tickets", sa.Integer(), nullable=False, server_default="0"), sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_error_code", sa.String(64)), sa.Column("watermark_received_at_utc", sa.DateTime(timezone=True)), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sync_runs_created_at", "sync_runs", ["created_at_utc"])
    op.create_table("tickets", sa.Column("id", sa.String(36), primary_key=True), sa.Column("gmail_message_id", sa.String(36), sa.ForeignKey("gmail_messages.id"), nullable=False), sa.Column("ticket_number", sa.String(64)), sa.Column("purchased_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("purchased_local_date", sa.Date(), nullable=False), sa.Column("purchased_local_time", sa.Time()), sa.Column("purchased_timezone", sa.String(32), nullable=False), sa.Column("total_cents", sa.Integer(), nullable=False), sa.Column("parse_status", sa.String(16), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("gmail_message_id"), sa.CheckConstraint("total_cents >= 0", name="ck_tickets_total_cents_non_negative"))
    op.create_index("ix_tickets_purchased_at", "tickets", ["purchased_at_utc", "id"])
    op.create_index("ix_tickets_local_date", "tickets", ["purchased_local_date"])
    op.create_table("product_aliases", sa.Column("id", sa.String(36), primary_key=True), sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False), sa.Column("raw_description", sa.String(255), nullable=False), sa.Column("normalized_description", sa.String(255), nullable=False), sa.Column("normalization_key", sa.String(255), nullable=False), sa.Column("comparable_basis", sa.String(8), nullable=False), sa.Column("resolution", sa.String(16), nullable=False), sa.Column("normalization_version", sa.String(32), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("normalization_key", "comparable_basis", name="uq_aliases_normalization_basis"))
    op.create_table("ticket_items", sa.Column("id", sa.String(36), primary_key=True), sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False), sa.Column("line_index", sa.Integer(), nullable=False), sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id")), sa.Column("raw_description", sa.String(255), nullable=False), sa.Column("normalized_description", sa.String(255)), sa.Column("quantity", sa.Numeric(12, 3)), sa.Column("quantity_unit", sa.String(8), nullable=False), sa.Column("weight_grams", sa.Integer()), sa.Column("explicit_unit_price_cents", sa.Integer()), sa.Column("line_amount_cents", sa.Integer(), nullable=False), sa.Column("comparable_price_cents", sa.Integer()), sa.Column("comparable_basis", sa.String(8)), sa.Column("parse_status", sa.String(16), nullable=False), sa.Column("parse_note", sa.String(255)), sa.UniqueConstraint("ticket_id", "line_index", name="uq_ticket_items_ticket_line"), sa.CheckConstraint("line_amount_cents >= 0", name="ck_ticket_items_amount_non_negative"))
    op.create_index("ix_ticket_items_product_ticket", "ticket_items", ["product_id", "ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_items_product_ticket", table_name="ticket_items")
    op.drop_table("ticket_items")
    op.drop_table("product_aliases")
    op.drop_index("ix_tickets_local_date", table_name="tickets")
    op.drop_index("ix_tickets_purchased_at", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index("ix_sync_runs_created_at", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_table("products")
    op.drop_index("ix_gmail_messages_sha256", table_name="gmail_messages")
    op.drop_index("ix_gmail_messages_received_at", table_name="gmail_messages")
    op.drop_table("gmail_messages")
