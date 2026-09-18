
import pytest

from app.domain.entities import ParseStatus, QuantityUnit
from app.infrastructure.parser import (
    TicketParseError,
    parse_pdf_bytes,
    parse_pdf_file,
    parse_ticket_subject,
    parse_ticket_text,
)


class FakeExtractor:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract(self, _pdf_bytes: bytes) -> str:
        return self.text


def ticket_text(total: str = "5,12") -> str:
    return f"""Fecha: 17/09/2026 18:42
Tienda: Madrid Centro
Ticket: 123456
1 Leche entera 1,50
2 Yogur natural 2,00
Tomate pera 1,62
0,740 kg x 2,19 €/kg 1,62
TOTAL {total} €
"""


def test_subject_valid_and_invalid() -> None:
    assert parse_ticket_subject("20260917 Mercadona 12,90 €").total_cents == 1290
    with pytest.raises(TicketParseError) as error:
        parse_ticket_subject("ticket de mercadona")
    assert error.value.code == "SUBJECT_INVALID"


def test_normal_pdf_extracts_unit_and_weight_lines() -> None:
    parsed = parse_pdf_bytes(b"%PDF fixture", extractor=FakeExtractor(ticket_text()))
    assert parsed.status is ParseStatus.READY
    assert len(parsed.lines) == 3
    assert parsed.lines[1].quantity == 2
    assert parsed.lines[2].quantity_unit is QuantityUnit.KG
    assert parsed.lines[2].weight_grams == 740
    assert parsed.lines[2].comparable_price_cents == 219


def test_real_pdf_fixture_uses_deterministic_text_extraction() -> None:
    parsed = parse_pdf_file("tests/fixtures/normal_ticket.pdf")
    assert parsed.status is ParseStatus.READY
    assert parsed.ticket_number == "123456"
    assert parsed.total_cents == 512


def test_same_description_is_kept_as_two_observations() -> None:
    parsed = parse_ticket_text("""Fecha: 17/09/2026
Leche entera 1,50
Leche entera 1,70
TOTAL 3,20
""")
    assert [line.line_amount_cents for line in parsed.lines] == [150, 170]


def test_discount_and_rounding_tolerance_are_supported() -> None:
    parsed = parse_ticket_text("""Fecha: 17/09/2026
Pan 1,00
Descuento -0,10
TOTAL 0,90
""")
    assert parsed.status is ParseStatus.READY
    rounded = parse_ticket_text("""Fecha: 17/09/2026
Pan 1,00
TOTAL 1,02
""", tolerance_cents=2)
    assert rounded.status is ParseStatus.READY


def test_mismatch_is_needs_review_without_inventing_values() -> None:
    parsed = parse_ticket_text(ticket_text("4,99"))
    assert parsed.status is ParseStatus.NEEDS_REVIEW
    assert parsed.error_code == "TOTAL_MISMATCH"


def test_invalid_pdf_is_typed_error() -> None:
    with pytest.raises(TicketParseError) as error:
        parse_pdf_bytes(b"not a pdf", extractor=FakeExtractor("unused"))
    assert error.value.code == "PDF_INVALID"
