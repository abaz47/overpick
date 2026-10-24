"""Daily schedule sync for current-season leagues."""

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from apps.matches.services.api_football import (
    ApiFootballClient,
    ApiFootballError,
)
from apps.matches.services.sync import (
    current_season_leagues,
    sync_schedule,
)
from apps.predictions.services.build import (
    build_predictions,
)


class Command(BaseCommand):
    """Refresh calendars for current seasons, then predict."""

    help = (
        "Daily job: sync fixtures for current-season "
        "leagues (~1 API call each), then build_predictions."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--max-requests",
            type=int,
            default=None,
            help="Stop after N API calls",
        )
        parser.add_argument(
            "--skip-predict",
            action="store_true",
            help="Do not run build_predictions after sync",
        )

    def handle(self, *args, **options) -> None:
        try:
            client = ApiFootballClient()
        except ApiFootballError as exc:
            raise CommandError(str(exc)) from exc

        n = current_season_leagues().count()
        self.stdout.write(
            f"sync_schedule: {n} current-season leagues…",
        )
        stats = sync_schedule(
            client,
            max_requests=options["max_requests"],
        )
        summary = (
            "sync_schedule: "
            f"leagues={stats.leagues} "
            f"skipped={stats.skipped} "
            f"seen={stats.fixtures_seen} "
            f"created={stats.fixtures_created} "
            f"updated={stats.fixtures_updated} "
            f"api_requests={stats.api_requests} "
            f"stopped={stats.stopped_reason or '-'}"
        )
        for err in stats.errors:
            self.stderr.write(self.style.WARNING(err))
        if stats.stopped_reason == "rate_limit":
            self.stdout.write(self.style.WARNING(summary))
            return
        self.stdout.write(self.style.SUCCESS(summary))

        if options["skip_predict"]:
            return
        pred = build_predictions()
        self.stdout.write(
            self.style.SUCCESS(
                "build_predictions: "
                f"considered={pred.considered} "
                f"created={pred.created} "
                f"skipped_locked={pred.skipped_locked} "
                f"skipped_form={pred.skipped_form}",
            ),
        )
