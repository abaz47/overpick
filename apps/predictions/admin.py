"""Admin for predictions."""

from django.contrib import admin

from apps.predictions.models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    """Prediction admin."""

    list_display = (
        "fixture",
        "model_version",
        "lambda_total",
        "p_over_15",
        "p_over_25",
        "p_over_35",
        "p_btts",
        "is_locked",
        "created_at",
    )
    list_filter = ("model_version", "is_locked")
    search_fields = (
        "fixture__home__name",
        "fixture__away__name",
        "fixture__api_id",
    )
    autocomplete_fields = ("fixture",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
