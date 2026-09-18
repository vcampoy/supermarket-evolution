"""SQLAlchemy read repositories used by API use cases."""

from __future__ import annotations

import unicodedata
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.application.queries import PageResult
from app.infrastructure.models import ProductModel, SyncRunModel, TicketItemModel, TicketModel


def _search_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


class SqlAlchemyQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_tickets(self, *, page: int, page_size: int) -> PageResult[tuple[TicketModel, int]]:
        total = int(await self.session.scalar(select(func.count(TicketModel.id))) or 0)
        line_counts = (
            select(TicketItemModel.ticket_id, func.count(TicketItemModel.id).label("line_count"))
            .group_by(TicketItemModel.ticket_id)
            .subquery()
        )
        result = await self.session.execute(
            select(TicketModel, func.coalesce(line_counts.c.line_count, 0).label("line_count"))
            .outerjoin(line_counts, line_counts.c.ticket_id == TicketModel.id)
            .order_by(TicketModel.purchased_at_utc.desc(), TicketModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return PageResult(list(result.tuples().all()), page, page_size, total)


    async def get_ticket(self, ticket_id: UUID) -> TicketModel | None:
        return cast(TicketModel | None, await self.session.scalar(
            select(TicketModel)
            .where(TicketModel.id == str(ticket_id))
            .options(
                joinedload(TicketModel.gmail_message),
                selectinload(TicketModel.items).selectinload(TicketItemModel.product),
            )
        ))

    async def search_products(self, *, query: str, limit: int) -> list[ProductModel]:
        # SQLite has no portable accent-insensitive collation. The bounded read
        # keeps matching deterministic while preserving the canonical spelling.
        result = await self.session.scalars(
            select(ProductModel)
            .where(ProductModel.status == "active")
            .order_by(ProductModel.canonical_name.asc(), ProductModel.id.asc())
            .limit(2000)
        )
        needle = _search_key(query)
        matches = [
            product
            for product in result
            if needle in _search_key(product.canonical_name)
            or needle in _search_key(product.normalization_key)
        ]
        return matches[:limit]

    async def get_product(self, product_id: UUID) -> ProductModel | None:
        return cast(ProductModel | None, await self.session.scalar(
            select(ProductModel).where(
                ProductModel.id == str(product_id), ProductModel.status == "active"
            )
        ))

    async def get_product_history(self, product_id: UUID) -> list[tuple[TicketItemModel, TicketModel]]:
        result = await self.session.execute(
            select(TicketItemModel, TicketModel)
            .join(TicketModel, TicketModel.id == TicketItemModel.ticket_id)
            .where(
                TicketItemModel.product_id == str(product_id),
                TicketItemModel.parse_status == "ready",
                TicketItemModel.comparable_price_cents.is_not(None),
                TicketItemModel.comparable_basis == select(ProductModel.comparable_basis)
                .where(ProductModel.id == str(product_id))
                .scalar_subquery(),
            )
            .order_by(TicketModel.purchased_at_utc.asc(), TicketModel.id.asc(), TicketItemModel.line_index.asc())
        )
        return list(result.tuples().all())

    async def list_product_tickets(self, *, product_id: UUID, page: int, page_size: int) -> PageResult[tuple[TicketItemModel, TicketModel]]:
        base = (
            select(TicketItemModel.id)
            .join(TicketModel, TicketModel.id == TicketItemModel.ticket_id)
            .where(
                TicketItemModel.product_id == str(product_id),
                TicketItemModel.parse_status == "ready",
                TicketItemModel.comparable_price_cents.is_not(None),
            )
        ).subquery()
        total = int(await self.session.scalar(select(func.count()).select_from(base)) or 0)
        result = await self.session.execute(
            select(TicketItemModel, TicketModel)
            .join(TicketModel, TicketModel.id == TicketItemModel.ticket_id)
            .where(
                TicketItemModel.product_id == str(product_id),
                TicketItemModel.parse_status == "ready",
                TicketItemModel.comparable_price_cents.is_not(None),
            )
            .order_by(TicketModel.purchased_at_utc.desc(), TicketModel.id.desc(), TicketItemModel.line_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return PageResult(list(result.tuples().all()), page, page_size, total)


class SqlAlchemySyncQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_sync(self) -> SyncRunModel | None:
        return cast(
            SyncRunModel | None,
            await self.session.scalar(
                select(SyncRunModel).order_by(SyncRunModel.created_at_utc.desc()).limit(1)
            ),
        )

    async def get_sync(self, run_id: UUID) -> SyncRunModel | None:
        return await self.session.get(SyncRunModel, str(run_id))
