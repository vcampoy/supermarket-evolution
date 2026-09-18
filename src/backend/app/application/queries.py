"""Read-side use cases for the HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, TypeVar
from uuid import UUID


class QueryError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, object] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


T = TypeVar("T")
H = TypeVar("H")


@dataclass(frozen=True, slots=True)
class PageResult[T]:
    items: list[T]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        return (self.total_items + self.page_size - 1) // self.page_size


L = TypeVar("L")
D = TypeVar("D")


class TicketQueryRepository[L, D](Protocol):
    async def list_tickets(self, *, page: int, page_size: int) -> PageResult[L]: ...

    async def get_ticket(self, ticket_id: UUID) -> D | None: ...


class ProductQueryRepository(Protocol[T, H]):
    async def search_products(self, *, query: str, limit: int) -> list[T]: ...

    async def get_product(self, product_id: UUID) -> T | None: ...

    async def get_product_history(self, product_id: UUID) -> list[H]: ...

    async def list_product_tickets(self, *, product_id: UUID, page: int, page_size: int) -> PageResult[H]: ...


class TicketQueryService[L, D]:
    def __init__(self, repository: TicketQueryRepository[L, D]) -> None:
        self.repository = repository

    async def list(self, *, page: int, page_size: int) -> PageResult[L]:
        return await self.repository.list_tickets(page=page, page_size=page_size)

    async def get(self, ticket_id: UUID) -> D:
        result = await self.repository.get_ticket(ticket_id)
        if result is None:
            raise QueryError("TICKET_NOT_FOUND", "Ticket not found")
        return result


class ProductQueryService[T, H]:
    def __init__(self, repository: ProductQueryRepository[T, H]) -> None:
        self.repository = repository

    async def search(self, *, query: str, limit: int) -> list[T]:
        return await self.repository.search_products(query=query, limit=limit)

    async def get(self, product_id: UUID) -> T:
        result = await self.repository.get_product(product_id)
        if result is None:
            raise QueryError("PRODUCT_NOT_FOUND", "Product not found")
        return result

    async def history(self, product_id: UUID) -> list[H]:
        if await self.repository.get_product(product_id) is None:
            raise QueryError("PRODUCT_NOT_FOUND", "Product not found")
        return await self.repository.get_product_history(product_id)

    async def tickets(self, *, product_id: UUID, page: int, page_size: int) -> PageResult[H]:
        if await self.repository.get_product(product_id) is None:
            raise QueryError("PRODUCT_NOT_FOUND", "Product not found")
        return await self.repository.list_product_tickets(product_id=product_id, page=page, page_size=page_size)


class SyncQueryRepository[T](Protocol):
    async def latest_sync(self) -> T | None: ...

    async def get_sync(self, run_id: UUID) -> T | None: ...


class SyncQueryService[T]:
    def __init__(self, repository: SyncQueryRepository[T]) -> None:
        self.repository = repository

    async def latest(self) -> T | None:
        return await self.repository.latest_sync()

    async def get(self, run_id: UUID) -> T:
        result = await self.repository.get_sync(run_id)
        if result is None:
            raise QueryError("SYNC_RUN_NOT_FOUND", "Sync run not found")
        return result


@dataclass(frozen=True, slots=True)
class PriceHistorySummary:
    first_price_cents: int | None
    last_price_cents: int | None
    minimum_price_cents: int | None
    maximum_price_cents: int | None
    change_cents: int | None
    change_percent: Decimal | None
    observation_count: int


def summarize_prices(prices: list[int]) -> PriceHistorySummary:
    if not prices:
        return PriceHistorySummary(None, None, None, None, None, None, 0)
    first = prices[0]
    last = prices[-1]
    change = last - first if len(prices) > 1 else None
    percent = None
    if change is not None and first != 0:
        percent = (Decimal(change) * Decimal("100") / Decimal(first)).quantize(Decimal("0.01"))
    return PriceHistorySummary(first, last, min(prices), max(prices), change, percent, len(prices))
