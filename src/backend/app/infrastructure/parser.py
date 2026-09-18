"""Deterministic, conservative parsing of Mercadona ticket PDFs.

The parser intentionally returns a reviewable result instead of guessing when
the PDF does not contain enough evidence.  It never writes logs containing the
extracted text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from app.application.contracts import ParsedLine, ParsedTicket, TicketParseError
from app.domain.entities import ParseStatus, ProductBasis, QuantityUnit
from app.domain.pricing import cents_from_amount, comparable_price_cents

PARSER_VERSION = "pdf-text-1"
LOCAL_ZONE = ZoneInfo("Europe/Madrid")
AMOUNT = r"-?\d{1,6}(?:[.,]\d{2})"
DATE_RE = re.compile(r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{2,4})(?:\s+(?P<hour>\d{1,2})[:.](?P<minute>\d{2}))?")
ISO_DATE_RE = re.compile(r"(?P<year>20\d{2})-(?P<month>\d{2})-(?P<day>\d{2})(?:[ T](?P<hour>\d{2})[:.](?P<minute>\d{2}))?")
MONEY_RE = re.compile(rf"(?P<amount>{AMOUNT})\s*(?:€|EUR)?\s*$", re.IGNORECASE)
WEIGHT_RE = re.compile(rf"(?P<weight>\d+(?:[.,]\d+)?)\s*kg\b(?:\s*(?:x|@|a)\s*(?P<unit>{AMOUNT})\s*(?:€/kg|EUR/kg|kg)?\s*)?(?:\s+(?P<amount>{AMOUNT})\s*(?:€|EUR)?)?$", re.IGNORECASE)
QUANTITY_RE = re.compile(r"^(?P<quantity>\d+(?:[.,]\d+)?)\s*(?:x|×|\*)?\s+(?P<description>.+)$", re.IGNORECASE)


class TextExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> str: ...


class PdfTextExtractor:
    """Extract text with pypdf; no OCR or layout-dependent heuristics."""

    def extract(self, pdf_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(pdf_bytes), strict=False)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # pypdf exposes several parser-specific exceptions
            raise TicketParseError("PDF_UNREADABLE", {"reason": type(exc).__name__}) from exc


@dataclass(frozen=True, slots=True)
class ParsedSubject:
    purchase_date: date
    total_cents: int


def normalize_description(description: str) -> str:
    return " ".join(description.casefold().strip().split())


def parse_ticket_subject(subject: str) -> ParsedSubject:
    match = re.fullmatch(r"\s*(?P<date>20\d{6})\s+mercadona\s+(?P<amount>\d+(?:[.,]\d{2}))\s*€?\s*", subject, re.IGNORECASE)
    if not match:
        raise TicketParseError("SUBJECT_INVALID")
    raw_date = match.group("date")
    try:
        purchase_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:]))
    except ValueError as exc:
        raise TicketParseError("SUBJECT_INVALID") from exc
    return ParsedSubject(purchase_date, cents_from_amount(parse_euro_amount(match.group("amount"))))


def parse_euro_amount(value: str) -> Decimal:
    normalized = value.strip().replace("€", "").replace("EUR", "").replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise TicketParseError("INVALID_AMOUNT") from exc


def _parse_date(text: str) -> tuple[datetime, date, time | None]:
    match = ISO_DATE_RE.search(text) or DATE_RE.search(text)
    if not match:
        raise TicketParseError("DATE_MISSING")
    parts = match.groupdict()
    year = int(parts["year"])
    if year < 100:
        year += 2000
    local_date = date(year, int(parts["month"]), int(parts["day"]))
    local_time = time(int(parts["hour"] or 0), int(parts["minute"] or 0)) if parts.get("hour") else None
    local_dt = datetime.combine(local_date, local_time or time.min, tzinfo=LOCAL_ZONE)
    return local_dt.astimezone(UTC), local_date, local_time


def _metadata_value(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:#]?\s*([^\n]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _looks_like_non_item(line: str) -> bool:
    return bool(re.match(r"^(?:total|subtotal|iva|base imponible|cambio|efectivo|tarjeta|pago|fecha|hora|ticket|factura|mercadona)\b", line, re.IGNORECASE))


def _line_from_text(line: str, index: int) -> ParsedLine | None:
    money_match = MONEY_RE.search(line)
    if not money_match:
        return None
    description = line[: money_match.start()].strip(" .:-")
    if not description or _looks_like_non_item(description):
        return None
    quantity = Decimal("1")
    quantity_unit = QuantityUnit.UNIT
    quantity_match = QUANTITY_RE.match(description)
    if quantity_match:
        quantity = parse_euro_amount(quantity_match.group("quantity"))
        description = quantity_match.group("description").strip()
    amount_cents = cents_from_amount(parse_euro_amount(money_match.group("amount")))
    comparable = comparable_price_cents(line_amount_cents=amount_cents, quantity=quantity)
    return ParsedLine(
        line_index=index,
        raw_description=description,
        normalized_description=normalize_description(description),
        line_amount_cents=amount_cents,
        quantity_unit=quantity_unit,
        quantity=quantity,
        comparable_price_cents=comparable[0] if comparable else None,
        comparable_basis=ProductBasis.UNIT if comparable else None,
    )


def _attach_weight(previous: ParsedLine, line: str) -> ParsedLine | None:
    match = WEIGHT_RE.search(line)
    if not match:
        return None
    weight_kg = parse_euro_amount(match.group("weight"))
    weight_grams = int((weight_kg * Decimal("1000")).quantize(Decimal("1")))
    amount = previous.line_amount_cents
    if match.group("amount"):
        amount = cents_from_amount(parse_euro_amount(match.group("amount")))
    explicit = cents_from_amount(parse_euro_amount(match.group("unit"))) if match.group("unit") else None
    comparable = comparable_price_cents(line_amount_cents=amount, weight_grams=weight_grams, explicit_unit_price_cents=explicit)
    return ParsedLine(
        line_index=previous.line_index,
        raw_description=previous.raw_description,
        normalized_description=previous.normalized_description,
        line_amount_cents=amount,
        quantity_unit=QuantityUnit.KG,
        weight_grams=weight_grams,
        explicit_unit_price_cents=explicit,
        comparable_price_cents=comparable[0] if comparable else None,
        comparable_basis=ProductBasis.KG if comparable else None,
    )


def parse_ticket_text(text: str, *, tolerance_cents: int = 2) -> ParsedTicket:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        raise TicketParseError("PDF_EMPTY")
    compact = "\n".join(lines)
    purchased_at, local_date, local_time = _parse_date(compact)
    ticket_number = _metadata_value(compact, ("ticket", "nº ticket", "numero de ticket", "factura", "nº"))
    store_name = _metadata_value(compact, ("tienda", "establecimiento"))
    total_match = re.search(rf"(?:total(?:\s+a\s+pagar)?|importe total)\s*[:]?\s*(?P<amount>{AMOUNT})", compact, re.IGNORECASE)
    if not total_match:
        raise TicketParseError("TOTAL_MISSING")
    total_cents = cents_from_amount(parse_euro_amount(total_match.group("amount")))

    parsed_lines: list[ParsedLine] = []
    adjustments_cents = 0
    for raw_line in lines:
        lower = raw_line.casefold()
        money_match = MONEY_RE.search(raw_line)
        if money_match and any(word in lower for word in ("descuento", "dto", "bonific", "redondeo")):
            adjustments_cents += cents_from_amount(parse_euro_amount(money_match.group("amount")))
            continue
        if parsed_lines:
            weighted = _attach_weight(parsed_lines[-1], raw_line)
            if weighted:
                parsed_lines[-1] = weighted
                continue
        item = _line_from_text(raw_line, len(parsed_lines) + 1)
        if item:
            parsed_lines.append(item)
    if not parsed_lines:
        raise TicketParseError("NO_LINES")

    net_lines = sum(item.line_amount_cents for item in parsed_lines) + adjustments_cents
    status = ParseStatus.READY if abs(net_lines - total_cents) <= tolerance_cents else ParseStatus.NEEDS_REVIEW
    error_code = None if status is ParseStatus.READY else "TOTAL_MISMATCH"
    error_context = None if status is ParseStatus.READY else {"difference_cents": str(net_lines - total_cents), "tolerance_cents": str(tolerance_cents)}
    return ParsedTicket(
        purchased_at_utc=purchased_at,
        purchased_local_date=local_date,
        purchased_local_time=local_time,
        purchased_timezone="Europe/Madrid",
        ticket_number=ticket_number,
        store_name=store_name,
        total_cents=total_cents,
        lines=tuple(parsed_lines),
        raw_text_excerpt=" ".join(lines)[:1000],
        status=status,
        error_code=error_code,
        error_context=error_context,
        adjustments_cents=adjustments_cents,
    )


def parse_pdf_bytes(pdf_bytes: bytes, *, extractor: TextExtractor | None = None, tolerance_cents: int = 2) -> ParsedTicket:
    if not pdf_bytes.startswith(b"%PDF"):
        raise TicketParseError("PDF_INVALID")
    text = (extractor or PdfTextExtractor()).extract(pdf_bytes)
    return parse_ticket_text(text, tolerance_cents=tolerance_cents)


def parse_pdf_file(path: str | Path, *, extractor: TextExtractor | None = None, tolerance_cents: int = 2) -> ParsedTicket:
    return parse_pdf_bytes(Path(path).read_bytes(), extractor=extractor, tolerance_cents=tolerance_cents)
