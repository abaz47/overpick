"""Dashboard app config."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """UI views for OverPick analytics."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    label = "dashboard"
    verbose_name = "Dashboard"
