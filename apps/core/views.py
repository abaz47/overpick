"""Core views for OverPick."""

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request: HttpRequest) -> HttpResponse:
    """Liveness probe for Docker / nginx."""
    return HttpResponse("ok", content_type="text/plain")
