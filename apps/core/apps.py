"""Core app config."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Application configuration for core."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"
