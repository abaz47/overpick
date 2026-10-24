"""Create locked Prediction rows for upcoming fixtures."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.matches.models import Fixture
from apps.predictions.models import Prediction
from apps.predictions.services.form import (
    build_form_features,
    expected_goals,
)
from apps.predictions.services.poisson import p_over

logger = logging.getLogger(__name__)

MODEL_VERSION = "poisson_v1"

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


def upcoming_fixtures(
    *,
    days: int | None = None,
) -> QuerySet[Fixture]:
    """NS/TBD fixtures with kickoff in the future."""
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
    feats = features.to_json()
    feats["signals"] = {
        "o15": p15 >= float(settings.SIGNAL_THRESHOLD_O15),
        "o25": p25 >= float(settings.SIGNAL_THRESHOLD_O25),
        "o35": p35 >= float(settings.SIGNAL_THRESHOLD_O35),
    }
    return Prediction.objects.create(
        fixture=fixture,
        model_version=MODEL_VERSION,
        lambda_home=lam_h,
        lambda_away=lam_a,
        lambda_total=lam_h + lam_a,
        p_over_15=p15,
        p_over_25=p25,
        p_over_35=p35,
        features_json=feats,
        is_locked=True,
    )


def build_predictions(
    *,
    days: int | None = None,
    force: bool = False,
) -> BuildStats:
    """Create predictions for upcoming fixtures."""
    stats = BuildStats()
    for fixture in upcoming_fixtures(days=days):
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
