"""Predictions app config."""

from django.apps import AppConfig


class PredictionsConfig(AppConfig):
    """Application configuration for predictions."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.predictions"
    label = "predictions"
    verbose_name = "Predictions"
