from decimal import Decimal

from app.domain.pricing import cents_from_amount, comparable_price_cents


def test_decimal_money_rounds_half_up_without_float() -> None:
    assert cents_from_amount(Decimal("12.905")) == 1291


def test_comparable_prices_keep_unit_and_kg_bases_separate() -> None:
    assert comparable_price_cents(line_amount_cents=500, quantity=Decimal("2")) == (250, "unit")
    assert comparable_price_cents(line_amount_cents=162, weight_grams=740) == (219, "kg")


def test_missing_measurement_is_partial() -> None:
    assert comparable_price_cents(line_amount_cents=100) is None
