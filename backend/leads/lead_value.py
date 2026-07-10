from __future__ import annotations

from decimal import Decimal


def lead_value_from_translation_score(score: int | float | None) -> Decimal | None:
    """
    Map translation need score (0–100) to an estimated opportunity value (USD).

    Used when converting a prospect to a lead unless lead_value is set explicitly.
    """
    if score is None:
        return None
    try:
        normalized = int(score)
    except (TypeError, ValueError):
        return None
    normalized = max(0, min(100, normalized))
    if normalized >= 80:
        return Decimal("7500.00")
    if normalized >= 60:
        return Decimal("3500.00")
    if normalized >= 40:
        return Decimal("1500.00")
    if normalized >= 20:
        return Decimal("750.00")
    return Decimal("250.00")
