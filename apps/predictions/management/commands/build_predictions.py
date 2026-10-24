"""Build Poisson totals predictions for upcoming matches."""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.predictions.services.build import (
    build_predictions,
)


class Command(BaseCommand):
    """Create locked Prediction rows (poisson_v1)."""

    help = (
        "Build Over 1.5/2.5/3.5 probabilities for "
        "upcoming NS/TBD fixtures using venue form "
        "+ independent Poisson."
    )

    def add_arguments(self, parser) -> None:
        default_days = int(
            getattr(settings, "PREDICTION_HORIZON_DAYS", 3),
        )
        parser.add_argument(
            "--days",
            type=int,
            default=default_days,
            help=(
                "Only fixtures within N days "
                f"(default: {default_days}; "
                "0 = all upcoming)"
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing locked predictions",
        )

    def handle(self, *args, **options) -> None:
        days = options["days"]
        if days == 0:
            days = None
        stats = build_predictions(
            days=days,
            force=options["force"],
        )
        summary = (
            "build_predictions: "
            f"considered={stats.considered} "
            f"created={stats.created} "
            f"skipped_locked={stats.skipped_locked} "
            f"skipped_form={stats.skipped_form} "
            f"errors={len(stats.errors)}"
        )
        for err in stats.errors:
            self.stderr.write(self.style.WARNING(err))
        self.stdout.write(self.style.SUCCESS(summary))
