"""Matches app config."""

from django.apps import AppConfig


class MatchesConfig(AppConfig):
    """Application configuration for matches."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.matches"
    label = "matches"
    verbose_name = "Matches"
