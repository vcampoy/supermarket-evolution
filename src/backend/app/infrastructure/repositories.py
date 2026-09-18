from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.contracts import (
    ArchivedPdf,
    GmailAttachment,
    GmailMessage,
    ParsedLine,
    ParsedTicket,
)
from app.application.ingestion import IngestionRepository
from app.infrastructure.models import GmailMessageModel, ProductModel, TicketItemModel, TicketModel


class SqlAlchemyTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists(self, ticket_id: UUID) -> bool:
        result = await self.session.scalar(select(TicketModel.id).where(TicketModel.id == str(ticket_id)))
        return result is not None


class SqlAlchemyIngestionRepository(IngestionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rollback(self) -> None:
        await self.session.rollback()

    async def last_received_at(self) -> datetime | None:
        return await self.session.scalar(select(func.max(GmailMessageModel.received_at_utc)))

    async def has_message(self, provider_message_id: str) -> bool:
        value = await self.session.scalar(
            select(GmailMessageModel.id).where(GmailMessageModel.provider_message_id == provider_message_id)
        )
        return value is not None

    async def _product_id_for_line(self, line: ParsedLine, now: datetime) -> str | None:
        if not line.comparable_basis or line.comparable_price_cents is None:
            return None
        basis = line.comparable_basis.value
        product = await self.session.scalar(
            select(ProductModel).where(
                ProductModel.normalization_key == line.normalized_description,
                ProductModel.comparable_basis == basis,
            )
        )
        if product is None:
            product = ProductModel(
                canonical_name=line.raw_description,
                normalization_key=line.normalized_description,
                comparable_basis=basis,
                status="active",
                created_at_utc=now,
                updated_at_utc=now,
            )
            self.session.add(product)
            await self.session.flush()
        return product.id

    async def save_message(
        self,
        *,
        message: GmailMessage,
        attachment: GmailAttachment,
        archived: ArchivedPdf,
        parsed: ParsedTicket | None,
        error_code: str | None = None,
    ) -> str:
        existing = await self.session.scalar(
            select(GmailMessageModel).where(GmailMessageModel.provider_message_id == message.provider_message_id)
        )
        if existing:
            return "message_duplicate"
        hash_match = await self.session.scalar(
            select(GmailMessageModel).where(GmailMessageModel.attachment_sha256 == archived.sha256)
        )
        now = datetime.now(UTC)
        gmail_model = GmailMessageModel(
            provider_message_id=message.provider_message_id,
            thread_id=message.thread_id,
            sender=message.sender,
            subject=message.subject,
            received_at_utc=message.received_at_utc,
            attachment_filename=attachment.filename,
            attachment_id=attachment.attachment_id,
            attachment_size_bytes=archived.size_bytes,
            attachment_sha256=archived.sha256,
            original_pdf_path=archived.relative_path,
            parse_status=parsed.status.value if parsed else "failed",
            parser_version="pdf-text-1" if parsed else None,
            parse_error_code=error_code or (parsed.error_code if parsed else None),
            created_at_utc=now,
        )
        self.session.add(gmail_model)
        await self.session.flush()
        if hash_match or parsed is None:
            await self.session.commit()
            return "hash_duplicate" if hash_match else "failed"
        ticket_model = TicketModel(
            gmail_message_id=gmail_model.id,
            ticket_number=parsed.ticket_number,
            purchased_at_utc=parsed.purchased_at_utc,
            purchased_local_date=parsed.purchased_local_date,
            purchased_local_time=parsed.purchased_local_time,
            purchased_timezone=parsed.purchased_timezone,
            total_cents=parsed.total_cents,
            store_name=parsed.store_name,
            raw_text_excerpt=parsed.raw_text_excerpt,
            parse_status=parsed.status.value,
            created_at_utc=now,
            updated_at_utc=now,
        )
        self.session.add(ticket_model)
        await self.session.flush()
        for line in parsed.lines:
            product_id = await self._product_id_for_line(line, now)
            self.session.add(
                TicketItemModel(
                    ticket_id=ticket_model.id,
                    line_index=line.line_index,
                    product_id=product_id,
                    raw_description=line.raw_description,
                    normalized_description=line.normalized_description,
                    quantity=line.quantity,
                    quantity_unit=line.quantity_unit.value,
                    weight_grams=line.weight_grams,
                    explicit_unit_price_cents=line.explicit_unit_price_cents,
                    line_amount_cents=line.line_amount_cents,
                    comparable_price_cents=line.comparable_price_cents,
                    comparable_basis=line.comparable_basis.value if line.comparable_basis else None,
                    parse_status=line.parse_status.value,
                    parse_note=line.parse_note,
                )
            )
        await self.session.commit()
        return "imported"

    async def failed_messages(self) -> list[GmailMessageModel]:
        result = await self.session.scalars(
            select(GmailMessageModel).where(GmailMessageModel.parse_status.in_(("failed", "partial", "needs_review")))
        )
        return list(result)

    async def replace_parsed_ticket(self, message_model: GmailMessageModel, parsed: ParsedTicket) -> None:
        now = datetime.now(UTC)
        await self.session.execute(
            delete(TicketItemModel).where(
                TicketItemModel.ticket_id.in_(select(TicketModel.id).where(TicketModel.gmail_message_id == message_model.id))
            )
        )
        await self.session.execute(delete(TicketModel).where(TicketModel.gmail_message_id == message_model.id))
        message_model.parse_status = parsed.status.value
        message_model.parser_version = "pdf-text-1"
        message_model.parse_error_code = parsed.error_code
        ticket_model = TicketModel(
            gmail_message_id=message_model.id,
            ticket_number=parsed.ticket_number,
            purchased_at_utc=parsed.purchased_at_utc,
            purchased_local_date=parsed.purchased_local_date,
            purchased_local_time=parsed.purchased_local_time,
            purchased_timezone=parsed.purchased_timezone,
            total_cents=parsed.total_cents,
            store_name=parsed.store_name,
            raw_text_excerpt=parsed.raw_text_excerpt,
            parse_status=parsed.status.value,
            created_at_utc=now,
            updated_at_utc=now,
        )
        self.session.add(ticket_model)
        await self.session.flush()
        for line in parsed.lines:
            product_id = await self._product_id_for_line(line, now)
            self.session.add(
                TicketItemModel(
                    ticket_id=ticket_model.id,
                    line_index=line.line_index,
                    product_id=product_id,
                    raw_description=line.raw_description,
                    normalized_description=line.normalized_description,
                    quantity=line.quantity,
                    quantity_unit=line.quantity_unit.value,
                    weight_grams=line.weight_grams,
                    explicit_unit_price_cents=line.explicit_unit_price_cents,
                    line_amount_cents=line.line_amount_cents,
                    comparable_price_cents=line.comparable_price_cents,
                    comparable_basis=line.comparable_basis.value if line.comparable_basis else None,
                    parse_status=line.parse_status.value,
                    parse_note=line.parse_note,
                )
            )
        await self.session.commit()
