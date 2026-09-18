"""Application service for idempotent Gmail-to-ticket ingestion."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.application.contracts import (
    ArchivedPdf,
    GmailAttachment,
    GmailError,
    GmailMessage,
    ParsedTicket,
    TicketParseError,
)


class GmailGateway(Protocol):
    def list_messages(self, query: str) -> AsyncIterator[GmailMessage]: ...
    async def download_attachment(self, message_id: str, attachment: GmailAttachment) -> bytes: ...


class IngestionRepository(Protocol):
    async def last_received_at(self) -> datetime | None: ...
    async def has_message(self, provider_message_id: str) -> bool: ...
    async def rollback(self) -> None: ...
    async def save_message(
        self,
        *,
        message: GmailMessage,
        attachment: GmailAttachment,
        archived: ArchivedPdf,
        parsed: ParsedTicket | None,
        error_code: str | None = None,
    ) -> str: ...


class PdfArchiver(Protocol):
    def write(
        self,
        *,
        message_id: str,
        attachment_id: str,
        original_filename: str,
        pdf_bytes: bytes,
        received_at: datetime | None = None,
    ) -> ArchivedPdf: ...


class TicketParser(Protocol):
    def __call__(self, pdf_bytes: bytes) -> ParsedTicket: ...


@dataclass(frozen=True, slots=True)
class SyncSummary:
    mode: str
    query: str
    matched_messages: int = 0
    imported_tickets: int = 0
    skipped_duplicates: int = 0
    partial_tickets: int = 0
    error_count: int = 0
    last_error_code: str | None = None


class TicketSyncService:
    def __init__(self, *, gmail: GmailGateway, repository: IngestionRepository, archive: PdfArchiver, parser: TicketParser, max_attachment_bytes: int = 20 * 1024 * 1024) -> None:
        self.gmail = gmail
        self.repository = repository
        self.archive = archive
        self.parser = parser
        self.max_attachment_bytes = max_attachment_bytes

    async def sync(self, *, mode: str, query: str) -> SyncSummary:
        effective_query = query
        if mode in {"since-last", "incremental"}:
            watermark = await self.repository.last_received_at()
            if watermark:
                effective_query = f"{query} after:{int(watermark.timestamp())}"
        matched = imported = duplicates = partial = errors = 0
        last_error: str | None = None
        async for message in self.gmail.list_messages(effective_query):
            matched += 1
            if await self.repository.has_message(message.provider_message_id):
                duplicates += 1
                continue
            attachment = next((item for item in message.attachments if item.filename.lower().endswith(".pdf")), None)
            if attachment is None:
                errors += 1
                last_error = "PDF_ATTACHMENT_MISSING"
                continue
            try:
                pdf_bytes = await self.gmail.download_attachment(message.provider_message_id, attachment)
                if len(pdf_bytes) > self.max_attachment_bytes:
                    raise GmailError("PDF_TOO_LARGE")
                archived = self.archive.write(
                    message_id=message.provider_message_id,
                    attachment_id=attachment.attachment_id,
                    original_filename=attachment.filename,
                    pdf_bytes=pdf_bytes,
                    received_at=message.received_at_utc,
                )
                try:
                    parsed = self.parser(pdf_bytes)
                except TicketParseError as exc:
                    await self.repository.save_message(
                        message=message,
                        attachment=attachment,
                        archived=archived,
                        parsed=None,
                        error_code=exc.code,
                    )
                    errors += 1
                    last_error = exc.code
                    continue
                outcome = await self.repository.save_message(
                    message=message,
                    attachment=attachment,
                    archived=archived,
                    parsed=parsed,
                )
                if outcome == "message_duplicate":
                    duplicates += 1
                elif outcome == "hash_duplicate":
                    duplicates += 1
                else:
                    imported += 1
                    if parsed.status.value != "ready":
                        partial += 1
            except Exception as exc:
                await self.repository.rollback()
                errors += 1
                last_error = getattr(exc, "code", type(exc).__name__)
        return SyncSummary(
            mode=mode,
            query=effective_query,
            matched_messages=matched,
            imported_tickets=imported,
            skipped_duplicates=duplicates,
            partial_tickets=partial,
            error_count=errors,
            last_error_code=last_error,
        )


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> UUID:
    return uuid4()
