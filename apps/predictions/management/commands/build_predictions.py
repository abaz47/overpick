"""Build totals predictions for calendar-day batch windows."""

from django.core.management.base import BaseCommand, CommandError

from apps.predictions.services.batch import batch_label
from apps.predictions.services.build import (
    build_predictions,
)


class Command(BaseCommand):
    """Create locked Prediction rows (hybrid_v1)."""

    help = (
        "Build Over picks for Today/Tomorrow calendar days "
        "(00:00→00:00 MSK). Evening cron: "
        "--window tomorrow --force (does not touch Today)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Legacy: only fixtures within N days "
                "(disables daily batch). "
                "0 = all upcoming NS/TBD"
            ),
        )
        parser.add_argument(
            "--window",
            choices=("today", "tomorrow", "both"),
            default="both",
            help="Which calendar-day batch to build.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Replace existing locked predictions "
                "inside the selected window only."
            ),
        )

    def handle(self, *args, **options) -> None:
        days = options["days"]
        use_batch = days is None
        if days == 0:
            days = None
            use_batch = False
        window = options["window"]
        if not use_batch and window != "both":
            raise CommandError(
                "--window requires batch mode (omit --days).",
            )
        stats = build_predictions(
            days=days,
            force=options["force"],
            use_batch=use_batch,
            window=window,
        )
        summary = (
            "build_predictions: "
            f"window={window} "
            f"considered={stats.considered} "
            f"created={stats.created} "
            f"skipped_locked={stats.skipped_locked} "
            f"skipped_form={stats.skipped_form} "
            f"errors={len(stats.errors)}"
        )
        if stats.batch_start is not None:
            summary += (
                f" batch={batch_label(stats.batch_start)}"
                f"→{batch_label(stats.batch_end)}"
            )
        for err in stats.errors:
            self.stderr.write(self.style.WARNING(err))
        self.stdout.write(self.style.SUCCESS(summary))
