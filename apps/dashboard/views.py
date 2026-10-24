"""Upcoming / detail / history dashboard views."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.core.paginator import Paginator
from django.db.models import Avg, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.leagues.models import League
from apps.matches.models import Fixture
from apps.predictions.models import Prediction

MARKET_FIELD = {
    "o15": "p_over_15",
    "o25": "p_over_25",
    "o35": "p_over_35",
}
FINISHED = (
    Fixture.Status.FT,
    Fixture.Status.AET,
    Fixture.Status.PEN,
)
# Upcoming horizon presets (hours from now, MSK clock).
HOUR_WINDOWS = ("3", "6", "9", "12", "24", "48")
DEFAULT_HOURS = "48"
PAGE_SIZE = 50


def _parse_int(raw: str | None) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _hours_window(
    hours_raw: str | None,
) -> tuple[datetime, datetime]:
    """Return [now, now+N hours) for upcoming filters."""
    now = timezone.now()
    hours = DEFAULT_HOURS
    if hours_raw in HOUR_WINDOWS:
        hours = hours_raw
    return now, now + timedelta(hours=int(hours))


def _league_choices() -> list[dict[str, Any]]:
    """Distinct competitions for filter dropdowns."""
    seen: set[int] = set()
    choices: list[dict[str, Any]] = []
    qs = League.objects.filter(is_active=True).order_by(
        "country",
        "name",
        "-season",
    )
    for league in qs:
        if league.api_id in seen:
            continue
        seen.add(league.api_id)
        choices.append(
            {
                "api_id": league.api_id,
                "name": league.name,
                "country": league.country,
            },
        )
    return choices


def _apply_league_filter(
    qs: QuerySet,
    league_api_id: int | None,
) -> QuerySet:
    if league_api_id is None:
        return qs
    return qs.filter(fixture__league__api_id=league_api_id)


def _apply_signal_filter(
    qs: QuerySet,
    market: str,
    signals_only: bool,
) -> QuerySet:
    if not signals_only:
        return qs
    key = f"features_json__signals__{market}"
    return qs.filter(**{key: True})


@require_GET
def upcoming(request: HttpRequest) -> HttpResponse:
    """List upcoming fixtures with predictions."""
    market = request.GET.get("market", "o25")
    if market not in MARKET_FIELD:
        market = "o25"
    hours_raw = request.GET.get("hours", DEFAULT_HOURS)
    if hours_raw not in HOUR_WINDOWS:
        hours_raw = DEFAULT_HOURS
    league_api_id = _parse_int(request.GET.get("league"))
    signals_only = request.GET.get("signals") == "1"

    start, end = _hours_window(hours_raw)
    qs = Prediction.objects.filter(
        fixture__status__in=(
            Fixture.Status.NS,
            Fixture.Status.TBD,
        ),
        fixture__kickoff_at__gte=start,
        fixture__kickoff_at__lt=end,
    ).select_related(
        "fixture",
        "fixture__home",
        "fixture__away",
        "fixture__league",
    )
    qs = _apply_league_filter(qs, league_api_id)
    qs = _apply_signal_filter(qs, market, signals_only)
    # Nearest kickoff first (stored UTC, displayed MSK).
    qs = qs.order_by("fixture__kickoff_at", "pk")

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/upcoming.html",
        {
            "page": page,
            "market": market,
            "hours": hours_raw,
            "league_api_id": league_api_id,
            "signals_only": signals_only,
            "leagues": _league_choices(),
        },
    )


@require_GET
def match_detail(
    request: HttpRequest,
    fixture_id: int,
) -> HttpResponse:
    """Single match prediction breakdown."""
    fixture = get_object_or_404(
        Fixture.objects.select_related(
            "home",
            "away",
            "league",
        ),
        pk=fixture_id,
    )
    prediction = (
        Prediction.objects.filter(fixture=fixture)
        .select_related("fixture")
        .first()
    )
    features = {}
    if prediction is not None:
        features = prediction.features_json or {}
    return render(
        request,
        "dashboard/match_detail.html",
        {
            "fixture": fixture,
            "prediction": prediction,
            "features": features,
            "signals": features.get("signals") or {},
        },
    )


@require_GET
def history(request: HttpRequest) -> HttpResponse:
    """Finished matches: forecast vs actual."""
    market = request.GET.get("market", "o25")
    if market not in MARKET_FIELD:
        market = "o25"
    league_api_id = _parse_int(request.GET.get("league"))
    signals_only = request.GET.get("signals") == "1"
    days_raw = request.GET.get("days", "30")
    days = _parse_int(days_raw) or 30

    since = timezone.now() - timedelta(days=days)
    qs = Prediction.objects.filter(
        fixture__status__in=FINISHED,
        fixture__kickoff_at__gte=since,
        fixture__goals_home__isnull=False,
        fixture__goals_away__isnull=False,
    ).select_related(
        "fixture",
        "fixture__home",
        "fixture__away",
        "fixture__league",
    )
    qs = _apply_league_filter(qs, league_api_id)
    qs = _apply_signal_filter(qs, market, signals_only)
    qs = qs.order_by("-fixture__kickoff_at")

    kpi = _history_kpi(qs)

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/history.html",
        {
            "page": page,
            "market": market,
            "days": str(days),
            "league_api_id": league_api_id,
            "signals_only": signals_only,
            "leagues": _league_choices(),
            "kpi": kpi,
        },
    )


def _history_kpi(qs: QuerySet[Prediction]) -> dict:
    """Hit-rates for O1.5 / O2.5 / O3.5 on a queryset."""
    rows = list(
        qs.values_list(
            "fixture__goals_home",
            "fixture__goals_away",
            "features_json",
        ),
    )
    totals = {"o15": [0, 0], "o25": [0, 0], "o35": [0, 0]}
    for gh, ga, _feats in rows:
        total = int(gh) + int(ga)
        checks = {
            "o15": total >= 2,
            "o25": total >= 3,
            "o35": total >= 4,
        }
        for key, hit in checks.items():
            totals[key][1] += 1
            if hit:
                totals[key][0] += 1
    result = {}
    for key, (hits, n) in totals.items():
        result[key] = {
            "hits": hits,
            "n": n,
            "rate": (hits / n) if n else None,
        }
    result["count"] = len(rows)
    agg = qs.aggregate(
        avg15=Avg("p_over_15"),
        avg25=Avg("p_over_25"),
        avg35=Avg("p_over_35"),
    )
    result["avg15"] = agg["avg15"]
    result["avg25"] = agg["avg25"]
    result["avg35"] = agg["avg35"]
    return result
