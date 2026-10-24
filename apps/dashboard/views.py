"""Picks / detail / history dashboard views."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Q, QuerySet
from django.db.models.functions import TruncDate
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
OVER_LINES = {
    "o25": 3,
}
PRIMARY_KEYS = ("o25", "btts")


def _parse_int(raw: str | None) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _msk_date(dt: datetime) -> date:
    return timezone.localtime(dt).date()


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """Return [day 00:00, next day 00:00) in local TZ as aware datetimes."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(
        datetime.combine(day, datetime.min.time()),
        tz,
    )
    return start, start + timedelta(days=1)


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
    """Matches with at least one product tip (O2.5 and/or BTTS)."""
    return qs.filter(
        Q(features_json__signals__o25=True)
        | Q(features_json__signals__btts=True)
        | Q(features_json__signals__primary__in=PRIMARY_KEYS),
    )


def _finished_pick_qs(
    *,
    league_api_id: int | None = None,
) -> QuerySet:
    qs = (
        _primary_picks(Prediction.objects.all())
        .filter(
            fixture__status__in=FINISHED,
            fixture__kickoff_at__gte=stats_since(),
            fixture__goals_home__isnull=False,
            fixture__goals_away__isnull=False,
        )
        .select_related(
            "fixture",
            "fixture__home",
            "fixture__away",
            "fixture__league",
        )
    )
    return _apply_league_filter(qs, league_api_id)


def _history_dates(
    *,
    league_api_id: int | None = None,
) -> list[date]:
    """MSK calendar days that have finished tips (newest first)."""
    qs = _finished_pick_qs(league_api_id=league_api_id)
    days = (
        qs.annotate(
            day=TruncDate(
                "fixture__kickoff_at",
                tzinfo=timezone.get_current_timezone(),
            ),
        )
        .values_list("day", flat=True)
        .distinct()
        .order_by("-day")
    )
    return [d for d in days if d is not None]


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
    show_kpi = which == "today"
    kpi = _pick_accuracy_kpi_list(rows) if show_kpi else None
    title = "Tomorrow" if which == "tomorrow" else "Today"
    return render(
        request,
        "dashboard/picks.html",
        {
            "picks": rows,
            "kpi": kpi,
            "show_kpi": show_kpi,
            "show_score": which == "today",
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
    """Finished picks for one MSK day that has tips."""
    league_api_id = _parse_int(request.GET.get("league"))
    available_dates = _history_dates(league_api_id=league_api_id)
    selected = _parse_date(request.GET.get("date"))
    if selected not in available_dates:
        selected = available_dates[0] if available_dates else None

    rows: list[Prediction] = []
    if selected is not None:
        since, until = _day_bounds(selected)
        qs = _finished_pick_qs(
            league_api_id=league_api_id,
        ).filter(
            fixture__kickoff_at__gte=since,
            fixture__kickoff_at__lt=until,
        )
        rows = list(qs.order_by("-fixture__kickoff_at"))

    kpi = _pick_accuracy_kpi_list(rows)
    day_groups = _group_by_msk_day(rows)

    return render(
        request,
        "dashboard/history.html",
        {
            "day_groups": day_groups,
            "available_dates": available_dates,
            "selected_date": selected,
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


def _market_stat() -> dict[str, Any]:
    return {"wins": 0, "picked": 0, "rate": None}


def _pick_accuracy_kpi_list(
    preds: list[Prediction],
) -> dict:
    """Separate won/picked for finished O2.5 and BTTS tips."""
    o25 = _market_stat()
    btts = _market_stat()
    for pred in preds:
        fx = pred.fixture
        if not fx.is_finished:
            continue
        if fx.goals_home is None or fx.goals_away is None:
            continue
        signals = (pred.features_json or {}).get("signals") or {}
        gh = int(fx.goals_home)
        ga = int(fx.goals_away)
        if signals.get("o25"):
            o25["picked"] += 1
            if gh + ga >= OVER_LINES["o25"]:
                o25["wins"] += 1
        if signals.get("btts"):
            btts["picked"] += 1
            if gh >= 1 and ga >= 1:
                btts["wins"] += 1
    for block in (o25, btts):
        if block["picked"]:
            block["rate"] = block["wins"] / block["picked"]
    return {
        "o25": o25,
        "btts": btts,
        "count": o25["picked"] + btts["picked"],
    }
