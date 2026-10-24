"""Build Poisson totals predictions for upcoming matches."""

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
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Only fixtures within N days (default: all)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace existing locked predictions",
        )

    def handle(self, *args, **options) -> None:
        stats = build_predictions(
            days=options["days"],
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
