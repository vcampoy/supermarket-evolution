"""FastAPI adapter for the local-first read and synchronization API."""

from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from app.api.schemas import (
    ErrorResponse,
    HealthResponse,
    HistoryPoint,
    LastRun,
    OriginalPdf,
    PriceSummary,
    ProductDetailResponse,
    ProductHistoryResponse,
    ProductRef,
    ProductSearchItem,
    ProductSearchResponse,
    ProductTicketAppearance,
    ProductTicketResponse,
    SyncErrorCount,
    SyncRunAccepted,
    SyncRunRequest,
    SyncRunResponse,
    SyncStatusResponse,
    TicketDetailResponse,
    TicketItemResponse,
    TicketListResponse,
    TicketSummary,
)
from app.application.ingestion import TicketSyncService
from app.application.queries import (
    ProductQueryService,
    QueryError,
    SyncQueryService,
    TicketQueryService,
    summarize_prices,
)
from app.core.config import Settings, get_settings
from app.infrastructure.archive import PdfArchive
from app.infrastructure.db import SessionFactory, get_session
from app.infrastructure.gmail import GmailApiClient
from app.infrastructure.models import ProductModel, SyncRunModel, TicketItemModel, TicketModel
from app.infrastructure.parser import parse_pdf_bytes
from app.infrastructure.query_repositories import (
    SqlAlchemyQueryRepository,
    SqlAlchemySyncQueryRepository,
)

LOCAL_ZONE = ZoneInfo("Europe/Madrid")


def _allowed_bind_host(value: str) -> bool:
    if value in {"127.0.0.1", "localhost", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and address in ipaddress.ip_network("100.64.0.0/10")


class SPAStaticFiles(StaticFiles):
    """Serve the React entry point for browser-history routes."""

    async def get_response(self, path: str, scope: Scope) -> Any:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and "." not in Path(path).name:
            return await super().get_response("index.html", scope)
        return response


class APIError(Exception):
    def __init__(
        self, code: str, message: str, http_status: int, *, details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(message)


class SyncCoordinator:
    def __init__(self) -> None:
        self._running = False
        self._lock = asyncio.Lock()

    def is_running(self) -> bool:
        return self._running

    async def try_start(self) -> bool:
        async with self._lock:
            if self._running:
                return False
            self._running = True
            return True

    async def finish(self) -> None:
        async with self._lock:
            self._running = False


coordinator = SyncCoordinator()
sync_session_factory = SessionFactory


def _request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


def _error_response(request: Request, exc: APIError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", _request_id())
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "requestId": request_id,
            }
        },
    )


def _safe_datetime(value: datetime | None, *, local: bool = False) -> datetime | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return aware.astimezone(LOCAL_ZONE if local else UTC)


def _basis(value: str | None) -> Literal["unit", "kg"]:
    assert value in {"unit", "kg"}
    return cast(Literal["unit", "kg"], value)


async def _query_timeout[QueryResult](operation: Awaitable[QueryResult]) -> QueryResult:
    try:
        async with asyncio.timeout(get_settings().api_query_timeout_seconds):
            return await operation
    except TimeoutError as exc:
        raise APIError("QUERY_TIMEOUT", "The query took too long", 504) from exc


def _required_datetime(value: datetime | None, *, local: bool = False) -> datetime:
    result = _safe_datetime(value, local=local)
    assert result is not None
    return result


def _parse_uuid(value: str, resource: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise APIError(
            "INVALID_UUID", "The identifier is invalid", 422, details={"resource": resource}
        ) from exc


def _page(page: int, page_size: int, *, exact_size: bool = True) -> tuple[int, int]:
    if page < 1:
        raise APIError("INVALID_PAGE", "Page must be greater than zero", 422)
    if exact_size and page_size != 50:
        raise APIError("INVALID_PAGE_SIZE", "Page size must be 50", 422)
    if not exact_size and not 1 <= page_size <= 50:
        raise APIError("INVALID_PAGE_SIZE", "Page size must be between 1 and 50", 422)
    return page, page_size


def _page_response(result: Any, items: list[Any]) -> dict[str, Any]:
    return {
        "items": items,
        "page": result.page,
        "pageSize": result.page_size,
        "totalItems": result.total_items,
        "totalPages": result.total_pages,
    }


def _ticket_summary(model: TicketModel, line_count: int) -> TicketSummary:
    return TicketSummary(
        id=UUID(model.id),
        purchasedAt=_required_datetime(model.purchased_at_utc, local=True),
        timezone=model.purchased_timezone,
        lineCount=line_count,
        totalCents=model.total_cents,
        parseStatus=model.parse_status,
    )


def _history_point(item: TicketItemModel, ticket: TicketModel) -> HistoryPoint:
    assert item.comparable_price_cents is not None
    return HistoryPoint(
        ticketId=UUID(ticket.id),
        purchasedAt=_required_datetime(ticket.purchased_at_utc, local=True),
        priceCents=item.comparable_price_cents,
        basis=_basis(item.comparable_basis),
    )


def _summary(prices: list[int]) -> PriceSummary:
    value = summarize_prices(prices)
    return PriceSummary(
        firstPriceCents=value.first_price_cents,
        lastPriceCents=value.last_price_cents,
        minimumPriceCents=value.minimum_price_cents,
        maximumPriceCents=value.maximum_price_cents,
        changeCents=value.change_cents,
        changePercent=value.change_percent,
        observationCount=value.observation_count,
    )


def _query_service(
    session: AsyncSession,
) -> tuple[
    TicketQueryService[tuple[TicketModel, int], TicketModel],
    ProductQueryService[ProductModel, tuple[TicketItemModel, TicketModel]],
]:
    repository = SqlAlchemyQueryRepository(session)
    return TicketQueryService(repository), ProductQueryService(repository)


def _sync_query_service(session: AsyncSession) -> SyncQueryService[SyncRunModel]:
    return SyncQueryService(SqlAlchemySyncQueryRepository(session))


async def _require_sync_auth(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if (
        settings.local_app_token
        and request.headers.get("authorization") != f"Bearer {settings.local_app_token}"
    ):
        raise APIError("AUTH_REQUIRED", "Authentication is required", 401)


async def _run_sync_job(run_id: str, mode: str, settings: Settings) -> None:
    try:
        async with sync_session_factory() as session:
            run = await session.get(SyncRunModel, run_id)
            if run is None:
                return
            run.status = "running"
            run.started_at_utc = datetime.now(UTC)
            await session.commit()
            query = (
                settings.gmail_query
                or f"from:({settings.gmail_sender}) has:attachment filename:pdf"
            )
            from app.infrastructure.repositories import SqlAlchemyIngestionRepository

            service = TicketSyncService(
                gmail=GmailApiClient(settings),
                repository=SqlAlchemyIngestionRepository(session),
                archive=PdfArchive(settings.tickets_directory),
                parser=parse_pdf_bytes,
                max_attachment_bytes=settings.gmail_max_attachment_bytes,
            )
            summary = await service.sync(mode=mode, query=query)
            run.status = "partial" if summary.error_count else "succeeded"
            run.query = summary.query
            run.matched_messages = summary.matched_messages
            run.imported_tickets = summary.imported_tickets
            run.skipped_duplicates = summary.skipped_duplicates
            run.partial_tickets = summary.partial_tickets
            run.error_count = summary.error_count
            run.last_error_code = summary.last_error_code
            run.finished_at_utc = datetime.now(UTC)
            await session.commit()
    except Exception as exc:
        async with sync_session_factory() as session:
            run = await session.get(SyncRunModel, run_id)
            if run is not None:
                run.status = "failed"
                run.error_count = max(run.error_count, 1)
                run.last_error_code = getattr(exc, "code", "SYNC_FAILED")
                run.finished_at_utc = datetime.now(UTC)
                await session.commit()
    finally:
        await coordinator.finish()


router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
async def health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise APIError("DATABASE_UNAVAILABLE", "Database unavailable", 503) from exc
    settings = get_settings()
    return HealthResponse(status="ok", database="ok", version=settings.app_version)


@router.get(
    "/tickets", response_model=TicketListResponse, responses={422: {"model": ErrorResponse}}
)
async def list_tickets(
    page: int = Query(1),
    page_size: int = Query(50, alias="pageSize"),
    snake_page_size: int | None = Query(None, alias="page_size", include_in_schema=False),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, page_size = _page(page, snake_page_size if snake_page_size is not None else page_size)
    ticket_service, _ = _query_service(session)
    result = await _query_timeout(ticket_service.list(page=page, page_size=page_size))
    return _page_response(
        result, [_ticket_summary(ticket, count) for ticket, count in result.items]
    )


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def get_ticket(
    ticket_id: str, session: AsyncSession = Depends(get_session)
) -> TicketDetailResponse:
    ticket_service, _ = _query_service(session)
    ticket = await _query_timeout(ticket_service.get(_parse_uuid(ticket_id, "ticket")))
    original = ticket.gmail_message
    items = [
        TicketItemResponse(
            id=UUID(item.id),
            lineIndex=item.line_index,
            rawDescription=item.raw_description,
            product=(
                ProductRef(
                    id=UUID(item.product.id),
                    name=item.product.canonical_name,
                    basis=_basis(item.product.comparable_basis),
                )
                if item.product
                else None
            ),
            quantity=str(item.quantity) if item.quantity is not None else None,
            quantityUnit=item.quantity_unit,
            weightGrams=item.weight_grams,
            comparablePriceCents=item.comparable_price_cents,
            comparableBasis=_basis(item.comparable_basis) if item.comparable_basis else None,
            lineAmountCents=item.line_amount_cents,
            parseStatus=item.parse_status,
        )
        for item in sorted(ticket.items, key=lambda value: value.line_index)
    ]
    return TicketDetailResponse(
        id=UUID(ticket.id),
        ticketNumber=ticket.ticket_number,
        purchasedAt=_required_datetime(ticket.purchased_at_utc, local=True),
        timezone=ticket.purchased_timezone,
        totalCents=ticket.total_cents,
        parseStatus=ticket.parse_status,
        originalPdf=OriginalPdf(
            available=original is not None, sha256=original.attachment_sha256 if original else None
        ),
        items=items,
    )


@router.get(
    "/products/search",
    response_model=ProductSearchResponse,
    responses={422: {"model": ErrorResponse}},
)
async def search_products(
    q: str = Query(""), limit: int = Query(20), session: AsyncSession = Depends(get_session)
) -> ProductSearchResponse:
    if len(q.strip()) == 1:
        raise APIError("QUERY_TOO_SHORT", "Search query must contain at least two characters", 422)
    if not 1 <= limit <= 50:
        raise APIError("INVALID_LIMIT", "Limit must be between 1 and 50", 422)
    _, product_service = _query_service(session)
    products = await _query_timeout(product_service.search(query=q, limit=limit))
    return ProductSearchResponse(
        items=[
            ProductSearchItem(
                id=UUID(p.id),
                name=p.canonical_name,
                basis=_basis(p.comparable_basis),
                match=p.canonical_name,
            )
            for p in products
        ]
    )


async def _product_detail(product_id: str, session: AsyncSession) -> tuple[Any, list[HistoryPoint]]:
    _, product_service = _query_service(session)
    product = await _query_timeout(product_service.get(_parse_uuid(product_id, "product")))
    history_rows = await _query_timeout(product_service.history(UUID(product.id)))
    return product, [_history_point(item, ticket) for item, ticket in history_rows]


@router.get(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def get_product(
    product_id: str, session: AsyncSession = Depends(get_session)
) -> ProductDetailResponse:
    product, points = await _product_detail(product_id, session)
    return ProductDetailResponse(
        id=UUID(product.id),
        name=product.canonical_name,
        basis=_basis(product.comparable_basis),
        summary=_summary([point.price_cents for point in points]),
        priceHistory=points,
    )


@router.get(
    "/products/{product_id}/history",
    response_model=ProductHistoryResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def product_history(
    product_id: str, session: AsyncSession = Depends(get_session)
) -> ProductHistoryResponse:
    product, points = await _product_detail(product_id, session)
    return ProductHistoryResponse(
        productId=UUID(product.id),
        basis=_basis(product.comparable_basis),
        summary=_summary([point.price_cents for point in points]),
        points=points,
    )


def _product_ticket_appearance(item: TicketItemModel, ticket: TicketModel) -> ProductTicketAppearance:
    assert item.comparable_price_cents is not None
    return ProductTicketAppearance(
        ticketId=UUID(item.ticket_id),
        purchasedAt=_required_datetime(ticket.purchased_at_utc, local=True),
        lineAmountCents=item.line_amount_cents,
        comparablePriceCents=item.comparable_price_cents,
        basis=_basis(item.comparable_basis),
    )


@router.get(
    "/products/{product_id}/tickets",
    response_model=ProductTicketResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def product_tickets(
    product_id: str,
    page: int = Query(1),
    page_size: int = Query(50, alias="pageSize"),
    snake_page_size: int | None = Query(None, alias="page_size", include_in_schema=False),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    parsed_id = _parse_uuid(product_id, "product")
    _, product_service = _query_service(session)
    _, page_size = _page(page, snake_page_size if snake_page_size is not None else page_size)
    result = await _query_timeout(product_service.tickets(product_id=parsed_id, page=page, page_size=page_size))
    items = [_product_ticket_appearance(item, ticket) for item, ticket in result.items]
    return _page_response(result, items)


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(session: AsyncSession = Depends(get_session)) -> SyncStatusResponse:
    run = await _query_timeout(_sync_query_service(session).latest())
    last = (
        LastRun(
            id=UUID(run.id),
            mode=run.mode,
            status=run.status,
            startedAt=_safe_datetime(run.started_at_utc),
            finishedAt=_safe_datetime(run.finished_at_utc),
            importedTickets=run.imported_tickets,
            partialTickets=run.partial_tickets,
            errorCount=run.error_count,
        )
        if run
        else None
    )
    return SyncStatusResponse(
        running=coordinator.is_running(), lastRun=last, nextScheduledAt=None, hostOnline=True
    )


async def _start_sync(payload: SyncRunRequest) -> SyncRunAccepted:
    if not await coordinator.try_start():
        raise APIError("SYNC_ALREADY_RUNNING", "A synchronization is already running", 409)
    settings = get_settings()
    run_id = str(uuid4())
    try:
        async with sync_session_factory() as session:
            session.add(
                SyncRunModel(
                    id=run_id, mode=payload.mode, status="queued", created_at_utc=datetime.now(UTC)
                )
            )
            await session.commit()
        asyncio.create_task(_run_sync_job(run_id, payload.mode, settings))
    except Exception:
        await coordinator.finish()
        raise
    return SyncRunAccepted(id=UUID(run_id), mode=payload.mode, status="queued")


@router.post(
    "/sync/run",
    response_model=SyncRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_require_sync_auth)],
    responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
@router.post(
    "/sync-runs",
    response_model=SyncRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_require_sync_auth)],
    responses={401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def start_sync(payload: SyncRunRequest = SyncRunRequest()) -> SyncRunAccepted:
    return await _start_sync(payload)


@router.get(
    "/sync-runs/{run_id}",
    response_model=SyncRunResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def get_sync_run(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> SyncRunResponse:
    run = await _query_timeout(_sync_query_service(session).get(_parse_uuid(run_id, "sync_run")))
    errors = (
        [SyncErrorCount(code=run.last_error_code, count=run.error_count)]
        if run.last_error_code
        else []
    )
    return SyncRunResponse(
        id=UUID(run.id),
        mode=run.mode,
        status=run.status,
        matchedMessages=run.matched_messages,
        importedTickets=run.imported_tickets,
        skippedDuplicates=run.skipped_duplicates,
        partialTickets=run.partial_tickets,
        errorCount=run.error_count,
        errors=errors,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if not _allowed_bind_host(get_settings().bind_host):
        raise RuntimeError("SUPERMARKET_BIND_HOST must be loopback or an explicit Tailscale IPv4 address")
    if get_settings().bind_host not in {"127.0.0.1", "localhost", "::1"} and not get_settings().local_app_token:
        raise RuntimeError("SUPERMARKET_LOCAL_APP_TOKEN is required for a Tailscale bind")
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Request-ID"],
    allow_credentials=False,
)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _error_response(request, exc)


@app.exception_handler(QueryError)
async def query_error_handler(request: Request, exc: QueryError) -> JSONResponse:
    return _error_response(
        request,
        APIError(
            exc.code,
            exc.message,
            404 if exc.code.endswith("_NOT_FOUND") else 400,
            details=exc.details,
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, _exc: RequestValidationError) -> JSONResponse:
    malformed_json = any(error.get("type") == "json_invalid" for error in _exc.errors())
    return _error_response(
        request,
        APIError(
            "MALFORMED_JSON" if malformed_json else "INVALID_REQUEST",
            "Request body is not valid JSON" if malformed_json else "Request validation failed",
            400 if malformed_json else 422,
        ),
    )


@app.exception_handler(ValidationError)
async def pydantic_error_handler(request: Request, _exc: ValidationError) -> JSONResponse:
    return _error_response(request, APIError("INVALID_REQUEST", "Request validation failed", 422))


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, _exc: SQLAlchemyError) -> JSONResponse:
    return _error_response(request, APIError("DATABASE_UNAVAILABLE", "Database unavailable", 503))


app.include_router(router, prefix="/api/v1")
app.include_router(router, prefix="/api")

frontend_directory = Path(settings.frontend_dist_directory).expanduser()
if frontend_directory.is_dir():
    app.mount("/", SPAStaticFiles(directory=frontend_directory, html=True), name="frontend")
