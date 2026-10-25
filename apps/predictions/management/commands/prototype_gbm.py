"""Run Poisson vs GBM vs hybrid walk-forward prototype."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.predictions.services.gbm_prototype import (
    format_prototype_report,
    run_gbm_prototype,
)


class Command(BaseCommand):
    """Compare poisson_v4 with a residual GBM on O2.5."""

    help = (
        "Walk-forward prototype: Poisson vs LightGBM/HGB "
        "vs hybrid on finished fixtures (no tip changes)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Cap finished fixtures loaded (debug).",
        )
        parser.add_argument(
            "--min-train",
            type=int,
            default=8000,
            help="Min train rows before first test season.",
        )
        parser.add_argument(
            "--gbm-thr",
            type=float,
            default=0.60,
            help="Tip threshold on GBM probability.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Write report path (default: reports/gbm_prototype.txt).",
        )

    def handle(self, *args, **options) -> None:
        self.stdout.write("Running GBM prototype…")
        report = run_gbm_prototype(
            limit=options["limit"],
            min_train=options["min_train"],
            gbm_thr=options["gbm_thr"],
            hybrid_thr=options["gbm_thr"],
        )
        text = format_prototype_report(report)
        self.stdout.write(text)

        out = options["output"] or "reports/gbm_prototype.txt"
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
