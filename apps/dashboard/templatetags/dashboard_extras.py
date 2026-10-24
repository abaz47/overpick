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
def hit_badge(value) -> str:
    """Bootstrap class for hit/miss/None."""
    if value is True:
        return "success"
    if value is False:
        return "danger"
    return "secondary"


@register.filter
def hit_label(value) -> str:
    """Short hit/miss label."""
    if value is True:
        return "HIT"
    if value is False:
        return "MISS"
    return "—"
