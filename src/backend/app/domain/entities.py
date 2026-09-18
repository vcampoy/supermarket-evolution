from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class ParseStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


class QuantityUnit(StrEnum):
    UNIT = "unit"
    KG = "kg"
    UNKNOWN = "unknown"


class ProductBasis(StrEnum):
    UNIT = "unit"
    KG = "kg"


class SyncMode(StrEnum):
    BACKFILL = "backfill"
    INCREMENTAL = "incremental"
    MANUAL = "manual"
    RECOVERY = "recovery"


class SyncStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TicketItem:
    line_index: int
    raw_description: str
    line_amount_cents: int
    quantity_unit: QuantityUnit
    quantity: Decimal | None = None
    weight_grams: int | None = None
    comparable_price_cents: int | None = None
    comparable_basis: ProductBasis | None = None
    parse_status: ParseStatus = ParseStatus.READY


@dataclass(frozen=True, slots=True)
class Ticket:
    id: UUID
    gmail_message_id: UUID
    purchased_at_utc: datetime
    purchased_local_date: date
    purchased_timezone: str
    total_cents: int
    ticket_number: str | None = None
    purchased_local_time: time | None = None
    parse_status: ParseStatus = ParseStatus.READY
