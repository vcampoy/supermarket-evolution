from decimal import ROUND_HALF_UP, Decimal


def cents_from_amount(amount: Decimal) -> int:
    """Convert a decimal euro amount to cents exactly once at the domain boundary."""
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def comparable_price_cents(
    *,
    line_amount_cents: int,
    quantity: Decimal | None = None,
    weight_grams: int | None = None,
    explicit_unit_price_cents: int | None = None,
) -> tuple[int, str] | None:
    """Return the comparable price and its basis, without mixing units and kilograms."""
    if explicit_unit_price_cents is not None:
        if quantity is not None and quantity > 0:
            return explicit_unit_price_cents, "unit"
        if weight_grams is not None and weight_grams > 0:
            return explicit_unit_price_cents, "kg"

    if quantity is not None and quantity > 0:
        value = (Decimal(line_amount_cents) / quantity).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(value), "unit"
    if weight_grams is not None and weight_grams > 0:
        value = (Decimal(line_amount_cents) * Decimal("1000") / Decimal(weight_grams)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return int(value), "kg"
    return None
