"""Template filters for dashboard."""

from django import template

register = template.Library()


@register.filter
def pct(value, digits: int = 0) -> str:
    """Format 0..1 probability as percent."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return "—"
    return f"{number * 100:.{int(digits)}f}%"


@register.filter
def min_odds(value, digits: int = 2) -> str:
    """Fair decimal odds floor: 1 / P (min coeff to take the tip)."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return "—"
    if number <= 0.0:
        return "—"
    return f"{(1.0 / number):.{int(digits)}f}"


@register.filter
def hit_badge(value) -> str:
    """Bootstrap class for hit/miss/None."""
    if value is True:
        return "success"
    if value is False:
        return "danger"
    return "secondary"


@register.filter
def hit_label(value) -> str:
    """Short won/lost label for finished picks."""
    if value is True:
        return "Won"
    if value is False:
        return "Lost"
    return "—"
