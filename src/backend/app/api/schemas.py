"""Public JSON schemas for the versioned API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ErrorBody(APIModel):
    code: str = Field(examples=["TICKET_NOT_FOUND"])
    message: str = Field(examples=["Ticket not found"])
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(alias="requestId", examples=["req_01J..."])


class ErrorResponse(APIModel):
    error: ErrorBody

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "error": {
                        "code": "TICKET_NOT_FOUND",
                        "message": "Ticket not found",
                        "details": {},
                        "requestId": "req_01J...",
                    }
                }
            ]
        },
    )


class PageMeta(APIModel):
    page: int
    page_size: int = Field(alias="pageSize")
    total_items: int = Field(alias="totalItems")
    total_pages: int = Field(alias="totalPages")


class TicketSummary(APIModel):
    id: UUID
    purchased_at: datetime = Field(alias="purchasedAt")
    timezone: str
    line_count: int = Field(alias="lineCount")
    total_cents: int = Field(alias="totalCents")
    parse_status: str = Field(alias="parseStatus")


class TicketListResponse(PageMeta):
    items: list[TicketSummary]


class ProductRef(APIModel):
    id: UUID
    name: str
    basis: Literal["unit", "kg"]


class TicketItemResponse(APIModel):
    id: UUID
    line_index: int = Field(alias="lineIndex")
    raw_description: str = Field(alias="rawDescription")
    product: ProductRef | None
    quantity: str | None
    quantity_unit: str = Field(alias="quantityUnit")
    weight_grams: int | None = Field(alias="weightGrams")
    comparable_price_cents: int | None = Field(alias="comparablePriceCents")
    comparable_basis: Literal["unit", "kg"] | None = Field(alias="comparableBasis")
    line_amount_cents: int = Field(alias="lineAmountCents")
    parse_status: str = Field(alias="parseStatus")


class OriginalPdf(APIModel):
    available: bool
    sha256: str | None = None


class TicketDetailResponse(APIModel):
    id: UUID
    ticket_number: str | None = Field(alias="ticketNumber")
    purchased_at: datetime = Field(alias="purchasedAt")
    timezone: str
    total_cents: int = Field(alias="totalCents")
    parse_status: str = Field(alias="parseStatus")
    original_pdf: OriginalPdf = Field(alias="originalPdf")
    items: list[TicketItemResponse]


class ProductSearchItem(APIModel):
    id: UUID
    name: str
    basis: Literal["unit", "kg"]
    match: str


class ProductSearchResponse(APIModel):
    items: list[ProductSearchItem]


class HistoryPoint(APIModel):
    ticket_id: UUID = Field(alias="ticketId")
    purchased_at: datetime = Field(alias="purchasedAt")
    price_cents: int = Field(alias="priceCents")
    basis: Literal["unit", "kg"]


class PriceSummary(APIModel):
    first_price_cents: int | None = Field(alias="firstPriceCents")
    last_price_cents: int | None = Field(alias="lastPriceCents")
    minimum_price_cents: int | None = Field(alias="minimumPriceCents")
    maximum_price_cents: int | None = Field(alias="maximumPriceCents")
    change_cents: int | None = Field(alias="changeCents")
    change_percent: Decimal | None = Field(alias="changePercent")
    observation_count: int = Field(alias="observationCount")


class ProductDetailResponse(APIModel):
    id: UUID
    name: str
    basis: Literal["unit", "kg"]
    summary: PriceSummary
    price_history: list[HistoryPoint] = Field(alias="priceHistory")


class ProductHistoryResponse(APIModel):
    product_id: UUID = Field(alias="productId")
    basis: Literal["unit", "kg"]
    summary: PriceSummary
    points: list[HistoryPoint]


class ProductTicketAppearance(APIModel):
    ticket_id: UUID = Field(alias="ticketId")
    purchased_at: datetime = Field(alias="purchasedAt")
    line_amount_cents: int = Field(alias="lineAmountCents")
    comparable_price_cents: int = Field(alias="comparablePriceCents")
    basis: Literal["unit", "kg"]


class ProductTicketResponse(PageMeta):
    items: list[ProductTicketAppearance]


class SyncRunRequest(APIModel):
    mode: Literal["manual", "backfill", "incremental", "recovery"] = "manual"


class SyncRunAccepted(APIModel):
    id: UUID
    mode: str
    status: str


class SyncErrorCount(APIModel):
    code: str
    count: int


class SyncRunResponse(APIModel):
    id: UUID
    mode: str
    status: str
    matched_messages: int = Field(alias="matchedMessages")
    imported_tickets: int = Field(alias="importedTickets")
    skipped_duplicates: int = Field(alias="skippedDuplicates")
    partial_tickets: int = Field(alias="partialTickets")
    error_count: int = Field(alias="errorCount")
    errors: list[SyncErrorCount]


class LastRun(APIModel):
    id: UUID
    mode: str
    status: str
    started_at: datetime | None = Field(alias="startedAt")
    finished_at: datetime | None = Field(alias="finishedAt")
    imported_tickets: int = Field(alias="importedTickets")
    partial_tickets: int = Field(alias="partialTickets")
    error_count: int = Field(alias="errorCount")


class SyncStatusResponse(APIModel):
    running: bool
    last_run: LastRun | None = Field(alias="lastRun")
    next_scheduled_at: datetime | None = Field(alias="nextScheduledAt")
    host_online: bool = Field(alias="hostOnline")


class HealthResponse(APIModel):
    status: Literal["ok"]
    database: Literal["ok"]
    version: str
