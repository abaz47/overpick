"""Weekly-style threshold calibration from full backtest."""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.predictions.services.calibrate import (
    calibrate_all,
    write_league_calibration,
)

ENV_KEYS = {
    "o15": "SIGNAL_THRESHOLD_O15",
    "o25": "SIGNAL_THRESHOLD_O25",
    "o35": "SIGNAL_THRESHOLD_O35",
}


class Command(BaseCommand):
    """Suggest (and optionally apply) calibrated thresholds."""

    help = (
        "Walk-forward backtest → suggest SIGNAL_THRESHOLD_* "
        "when hit_rate≈threshold and coverage≥5%. "
        "Use --apply to patch .env (then restart web)."
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

    def handle(self, *args, **options) -> None:
        current = {
            "o15": float(settings.SIGNAL_THRESHOLD_O15),
            "o25": float(settings.SIGNAL_THRESHOLD_O25),
            "o35": float(settings.SIGNAL_THRESHOLD_O35),
        }
        self.stdout.write(
            "Current thresholds: "
            f"O15={current['o15']:.2f} "
            f"O25={current['o25']:.2f} "
            f"O35={current['o35']:.2f}",
        )
        suggestions = calibrate_all(current=current)
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

        league_data, league_path = write_league_calibration(
            global_thr=current,
        )
        self.stdout.write(
            f"League overrides: {len(league_data)} → {league_path}",
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
            # Never weaken global floors via --apply.
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
                "Nothing stricter to apply (league JSON already updated).",
            )
            return
        env_path.write_text(text, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {env_path}. Restart the app "
                "and run build_predictions --force.",
            ),
        )
