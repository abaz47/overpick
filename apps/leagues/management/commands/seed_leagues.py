"""Seed default leagues for OverPick."""

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from apps.leagues.defaults import DEFAULT_LEAGUES
from apps.leagues.models import League


class Command(BaseCommand):
    """Create League rows for a season range."""

    help = (
        "Seed default 1st/2nd divisions for seasons "
        "[--from-season, --to-season]."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--from-season",
            type=int,
            default=None,
            help="First season year (e.g. 2022)",
        )
        parser.add_argument(
            "--to-season",
            type=int,
            default=None,
            help="Last season year (e.g. 2026)",
        )
        parser.add_argument(
            "--season",
            type=int,
            default=None,
            help="Single season (alias for from=to)",
        )
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Deactivate leagues whose api_id is not in the default list"
            ),
        )

    def handle(self, *args, **options) -> None:
        seasons = self._resolve_seasons(options)
        created = 0
        updated = 0
        seen_ids = [row["api_id"] for row in DEFAULT_LEAGUES]

        for season in seasons:
            for row in DEFAULT_LEAGUES:
                _obj, was_created = League.objects.update_or_create(
                    api_id=row["api_id"],
                    season=season,
                    defaults={
                        "name": row["name"],
                        "country": row["country"],
                        "code": row["code"],
                        "is_active": True,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        deactivated = 0
        if options["deactivate_missing"]:
            deactivated = League.objects.exclude(
                api_id__in=seen_ids,
            ).update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_leagues seasons={seasons[0]}..{seasons[-1]}: "
                f"created={created} updated={updated} "
                f"deactivated={deactivated}",
            ),
        )

    def _resolve_seasons(self, options: dict) -> list[int]:
        single = options.get("season")
        start = options.get("from_season")
        end = options.get("to_season")
        if single is not None:
            return [single]
        if start is None or end is None:
            raise CommandError(
                "Provide --season N or --from-season A --to-season B",
            )
        if end < start:
            raise CommandError(
                "--to-season must be >= --from-season",
            )
        return list(range(start, end + 1))
