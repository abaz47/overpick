"""Picks / detail / history dashboard views."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.core.stats_window import (
    site_launch_at,
    stats_since,
    today_picks_start,
)
from apps.leagues.models import League
from apps.matches.models import Fixture
from apps.predictions.models import Prediction
from apps.predictions.services.batch import (
    batch_label,
    batch_window_for,
)

FINISHED = (
    Fixture.Status.FT,
    Fixture.Status.AET,
    Fixture.Status.PEN,
)
# 1 = Yesterday; no "today" (live day lives on Picks).
HISTORY_DAYS = ("1", "2", "3", "7", "30")
DEFAULT_HISTORY_DAYS = "7"
# Product focuses on Over 2.5 picks only.
OVER_LINES = {
    "o25": 3,
}
PRIMARY_KEYS = ("o25",)


def _parse_int(raw: str | None) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _history_bounds(
    days_raw: str,
) -> tuple[datetime, datetime | None]:
    """Return [since, until) for History, floored by STATS_SINCE."""
    launch = stats_since()
    now = timezone.now()
    local = timezone.localtime(now)
    today_start = local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    if days_raw == "1":
        # Yesterday MSK only.
        since = today_start - timedelta(days=1)
        until = today_start
        return max(since, launch), until
    days = int(days_raw)
    since = now - timedelta(days=days)
    return max(since, launch), None


def _msk_date(dt: datetime) -> date:
    return timezone.localtime(dt).date()


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


def _primary_picks(qs: QuerySet) -> QuerySet:
    return qs.filter(
        features_json__signals__primary__in=PRIMARY_KEYS,
    )


def _render_picks(
    request: HttpRequest,
    *,
    which: str,
) -> HttpResponse:
    """Shared Today / Tomorrow picks page."""
    league_api_id = _parse_int(request.GET.get("league"))
    start, end = batch_window_for(which)
    list_start = start
    if which == "today":
        # Soft launch: show only from SITE_LAUNCH_AT
        # while that instant falls inside today's batch.
        list_start = today_picks_start(start, end)
    qs = (
        _primary_picks(Prediction.objects.all())
        .filter(
            fixture__kickoff_at__gte=list_start,
            fixture__kickoff_at__lt=end,
        )
        .select_related(
            "fixture",
            "fixture__home",
            "fixture__away",
            "fixture__league",
        )
    )
    qs = _apply_league_filter(qs, league_api_id)
    qs = qs.order_by("fixture__kickoff_at", "pk")
    rows = list(qs)
    kpi = _pick_accuracy_kpi_list(rows)
    title = "Tomorrow's Picks" if which == "tomorrow" else "Today's Picks"
    return render(
        request,
        "dashboard/picks.html",
        {
            "picks": rows,
            "kpi": kpi,
            "league_api_id": league_api_id,
            "leagues": _league_choices(),
            "batch_start": list_start,
            "batch_end": end,
            "batch_label": batch_label(list_start),
            "which": which,
            "page_title": title,
            "site_launch_at": site_launch_at(),
            "stats_since": stats_since(),
        },
    )


@require_GET
def picks(request: HttpRequest) -> HttpResponse:
    """Today's locked batch (07:30 → +24h MSK)."""
    return _render_picks(request, which="today")


@require_GET
def picks_tomorrow(request: HttpRequest) -> HttpResponse:
    """Tomorrow's batch preview / next lock window."""
    return _render_picks(request, which="tomorrow")


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
    signals = features.get("signals") or {}
    return render(
        request,
        "dashboard/match_detail.html",
        {
            "fixture": fixture,
            "prediction": prediction,
            "features": features,
            "signals": signals,
        },
    )


@require_GET
def history(request: HttpRequest) -> HttpResponse:
    """Finished picks grouped by MSK calendar day."""
    league_api_id = _parse_int(request.GET.get("league"))
    days_raw = request.GET.get("days", DEFAULT_HISTORY_DAYS)
    if days_raw not in HISTORY_DAYS:
        days_raw = DEFAULT_HISTORY_DAYS

    since, until = _history_bounds(days_raw)
    qs = (
        _primary_picks(Prediction.objects.all())
        .filter(
            fixture__status__in=FINISHED,
            fixture__kickoff_at__gte=since,
            fixture__goals_home__isnull=False,
            fixture__goals_away__isnull=False,
        )
        .select_related(
            "fixture",
            "fixture__home",
            "fixture__away",
            "fixture__league",
        )
        .order_by("-fixture__kickoff_at")
    )
    if until is not None:
        qs = qs.filter(fixture__kickoff_at__lt=until)
    qs = _apply_league_filter(qs, league_api_id)
    rows = list(qs)
    kpi = _pick_accuracy_kpi_list(rows)
    day_groups = _group_by_msk_day(rows)

    return render(
        request,
        "dashboard/history.html",
        {
            "day_groups": day_groups,
            "days": days_raw,
            "league_api_id": league_api_id,
            "leagues": _league_choices(),
            "kpi": kpi,
            "stats_since": stats_since(),
        },
    )


def _group_by_msk_day(
    preds: list[Prediction],
) -> list[dict[str, Any]]:
    """Group finished picks by local MSK date (newest first)."""
    buckets: dict[date, list[Prediction]] = defaultdict(list)
    for pred in preds:
        buckets[_msk_date(pred.fixture.kickoff_at)].append(
            pred,
        )
    groups: list[dict[str, Any]] = []
    for day in sorted(buckets, reverse=True):
        items = buckets[day]
        groups.append(
            {
                "date": day,
                "picks": items,
                "kpi": _pick_accuracy_kpi_list(items),
            },
        )
    return groups


def _pick_accuracy_kpi(
    qs: QuerySet[Prediction],
) -> dict:
    """won/picked per market from a queryset."""
    return _pick_accuracy_kpi_list(list(qs))


def _pick_accuracy_kpi_list(
    preds: list[Prediction],
) -> dict:
    """won/picked for finished Over 2.5 picks only."""
    wins = 0
    picked = 0
    for pred in preds:
        fx = pred.fixture
        if not fx.is_finished:
            continue
        if fx.goals_home is None or fx.goals_away is None:
            continue
        signals = (pred.features_json or {}).get("signals") or {}
        if signals.get("primary") != "o25" and not signals.get(
            "o25",
        ):
            continue
        picked += 1
        total = int(fx.goals_home) + int(fx.goals_away)
        if total >= OVER_LINES["o25"]:
            wins += 1
    return {
        "o25": {
            "wins": wins,
            "picked": picked,
            "rate": (wins / picked) if picked else None,
        },
        "count": picked,
    }
