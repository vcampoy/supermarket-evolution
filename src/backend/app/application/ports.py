from typing import Protocol
from uuid import UUID

from app.domain.entities import Ticket


class TicketRepository(Protocol):
    async def get(self, ticket_id: UUID) -> Ticket | None: ...

    async def add(self, ticket: Ticket) -> None: ...
