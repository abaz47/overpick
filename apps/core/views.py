"""Core views for OverPick."""

from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import render
from django.views.decorators.http import (
    require_GET,
)


@require_GET
def health(request: HttpRequest) -> HttpResponse:
    """Liveness probe for Docker / nginx."""
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """Placeholder home page (Upcoming later)."""
    return render(request, "core/home.html")
