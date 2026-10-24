"""Totals prediction models."""

from django.db import models


class Prediction(models.Model):
    """Immutable snapshot of a totals model output.

    Created before kickoff and locked so history
    compares the pre-match forecast to the result.
    """

    fixture = models.OneToOneField(
        "matches.Fixture",
        on_delete=models.CASCADE,
        related_name="prediction",
    )
    model_version = models.CharField(
        max_length=32,
        default="poisson_v1",
    )
    lambda_home = models.FloatField()
    lambda_away = models.FloatField()
    lambda_total = models.FloatField()
    p_over_15 = models.FloatField(
        help_text="P(total goals >= 2)",
    )
    p_over_25 = models.FloatField(
        help_text="P(total goals >= 3)",
    )
    p_over_35 = models.FloatField(
        help_text="P(total goals >= 4)",
    )
    p_btts = models.FloatField(
        null=True,
        blank=True,
        help_text="P(both teams score)",
    )
    features_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Form inputs used for the forecast",
    )
    is_locked = models.BooleanField(
        default=True,
        help_text="Do not overwrite after creation",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "prediction"
        verbose_name_plural = "predictions"

    def __str__(self) -> str:
        return f"Prediction {self.fixture_id} λ={self.lambda_total:.2f}"

    @property
    def is_hit_over_15(self) -> bool | None:
        """Whether O1.5 landed (needs FT score)."""
        total = self.fixture.total_goals
        if total is None:
            return None
        return total >= 2

    @property
    def is_hit_over_25(self) -> bool | None:
        """Whether O2.5 landed (needs FT score)."""
        total = self.fixture.total_goals
        if total is None:
            return None
        return total >= 3

    @property
    def is_hit_over_35(self) -> bool | None:
        """Whether O3.5 landed (needs FT score)."""
        total = self.fixture.total_goals
        if total is None:
            return None
        return total >= 4

    @property
    def is_hit_btts(self) -> bool | None:
        """Whether both teams scored (needs FT score)."""
        fx = self.fixture
        if fx.goals_home is None or fx.goals_away is None:
            return None
        return fx.goals_home >= 1 and fx.goals_away >= 1
