from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db import Base


class GmailMessageModel(Base):
    __tablename__ = "gmail_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    provider_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(255))
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(998))
    received_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attachment_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    attachment_id: Mapped[str | None] = mapped_column(String(255))
    attachment_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attachment_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_pdf_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(32))
    parse_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ticket: Mapped["TicketModel | None"] = relationship(back_populates="gmail_message")
    __table_args__ = (Index("ix_gmail_messages_received_at", "received_at_utc"), Index("ix_gmail_messages_sha256", "attachment_sha256"))


class TicketModel(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    gmail_message_id: Mapped[str] = mapped_column(ForeignKey("gmail_messages.id"), unique=True, nullable=False)
    ticket_number: Mapped[str | None] = mapped_column(String(64))
    purchased_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purchased_local_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchased_local_time: Mapped[time | None] = mapped_column(Time)
    purchased_timezone: Mapped[str] = mapped_column(String(32), nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    store_name: Mapped[str | None] = mapped_column(String(255))
    raw_text_excerpt: Mapped[str | None] = mapped_column(String(1000))
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gmail_message: Mapped[GmailMessageModel] = relationship(back_populates="ticket")
    items: Mapped[list["TicketItemModel"]] = relationship(back_populates="ticket", cascade="save-update, merge")
    __table_args__ = (Index("ix_tickets_purchased_at", "purchased_at_utc", "id"), Index("ix_tickets_local_date", "purchased_local_date"), CheckConstraint("total_cents >= 0", name="ck_tickets_total_cents_non_negative"))


class ProductModel(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalization_key: Mapped[str] = mapped_column(String(255), nullable=False)
    comparable_basis: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    items: Mapped[list["TicketItemModel"]] = relationship(back_populates="product")
    aliases: Mapped[list["ProductAliasModel"]] = relationship(back_populates="product")
    __table_args__ = (UniqueConstraint("normalization_key", "comparable_basis", name="uq_products_normalization_basis"),)


class ProductAliasModel(Base):
    __tablename__ = "product_aliases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    raw_description: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_description: Mapped[str] = mapped_column(String(255), nullable=False)
    normalization_key: Mapped[str] = mapped_column(String(255), nullable=False)
    comparable_basis: Mapped[str] = mapped_column(String(8), nullable=False)
    resolution: Mapped[str] = mapped_column(String(16), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    product: Mapped[ProductModel] = relationship(back_populates="aliases")
    __table_args__ = (UniqueConstraint("normalization_key", "comparable_basis", name="uq_aliases_normalization_basis"),)


class TicketItemModel(Base):
    __tablename__ = "ticket_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False)
    line_index: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    raw_description: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    quantity_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    explicit_unit_price_cents: Mapped[int | None] = mapped_column(Integer)
    line_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    comparable_price_cents: Mapped[int | None] = mapped_column(Integer)
    comparable_basis: Mapped[str | None] = mapped_column(String(8))
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False)
    parse_note: Mapped[str | None] = mapped_column(String(255))
    ticket: Mapped[TicketModel] = relationship(back_populates="items")
    product: Mapped[ProductModel | None] = relationship(back_populates="items")
    __table_args__ = (UniqueConstraint("ticket_id", "line_index", name="uq_ticket_items_ticket_line"), Index("ix_ticket_items_product_ticket", "product_id", "ticket_id"), CheckConstraint("line_amount_cents >= 0", name="ck_ticket_items_amount_non_negative"))


class SyncRunModel(Base):
    __tablename__ = "sync_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    query: Mapped[str | None] = mapped_column(String(2000))
    matched_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_tickets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partial_tickets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    watermark_received_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_sync_runs_created_at", "created_at_utc"),)
