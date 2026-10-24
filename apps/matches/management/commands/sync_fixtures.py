"""Sync fixtures from API-Football."""

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from apps.leagues.models import League
from apps.matches.services.api_football import (
    ApiFootballClient,
    ApiFootballError,
    RateLimitError,
)
from apps.matches.services.sync import (
    sync_active_leagues,
    sync_league,
)


class Command(BaseCommand):
    """Pull fixtures for active (or one) league."""

    help = (
        "Sync fixtures from API-Football into DB. "
        "Requires API_FOOTBALL_KEY. ~1 request per "
        "league-season. Free plan: 100 req/day, "
        "~10/min — use --max-requests and re-run."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--league-api-id",
            type=int,
            default=None,
            help="Sync only this API league id",
        )
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="With --league-api-id: season year",
        )
        parser.add_argument(
            "--max-requests",
            type=int,
            default=None,
            help="Stop after N API calls (quota guard)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-sync even if last_synced_at set",
        )

    def handle(self, *args, **options) -> None:
        try:
            client = ApiFootballClient()
        except ApiFootballError as exc:
            raise CommandError(str(exc)) from exc

        league_api_id = options["league_api_id"]
        if league_api_id is not None:
            stats = self._sync_one(
                client,
                league_api_id,
                options.get("season"),
            )
        else:
            active = League.objects.filter(
                is_active=True,
            ).count()
            if active == 0:
                raise CommandError(
                    "No active leagues. Run: "
                    "python manage.py seed_leagues "
                    "--from-season 2022 --to-season 2026",
                )
            stats = sync_active_leagues(
                client,
                max_requests=options["max_requests"],
                skip_synced=not options["force"],
            )

        summary = (
            "sync_fixtures: "
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
            self.stdout.write(
                self.style.WARNING(
                    "Quota/rate limit hit — re-run later "
                    "to continue (already synced skipped).",
                ),
            )
            return
        if stats.errors and stats.leagues == 0:
            raise CommandError(
                f"{summary}. Sync finished with errors only.",
            )
        self.stdout.write(self.style.SUCCESS(summary))

    def _sync_one(
        self,
        client: ApiFootballClient,
        league_api_id: int,
        season: int | None,
    ):
        qs = League.objects.filter(api_id=league_api_id)
        if season is not None:
            qs = qs.filter(season=season)
        leagues = list(qs.order_by("season"))
        if not leagues:
            raise CommandError(
                f"League api_id={league_api_id} "
                f"season={season} not found. "
                "Run seed_leagues first.",
            )
        from apps.matches.services.sync import SyncStats

        stats = SyncStats()
        for league in leagues:
            try:
                part = sync_league(league, client)
            except RateLimitError as exc:
                stats.errors.append(str(exc))
                stats.stopped_reason = "rate_limit"
                break
            except ApiFootballError as exc:
                raise CommandError(str(exc)) from exc
            stats.leagues += 1
            stats.fixtures_seen += part.fixtures_seen
            stats.fixtures_created += part.fixtures_created
            stats.fixtures_updated += part.fixtures_updated
            stats.teams_created += part.teams_created
            stats.teams_updated += part.teams_updated
        stats.api_requests = client.request_count
        return stats
