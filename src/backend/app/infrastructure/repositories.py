from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import TicketModel


class SqlAlchemyTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def exists(self, ticket_id: UUID) -> bool:
        result = await self.session.scalar(select(TicketModel.id).where(TicketModel.id == str(ticket_id)))
        return result is not None
