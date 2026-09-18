from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.application.ingestion import TicketSyncService
from app.domain.entities import ParseStatus, ProductBasis, QuantityUnit
from app.infrastructure.archive import PdfArchive
from app.infrastructure.gmail import GmailAttachment, GmailError, GmailMessage
from app.infrastructure.parser import ParsedLine, ParsedTicket, TicketParseError


def message(message_id: str, attachment_id: str = "a1") -> GmailMessage:
    return GmailMessage(
        provider_message_id=message_id,
        thread_id=None,
        sender="ticket_digital@mail.mercadona.com",
        subject="20260917 Mercadona 1,00 €",
        received_at_utc=datetime(2026, 9, 17, tzinfo=UTC),
        attachments=(GmailAttachment(attachment_id, "ticket.pdf", "application/pdf", None),),
    )


def parsed() -> ParsedTicket:
    line = ParsedLine(1, "Pan", "pan", 100, QuantityUnit.UNIT, quantity=1, comparable_price_cents=100, comparable_basis=ProductBasis.UNIT)
    return ParsedTicket(
        purchased_at_utc=datetime(2026, 9, 17, tzinfo=UTC),
        purchased_local_date=datetime(2026, 9, 17, tzinfo=UTC).date(),
        purchased_local_time=None,
        purchased_timezone="Europe/Madrid",
        ticket_number="1",
        store_name=None,
        total_cents=100,
        lines=(line,),
        raw_text_excerpt="safe excerpt",
        status=ParseStatus.READY,
    )


class FakeGmail:
    def __init__(self, messages: list[GmailMessage], payloads: dict[str, bytes], failures: set[str] | None = None) -> None:
        self.messages = messages
        self.payloads = payloads
        self.failures = failures or set()

    async def list_messages(self, _query: str):
        for item in self.messages:
            yield item

    async def download_attachment(self, message_id: str, _attachment: GmailAttachment) -> bytes:
        if message_id in self.failures:
            raise GmailError("DOWNLOAD_INTERRUPTED")
        return self.payloads[message_id]


class FakeRepository:
    def __init__(self) -> None:
        self.messages: dict[str, str] = {}
        self.hashes: set[str] = set()
        self.failed: list[str] = []

    async def last_received_at(self):
        return None

    async def rollback(self):
        return None

    async def has_message(self, provider_message_id: str) -> bool:
        return provider_message_id in self.messages

    async def save_message(self, *, message, attachment, archived, parsed, error_code=None) -> str:
        if message.provider_message_id in self.messages:
            return "message_duplicate"
        if archived.sha256 in self.hashes:
            self.messages[message.provider_message_id] = "hash_duplicate"
            return "hash_duplicate"
        self.messages[message.provider_message_id] = "failed" if parsed is None else "imported"
        self.hashes.add(archived.sha256)
        if parsed is None:
            self.failed.append(error_code or "unknown")
        return self.messages[message.provider_message_id]


@pytest.mark.asyncio
async def test_sync_is_idempotent_by_message_and_hash(tmp_path: Path) -> None:
    data = b"%PDF same"
    repo = FakeRepository()
    service = TicketSyncService(
        gmail=FakeGmail([message("m1"), message("m2")], {"m1": data, "m2": data}),
        repository=repo,
        archive=PdfArchive(tmp_path),
        parser=lambda _data: parsed(),
    )
    first = await service.sync(mode="backfill", query="q")
    second = await service.sync(mode="backfill", query="q")
    assert first.imported_tickets == 1
    assert first.skipped_duplicates == 1
    assert second.skipped_duplicates == 2
    assert len(list(tmp_path.rglob("*.pdf"))) == 1


@pytest.mark.asyncio
async def test_download_failure_does_not_abort_other_messages(tmp_path: Path) -> None:
    repo = FakeRepository()
    service = TicketSyncService(
        gmail=FakeGmail([message("bad"), message("good")], {"good": b"%PDF good"}, {"bad"}),
        repository=repo,
        archive=PdfArchive(tmp_path),
        parser=lambda _data: parsed(),
    )
    summary = await service.sync(mode="backfill", query="q")
    assert summary.error_count == 1
    assert summary.imported_tickets == 1


@pytest.mark.asyncio
async def test_ilegible_ticket_is_persisted_as_failed(tmp_path: Path) -> None:
    def fail(_data):
        raise TicketParseError("PDF_UNREADABLE")

    repo = FakeRepository()
    service = TicketSyncService(
        gmail=FakeGmail([message("m1")], {"m1": b"%PDF unreadable"}),
        repository=repo,
        archive=PdfArchive(tmp_path),
        parser=fail,
    )
    summary = await service.sync(mode="backfill", query="q")
    assert summary.error_count == 1
    assert repo.messages["m1"] == "failed"
    assert repo.failed == ["PDF_UNREADABLE"]
