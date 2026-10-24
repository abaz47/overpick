"""Fixture (match) models."""

from django.db import models


class Fixture(models.Model):
    """Scheduled or finished football match."""

    class Status(models.TextChoices):
        """API-Football-style match status codes."""

        NS = "NS", "Not started"
        TBD = "TBD", "Time to be defined"
        LIVE = "LIVE", "Live"
        HT = "HT", "Halftime"
        FT = "FT", "Finished"
        AET = "AET", "After extra time"
        PEN = "PEN", "Penalties"
        PST = "PST", "Postponed"
        CANC = "CANC", "Cancelled"
        ABD = "ABD", "Abandoned"
        AWD = "AWD", "Technical loss"
        WO = "WO", "Walkover"
        OTHER = "OTHER", "Other"

    api_id = models.PositiveIntegerField(
        unique=True,
        help_text="API-Football fixture id",
    )
    league = models.ForeignKey(
        "leagues.League",
        on_delete=models.CASCADE,
        related_name="fixtures",
    )
    season = models.PositiveSmallIntegerField()
    round = models.CharField(max_length=64, blank=True)
    home = models.ForeignKey(
        "leagues.Team",
        on_delete=models.PROTECT,
        related_name="home_fixtures",
    )
    away = models.ForeignKey(
        "leagues.Team",
        on_delete=models.PROTECT,
        related_name="away_fixtures",
    )
    kickoff_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.NS,
        db_index=True,
    )
    goals_home = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    goals_away = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kickoff_at"]
        verbose_name = "fixture"
        verbose_name_plural = "fixtures"
        indexes = [
            models.Index(
                fields=["league", "kickoff_at"],
                name="matches_fix_league_kickoff",
            ),
            models.Index(
                fields=["status", "kickoff_at"],
                name="matches_fix_status_kickoff",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.home} vs {self.away} ({self.kickoff_at:%Y-%m-%d})"

    @property
    def total_goals(self) -> int | None:
        """Full-time total goals, if available."""
        if self.goals_home is None or self.goals_away is None:
            return None
        return self.goals_home + self.goals_away

    @property
    def is_finished(self) -> bool:
        """Whether the match has a final score."""
        return self.status in {
            self.Status.FT,
            self.Status.AET,
            self.Status.PEN,
        }
