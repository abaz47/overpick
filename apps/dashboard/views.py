"""Upcoming / detail / history dashboard views."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, QuerySet
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
PAGE_SIZE = 50


def _parse_int(raw: str | None) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _days_window(
    days_raw: str | None,
) -> tuple[datetime | None, datetime | None]:
    """Return [start, end) for upcoming day filters."""
    now = timezone.now()
    today = timezone.localtime(now).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    if days_raw == "today":
        return today, today + timedelta(days=1)
    if days_raw == "tomorrow":
        start = today + timedelta(days=1)
        return start, start + timedelta(days=1)
    if days_raw in {"3", "7", "14"}:
        return now, now + timedelta(days=int(days_raw))
    # "all" or unknown → from now onward
    return now, None


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
    days_raw = request.GET.get("days", "7")
    league_api_id = _parse_int(request.GET.get("league"))
    signals_only = request.GET.get("signals") == "1"
    sort_field = MARKET_FIELD[market]

    start, end = _days_window(days_raw)
    qs = Prediction.objects.filter(
        fixture__status__in=(
            Fixture.Status.NS,
            Fixture.Status.TBD,
        ),
        fixture__kickoff_at__gt=timezone.now(),
    ).select_related(
        "fixture",
        "fixture__home",
        "fixture__away",
        "fixture__league",
    )
    if start is not None:
        qs = qs.filter(fixture__kickoff_at__gte=start)
    if end is not None:
        qs = qs.filter(fixture__kickoff_at__lt=end)
    qs = _apply_league_filter(qs, league_api_id)
    qs = _apply_signal_filter(qs, market, signals_only)
    qs = qs.order_by(f"-{sort_field}", "fixture__kickoff_at")

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "dashboard/upcoming.html",
        {
            "page": page,
            "market": market,
            "days": days_raw,
            "league_api_id": league_api_id,
            "signals_only": signals_only,
            "leagues": _league_choices(),
            "sort_field": sort_field,
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

    # KPI on the filtered queryset (before pagination).
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
            # Count all rows in filtered set.
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
    # Average predicted probs for calibration glance.
    agg = qs.aggregate(
        avg15=Avg("p_over_15"),
        avg25=Avg("p_over_25"),
        avg35=Avg("p_over_35"),
    )
    result["avg15"] = agg["avg15"]
    result["avg25"] = agg["avg25"]
    result["avg35"] = agg["avg35"]
    return result


@require_GET
def leagues(request: HttpRequest) -> HttpResponse:
    """Active leagues with fixture / prediction counts."""
    qs = (
        League.objects.filter(is_active=True)
        .annotate(
            fixtures_n=Count("fixtures", distinct=True),
            preds_n=Count(
                "fixtures__prediction",
                distinct=True,
            ),
            upcoming_n=Count(
                "fixtures",
                filter=Q(
                    fixtures__status=Fixture.Status.NS,
                    fixtures__kickoff_at__gt=timezone.now(),
                ),
                distinct=True,
            ),
        )
        .order_by("country", "name", "-season")
    )
    return render(
        request,
        "dashboard/leagues.html",
        {"leagues": qs},
    )
