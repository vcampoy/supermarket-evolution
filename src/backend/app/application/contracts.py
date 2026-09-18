"""Stable application contracts shared by adapters and use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from app.domain.entities import ParseStatus, ProductBasis, QuantityUnit


class GmailError(Exception):
    def __init__(self, code: str, *, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason
        super().__init__(code)


class ArchiveError(Exception):
    pass


class TicketParseError(Exception):
    def __init__(self, code: str, context: dict[str, str] | None = None) -> None:
        self.code = code
        self.context = context or {}
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GmailAttachment:
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int | None


@dataclass(frozen=True, slots=True)
class GmailMessage:
    provider_message_id: str
    thread_id: str | None
    sender: str
    subject: str | None
    received_at_utc: datetime | None
    attachments: tuple[GmailAttachment, ...]


@dataclass(frozen=True, slots=True)
class ArchivedPdf:
    sha256: str
    size_bytes: int
    relative_path: str
    is_duplicate_hash: bool = False


@dataclass(frozen=True, slots=True)
class ParsedLine:
    line_index: int
    raw_description: str
    normalized_description: str
    line_amount_cents: int
    quantity_unit: QuantityUnit
    quantity: Decimal | None = None
    weight_grams: int | None = None
    explicit_unit_price_cents: int | None = None
    comparable_price_cents: int | None = None
    comparable_basis: ProductBasis | None = None
    parse_status: ParseStatus = ParseStatus.READY
    parse_note: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedTicket:
    purchased_at_utc: datetime
    purchased_local_date: date
    purchased_local_time: time | None
    purchased_timezone: str
    ticket_number: str | None
    store_name: str | None
    total_cents: int
    lines: tuple[ParsedLine, ...]
    raw_text_excerpt: str
    status: ParseStatus
    error_code: str | None = None
    error_context: dict[str, str] | None = None
    adjustments_cents: int = 0
