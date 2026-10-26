"""Create locked Prediction rows for the daily batch."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.matches.models import Fixture
from apps.predictions.models import Prediction
from apps.predictions.services.batch import (
    batch_containing,
    batch_window_for,
    current_batch_window,
)
from apps.predictions.services.form import (
    build_form_features,
    expected_goals,
)
from apps.predictions.services.gbm_features import (
    build_gbm_feature_dict,
)
from apps.predictions.services.poisson import p_btts, p_over
from apps.predictions.services.signals import (
    build_signal_flags,
)

logger = logging.getLogger(__name__)

MODEL_VERSION = "hybrid_v1"

UPCOMING_STATUSES = (
    Fixture.Status.NS,
    Fixture.Status.TBD,
)


@dataclass
class BuildStats:
    """Counters for build_predictions."""

    considered: int = 0
    created: int = 0
    skipped_locked: int = 0
    skipped_form: int = 0
    errors: list[str] = field(default_factory=list)
    batch_start: datetime | None = None
    batch_end: datetime | None = None


def upcoming_fixtures(
    *,
    days: int | None = None,
    batch_window: tuple[datetime, datetime] | None = None,
) -> QuerySet[Fixture]:
    """NS/TBD fixtures in the daily batch (or legacy horizon)."""
    if batch_window is not None:
        start, end = batch_window
        return (
            Fixture.objects.filter(
                status__in=UPCOMING_STATUSES,
                kickoff_at__gte=start,
                kickoff_at__lt=end,
            )
            .select_related("home", "away", "league")
            .order_by("kickoff_at")
        )

    now = timezone.now()
    qs = (
        Fixture.objects.filter(
            status__in=UPCOMING_STATUSES,
            kickoff_at__gt=now,
        )
        .select_related("home", "away", "league")
        .order_by("kickoff_at")
    )
    if days is not None:
        qs = qs.filter(
            kickoff_at__lte=now + timedelta(days=days),
        )
    return qs


def predict_fixture(fixture: Fixture) -> Prediction:
    """Compute and persist a locked prediction."""
    features = build_form_features(fixture)
    if not features.enough_data:
        raise ValueError(
            "insufficient venue form "
            f"(home={features.home_last.sample_size}, "
            f"away={features.away_last.sample_size}, "
            f"min={features.min_n})",
        )
    lam_h, lam_a = expected_goals(features)
    p15 = p_over(lam_h, lam_a, 1.5)
    p25 = p_over(lam_h, lam_a, 2.5)
    p35 = p_over(lam_h, lam_a, 3.5)
    pb = p_btts(lam_h, lam_a)
    gbm_feats = build_gbm_feature_dict(
        fixture,
        features,
        p15=p15,
        p25=p25,
        p35=p35,
        p_btts=pb,
        lambda_home=lam_h,
        lambda_away=lam_a,
    )
    feats = features.to_json()
    feats["gbm_features"] = gbm_feats
    feats["signals"] = build_signal_flags(
        p15,
        p25,
        p35,
        p_btts=pb,
        league_api_id=fixture.league.api_id,
        gbm_features=gbm_feats,
    )
    b_start, b_end = batch_containing(fixture.kickoff_at)
    feats["batch_start"] = b_start.isoformat()
    feats["batch_end"] = b_end.isoformat()
    return Prediction.objects.create(
        fixture=fixture,
        model_version=MODEL_VERSION,
        lambda_home=lam_h,
        lambda_away=lam_a,
        lambda_total=lam_h + lam_a,
        p_over_15=p15,
        p_over_25=p25,
        p_over_35=p35,
        p_btts=pb,
        features_json=feats,
        is_locked=True,
    )


def build_predictions(
    *,
    days: int | None = None,
    force: bool = False,
    use_batch: bool = True,
    window: str = "both",
) -> BuildStats:
    """Create predictions for calendar-day batch window(s).

    ``window``: ``today`` / ``tomorrow`` / ``both``.
    Evening cron uses ``tomorrow`` + ``force`` so Today's
    locked tips are never rewritten.
    """
    stats = BuildStats()
    batch_window = None
    if use_batch and days is None:
        if window == "today":
            batch_window = batch_window_for("today")
        elif window == "tomorrow":
            batch_window = batch_window_for("tomorrow")
        else:
            start, end = current_batch_window()
            batch_window = (start, end + timedelta(days=1))
        stats.batch_start, stats.batch_end = batch_window
    elif days is None:
        days = int(
            getattr(settings, "PREDICTION_HORIZON_DAYS", 3),
        )

    for fixture in upcoming_fixtures(
        days=days,
        batch_window=batch_window,
    ):
        stats.considered += 1
        existing = Prediction.objects.filter(
            fixture=fixture,
        ).first()
        if existing is not None:
            if existing.is_locked and not force:
                stats.skipped_locked += 1
                continue
            if force:
                existing.delete()
            else:
                stats.skipped_locked += 1
                continue
        try:
            predict_fixture(fixture)
        except ValueError as exc:
            logger.info(
                "Skip fixture %s: %s",
                fixture.pk,
                exc,
            )
            stats.skipped_form += 1
            continue
        except Exception as exc:
            msg = f"{fixture.pk}: {exc}"
            logger.exception("Predict failed %s", fixture)
            stats.errors.append(msg)
            continue
        stats.created += 1
    return stats
