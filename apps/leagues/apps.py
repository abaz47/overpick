"""Leagues app config."""

from django.apps import AppConfig


class LeaguesConfig(AppConfig):
    """Application configuration for leagues."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.leagues"
    label = "leagues"
    verbose_name = "Leagues"
