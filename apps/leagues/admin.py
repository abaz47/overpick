"""Admin for leagues and teams."""

from django.contrib import admin

from apps.leagues.models import League, Team


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    """League admin."""

    list_display = (
        "name",
        "country",
        "code",
        "season",
        "api_id",
        "is_active",
        "last_synced_at",
    )
    list_filter = ("is_active", "country", "season")
    search_fields = ("name", "code", "country")
    list_editable = ("is_active",)
    readonly_fields = ("last_synced_at",)
    ordering = ("country", "name", "-season")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Team admin."""

    list_display = ("name", "api_id", "updated_at")
    search_fields = ("name", "api_id")
    ordering = ("name",)
