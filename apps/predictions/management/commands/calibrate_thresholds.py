"""Fit P-calibration + GBM + suggest tip thresholds."""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.predictions.services.backtest import run_backtest
from apps.predictions.services.calibrate import (
    calibrate_all,
    calibrate_hybrid_o25,
    calibrate_leagues_hybrid,
    fit_probability_calibration,
)
from apps.predictions.services.gbm_model import train_production_gbm
from apps.predictions.services.league_thresholds import (
    save_league_thresholds,
)

ENV_KEYS = {
    "o15": "SIGNAL_THRESHOLD_O15",
    "o25": "SIGNAL_THRESHOLD_O25",
    "o35": "SIGNAL_THRESHOLD_O35",
}


class Command(BaseCommand):
    """Refit O2.5 calibration, GBM, and tip thresholds."""

    help = (
        "Walk-forward backtest → fit raw→calibrated P(O2.5), "
        "train hybrid GBM, suggest tip thresholds on hybrid "
        "scale. Use --apply to patch .env (then restart web)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write new values into .env",
        )
        parser.add_argument(
            "--env-file",
            type=str,
            default=".env",
            help="Path to .env (default: .env)",
        )
        parser.add_argument(
            "--skip-gbm",
            action="store_true",
            help="Skip GBM retrain (debug).",
        )

    def handle(self, *args, **options) -> None:
        report = run_backtest()
        cal_path = fit_probability_calibration(report.rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"O2.5 calibration → {cal_path} (n={len(report.rows)})",
            ),
        )

        if not options["skip_gbm"]:
            gbm_path = train_production_gbm()
            self.stdout.write(
                self.style.SUCCESS(f"GBM model → {gbm_path}"),
            )

        current = {
            "o15": float(settings.SIGNAL_THRESHOLD_O15),
            "o25": float(settings.SIGNAL_THRESHOLD_O25),
            "o35": float(settings.SIGNAL_THRESHOLD_O35),
        }
        self.stdout.write(
            "Current thresholds (O2.5 on hybrid): "
            f"O15={current['o15']:.2f} "
            f"O25={current['o25']:.2f} "
            f"O35={current['o35']:.2f}",
        )
        suggestions = calibrate_all(
            current=current,
            rows=report.rows,
        )
        # Override O2.5 suggestion with hybrid-scale search.
        hybrid_cand = calibrate_hybrid_o25(
            current_thr=current["o25"],
        )
        if hybrid_cand is not None:
            suggestions["o25"] = hybrid_cand
            self.stdout.write("O2.5 thr from hybrid grid.")
        elif suggestions.get("o25") is not None:
            self.stdout.write(
                "O2.5 thr from Poisson-cal grid (no hybrid cand).",
            )

        payload = {"current": current, "suggested": {}}
        changed = False
        for market, cand in suggestions.items():
            key = ENV_KEYS[market]
            if cand is None:
                self.stdout.write(
                    f"  {key}: keep {current[market]:.2f}",
                )
                continue
            changed = True
            payload["suggested"][market] = {
                "threshold": cand.threshold,
                "hit_rate": cand.hit_rate,
                "coverage": cand.coverage,
                "signals": cand.signals,
            }
            self.stdout.write(
                self.style.WARNING(
                    f"  {key}: {current[market]:.2f} → "
                    f"{cand.threshold:.2f} "
                    f"(hit={cand.hit_rate:.1%}, "
                    f"cov={cand.coverage:.1%})",
                ),
            )

        out = Path("reports/calibrated_thresholds.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(f"Wrote {out}")

        # Global thr for league floors: use suggested o25 if any.
        o25_global = current["o25"]
        if suggestions.get("o25") is not None:
            o25_global = suggestions["o25"].threshold
        league_data = calibrate_leagues_hybrid(
            global_thr=o25_global,
        )
        # Preserve o15/o35 from previous file via merge-max save.
        league_path = save_league_thresholds(league_data)
        self.stdout.write(
            f"League hybrid overrides: {len(league_data)} → {league_path}",
        )

        if not options["apply"]:
            if changed:
                self.stdout.write(
                    "Dry-run only. Re-run with --apply "
                    "to patch .env, then restart web + "
                    "build_predictions --force.",
                )
            return

        env_path = Path(options["env_file"])
        text = (
            env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        )
        applied = 0
        for market, cand in suggestions.items():
            if cand is None:
                continue
            if cand.threshold < current[market]:
                self.stdout.write(
                    self.style.WARNING(
                        f"  skip weaken {ENV_KEYS[market]} "
                        f"{current[market]:.2f} → "
                        f"{cand.threshold:.2f}",
                    ),
                )
                continue
            key = ENV_KEYS[market]
            line = f"{key}={cand.threshold:.2f}"
            pattern = re.compile(
                rf"^{re.escape(key)}=.*$",
                re.M,
            )
            if pattern.search(text):
                text = pattern.sub(line, text)
            else:
                text = text.rstrip() + "\n" + line + "\n"
            applied += 1
        if applied == 0:
            self.stdout.write(
                "Nothing stricter to apply (calibration + "
                "GBM + league JSON already updated).",
            )
            return
        env_path.write_text(text, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {env_path}. Restart the app "
                "and run build_predictions --force.",
            ),
        )
