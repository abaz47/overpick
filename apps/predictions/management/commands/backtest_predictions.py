"""Walk-forward backtest for threshold calibration."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.predictions.services.backtest import (
    format_report,
    run_backtest,
)


class Command(BaseCommand):
    """Calibrate SIGNAL_THRESHOLD_* from full history."""

    help = (
        "Walk-forward backtest of poisson_v1 over "
        "finished fixtures; prints threshold grids."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Only score fixtures of this season "
            "(histories still use earlier matches).",
        )
        parser.add_argument(
            "--league-api-id",
            type=int,
            default=None,
            help="Only score fixtures of this league api_id.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Cap finished fixtures loaded (debug).",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Write report to this path (default: reports/backtest.txt).",
        )

    def handle(self, *args, **options) -> None:
        self.stdout.write("Running walk-forward backtest…")
        report = run_backtest(
            season=options["season"],
            league_api_id=options["league_api_id"],
            limit=options["limit"],
        )
        text = format_report(report)
        self.stdout.write(text)

        out = options["output"] or "reports/backtest.txt"
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
