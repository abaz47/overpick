"""League and team catalog models."""

from django.db import models


class League(models.Model):
    """Football competition tracked by OverPick."""

    api_id = models.PositiveIntegerField(
        unique=True,
        help_text="API-Football league id",
    )
    name = models.CharField(max_length=128)
    country = models.CharField(max_length=64)
    code = models.CharField(
        max_length=16,
        blank=True,
        help_text="Short code, e.g. PL, PD",
    )
    season = models.PositiveSmallIntegerField(
        help_text="Season start year, e.g. 2025",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["country", "name"]
        verbose_name = "league"
        verbose_name_plural = "leagues"

    def __str__(self) -> str:
        return f"{self.name} ({self.season})"


class Team(models.Model):
    """Football club / national team."""

    api_id = models.PositiveIntegerField(
        unique=True,
        help_text="API-Football team id",
    )
    name = models.CharField(max_length=128)
    logo_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "team"
        verbose_name_plural = "teams"

    def __str__(self) -> str:
        return self.name
