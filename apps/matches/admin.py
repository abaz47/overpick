"""Admin for fixtures."""

from django.contrib import admin

from apps.matches.models import Fixture


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    """Fixture admin."""

    list_display = (
        "kickoff_at",
        "league",
        "home",
        "away",
        "status",
        "score_display",
        "api_id",
    )
    list_filter = ("status", "league", "season")
    search_fields = (
        "home__name",
        "away__name",
        "api_id",
        "round",
    )
    autocomplete_fields = ("league", "home", "away")
    date_hierarchy = "kickoff_at"
    ordering = ("-kickoff_at",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Score")
    def score_display(self, obj: Fixture) -> str:
        """Show FT score or dash."""
        if obj.goals_home is None or obj.goals_away is None:
            return "—"
        return f"{obj.goals_home}:{obj.goals_away}"
