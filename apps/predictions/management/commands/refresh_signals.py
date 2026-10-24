"""Recompute Pick flags (O2.5) on locked predictions."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.predictions.models import Prediction
from apps.predictions.services.signals import (
    build_signal_flags,
)


class Command(BaseCommand):
    """Update features_json.signals from stored probabilities."""

    help = (
        "Refresh Over 2.5 pick badges on existing predictions "
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
            feats["signals"] = build_signal_flags(
                float(pred.p_over_15),
                float(pred.p_over_25),
                float(pred.p_over_35),
                p_btts=pred.p_btts,
                league_api_id=league_api_id,
            )
            pred.features_json = feats
            pred.save(update_fields=["features_json"])
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"refresh_signals: updated={updated}",
            ),
        )
