from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.main import _next_scheduled_at, app, coordinator
from app.infrastructure.db import Base, get_session
from app.infrastructure.models import GmailMessageModel, ProductModel, TicketItemModel, TicketModel


@pytest.fixture
async def api_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, sessions, engine
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def add_ticket(session, *, purchased_at: datetime, ticket_id: str | None = None, product_id: str | None = None, price: int | None = None, basis: str | None = None, quantity: Decimal | None = None):
    ticket_id = ticket_id or str(uuid4())
    message_id = str(uuid4())
    session.add(GmailMessageModel(provider_message_id=message_id, sender="sender", attachment_filename="ticket.pdf", attachment_size_bytes=1, attachment_sha256=uuid4().hex, original_pdf_path="2026-09/ticket.pdf", parse_status="ready", created_at_utc=purchased_at))
    await session.flush()
    session.add(TicketModel(id=ticket_id, gmail_message_id=message_id, purchased_at_utc=purchased_at, purchased_local_date=purchased_at.date(), purchased_timezone="Europe/Madrid", total_cents=price or 100, parse_status="ready", created_at_utc=purchased_at, updated_at_utc=purchased_at))
    if product_id and price is not None and basis:
        session.add(TicketItemModel(ticket_id=ticket_id, line_index=1, product_id=product_id, raw_description="Tomate Péra", normalized_description="tomate pera", quantity=quantity, quantity_unit="kg" if basis == "kg" else "unit", weight_grams=740 if basis == "kg" else None, line_amount_cents=price, comparable_price_cents=price, comparable_basis=basis, parse_status="ready"))
    return ticket_id


@pytest.mark.asyncio
async def test_ticket_pagination_is_stable_and_bounded(api_client):
    client, sessions, _ = api_client
    async with sessions() as session:
        ids = [str(uuid4()) for _ in range(51)]
        for ticket_id in ids:
            await add_ticket(session, purchased_at=datetime(2026, 9, 17, tzinfo=UTC), ticket_id=ticket_id)
        await session.commit()
    first = await client.get("/api/v1/tickets?page=1&pageSize=50")
    second = await client.get("/api/v1/tickets?page=2&pageSize=50")
    assert first.status_code == 200
    assert len(first.json()["items"]) == 50
    assert len(second.json()["items"]) == 1
    assert [item["id"] for item in first.json()["items"]] == sorted(ids, reverse=True)[:50]


@pytest.mark.asyncio
async def test_ticket_not_found_returns_safe_error(api_client):
    client, _, _ = api_client
    response = await client.get(f"/api/v1/tickets/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"
    assert "requestId" in response.json()["error"]


@pytest.mark.asyncio
async def test_search_is_case_and_accent_insensitive(api_client):
    client, sessions, _ = api_client
    async with sessions() as session:
        session.add(ProductModel(canonical_name="Tomate Péra", normalization_key="tomate pera", comparable_basis="unit", status="active", created_at_utc=datetime.now(UTC), updated_at_utc=datetime.now(UTC)))
        await session.commit()
    response = await client.get("/api/v1/products/search?q=TÓMATE&limit=20")
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Tomate Péra"


@pytest.mark.asyncio
async def test_history_keeps_unit_and_kg_series_separate(api_client):
    client, sessions, _ = api_client
    unit_id, kg_id = str(uuid4()), str(uuid4())
    async with sessions() as session:
        now = datetime(2026, 9, 17, tzinfo=UTC)
        session.add_all([
            ProductModel(id=unit_id, canonical_name="Tomate Péra", normalization_key="tomate pera", comparable_basis="unit", status="active", created_at_utc=now, updated_at_utc=now),
            ProductModel(id=kg_id, canonical_name="Tomate Péra", normalization_key="tomate pera", comparable_basis="kg", status="active", created_at_utc=now, updated_at_utc=now),
        ])
        await session.flush()
        await add_ticket(session, purchased_at=now, product_id=unit_id, price=200, basis="unit", quantity=Decimal("1"))
        await add_ticket(session, purchased_at=now, product_id=kg_id, price=300, basis="kg")
        await session.commit()
    response = await client.get(f"/api/v1/products/{unit_id}/history")
    assert response.status_code == 200
    assert response.json()["basis"] == "unit"
    assert [point["basis"] for point in response.json()["points"]] == ["unit"]


@pytest.mark.asyncio
async def test_single_point_and_zero_initial_price_have_null_variation(api_client):
    client, sessions, _ = api_client
    product_id = str(uuid4())
    async with sessions() as session:
        now = datetime(2026, 9, 17, tzinfo=UTC)
        session.add(ProductModel(id=product_id, canonical_name="Pan", normalization_key="pan", comparable_basis="unit", status="active", created_at_utc=now, updated_at_utc=now))
        await session.flush()
        await add_ticket(session, purchased_at=now, product_id=product_id, price=0, basis="unit", quantity=Decimal("1"))
        await session.commit()
    response = await client.get(f"/api/v1/products/{product_id}")
    assert response.status_code == 200
    assert response.json()["summary"]["observationCount"] == 1
    assert response.json()["summary"]["changePercent"] is None


@pytest.mark.asyncio
async def test_ticket_list_uses_constant_query_count(api_client):
    client, sessions, engine = api_client
    async with sessions() as session:
        for _ in range(3):
            await add_ticket(session, purchased_at=datetime(2026, 9, 17, tzinfo=UTC))
        await session.commit()
    queries = 0

    def count_queries(*_args):
        nonlocal queries
        queries += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_queries)
    response = await client.get("/api/v1/tickets")
    event.remove(engine.sync_engine, "before_cursor_execute", count_queries)
    assert response.status_code == 200
    assert queries <= 2


@pytest.mark.asyncio
async def test_concurrent_sync_returns_conflict(api_client, monkeypatch):
    client, sessions, _ = api_client
    monkeypatch.setattr("app.api.main.sync_session_factory", sessions)
    release = asyncio.Event()

    async def hold_sync(*_args):
        await release.wait()

    monkeypatch.setattr("app.api.main._run_sync_job", hold_sync)
    first = await client.post("/api/v1/sync/run", json={"mode": "manual"})
    second = await client.post("/api/v1/sync/run", json={"mode": "manual"})
    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SYNC_ALREADY_RUNNING"
    release.set()
    await asyncio.sleep(0)
    await coordinator.finish()


def test_next_scheduled_at_is_the_next_local_three_am() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Europe/Madrid")
    before = _next_scheduled_at(datetime(2026, 9, 18, 2, 59, tzinfo=zone))
    after = _next_scheduled_at(datetime(2026, 9, 18, 3, 0, tzinfo=zone))
    assert before == datetime(2026, 9, 18, 3, 0, tzinfo=zone)
    assert after == datetime(2026, 9, 19, 3, 0, tzinfo=zone)
