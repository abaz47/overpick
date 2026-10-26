"""Recompute Pick flags (O2.5 hybrid) on locked predictions."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.predictions.models import Prediction
from apps.predictions.services.batch import batch_window_for
from apps.predictions.services.form import (
    build_form_features,
    expected_goals,
)
from apps.predictions.services.gbm_features import (
    build_gbm_feature_dict,
)
from apps.predictions.services.signals import (
    build_signal_flags,
    freeze_signals,
    is_signals_frozen,
)


class Command(BaseCommand):
    """Update features_json.signals (optionally one day only)."""

    help = (
        "Refresh Over 2.5 hybrid pick badges. "
        "Skips frozen tips. Use --untipped-only to add "
        "new tips without changing already published ones."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--window",
            choices=("today", "tomorrow", "all"),
            default="all",
            help="Limit refresh to one calendar-day batch.",
        )
        parser.add_argument(
            "--untipped-only",
            action="store_true",
            help="Skip rows that already have a primary tip.",
        )
        parser.add_argument(
            "--freeze",
            action="store_true",
            help="Freeze signals after refresh (evening lock).",
        )

    def handle(self, *args, **options) -> None:
        updated = 0
        skipped = 0
        rebuilt = 0
        qs = Prediction.objects.select_related(
            "fixture__league",
            "fixture__home",
            "fixture__away",
        )
        window = options["window"]
        if window in ("today", "tomorrow"):
            start, end = batch_window_for(window)
            qs = qs.filter(
                fixture__kickoff_at__gte=start,
                fixture__kickoff_at__lt=end,
            )
        for pred in qs.iterator():
            feats = dict(pred.features_json or {})
            if is_signals_frozen(feats):
                skipped += 1
                continue
            signals = feats.get("signals") or {}
            if options["untipped_only"] and signals.get("primary"):
                skipped += 1
                continue
            league_api_id = None
            if pred.fixture_id and pred.fixture.league_id:
                league_api_id = pred.fixture.league.api_id
            gbm_feats = feats.get("gbm_features")
            if not isinstance(gbm_feats, dict) and pred.fixture_id:
                try:
                    form = build_form_features(pred.fixture)
                    if form.enough_data:
                        lam_h, lam_a = expected_goals(form)
                        gbm_feats = build_gbm_feature_dict(
                            pred.fixture,
                            form,
                            p15=float(pred.p_over_15),
                            p25=float(pred.p_over_25),
                            p35=float(pred.p_over_35),
                            p_btts=float(pred.p_btts or 0.0),
                            lambda_home=lam_h,
                            lambda_away=lam_a,
                        )
                        feats["gbm_features"] = gbm_feats
                        rebuilt += 1
                except Exception:
                    gbm_feats = None
            feats["signals"] = build_signal_flags(
                float(pred.p_over_15),
                float(pred.p_over_25),
                float(pred.p_over_35),
                p_btts=pred.p_btts,
                league_api_id=league_api_id,
                gbm_features=gbm_feats
                if isinstance(gbm_feats, dict)
                else None,
            )
            if options["freeze"]:
                feats = freeze_signals(feats)
            pred.features_json = feats
            pred.save(update_fields=["features_json"])
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"refresh_signals: window={window} "
                f"updated={updated} skipped={skipped} "
                f"gbm_rebuilt={rebuilt}",
            ),
        )
