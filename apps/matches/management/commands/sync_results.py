"""Hourly results sync for today (+ yesterday)."""

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from apps.matches.services.api_football import (
    ApiFootballClient,
    ApiFootballError,
)
from apps.matches.services.sync import sync_results


class Command(BaseCommand):
    """Pull scores/status for recent calendar days."""

    help = (
        "Hourly job: fixtures?date= for today and "
        "yesterday (MSK). ~2 API requests. Updates "
        "scores so History hit-rates stay current."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days-back",
            type=int,
            default=1,
            help="Also sync N previous calendar days (default 1 = yesterday)",
        )

    def handle(self, *args, **options) -> None:
        try:
            client = ApiFootballClient()
        except ApiFootballError as exc:
            raise CommandError(str(exc)) from exc

        stats = sync_results(
            client,
            days_back=options["days_back"],
        )
        summary = (
            "sync_results: "
            f"seen={stats.fixtures_seen} "
            f"created={stats.fixtures_created} "
            f"updated={stats.fixtures_updated} "
            f"skipped_unknown_league={stats.skipped} "
            f"api_requests={stats.api_requests} "
            f"stopped={stats.stopped_reason or '-'}"
        )
        for err in stats.errors:
            self.stderr.write(self.style.WARNING(err))
        if stats.stopped_reason == "rate_limit":
            self.stdout.write(self.style.WARNING(summary))
            return
        self.stdout.write(self.style.SUCCESS(summary))
