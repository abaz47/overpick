"""Recompute Pick flags (O2.5 + BTTS) on locked predictions."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.predictions.models import Prediction
from apps.predictions.services.poisson import p_btts
from apps.predictions.services.signals import (
    build_signal_flags,
)


class Command(BaseCommand):
    """Update features_json.signals (+ p_btts) from lambdas."""

    help = (
        "Refresh O2.5 / BTTS pick badges on existing predictions "
        "without recomputing form (uses current thresholds)."
    )

    def handle(self, *args, **options) -> None:
        updated = 0
        qs = Prediction.objects.select_related(
            "fixture__league",
        )
        for pred in qs.iterator():
            feats = dict(pred.features_json or {})
            league_api_id = None
            if pred.fixture_id and pred.fixture.league_id:
                league_api_id = pred.fixture.league.api_id
            pb = pred.p_btts
            if pb is None:
                pb = p_btts(
                    float(pred.lambda_home),
                    float(pred.lambda_away),
                )
                pred.p_btts = pb
            feats["signals"] = build_signal_flags(
                float(pred.p_over_15),
                float(pred.p_over_25),
                float(pred.p_over_35),
                p_btts=float(pb),
                league_api_id=league_api_id,
            )
            pred.features_json = feats
            pred.save(
                update_fields=["features_json", "p_btts"],
            )
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"refresh_signals: updated={updated}",
            ),
        )
