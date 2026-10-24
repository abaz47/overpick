"""HTTP client for API-Football (api-sports.io)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://v3.football.api-sports.io"


class ApiFootballError(Exception):
    """Raised when API-Football returns an error."""


class RateLimitError(ApiFootballError):
    """Daily or per-minute quota exceeded."""


class ApiFootballClient:
    """Thin wrapper around API-Football fixtures."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        min_interval: float | None = None,
    ) -> None:
        key = api_key if api_key is not None else settings.API_FOOTBALL_KEY
        if not key:
            raise ApiFootballError(
                "API_FOOTBALL_KEY is empty. Set it in .env.",
            )
        configured = getattr(
            settings,
            "API_FOOTBALL_BASE_URL",
            None,
        )
        self._base_url = (base_url or configured or DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self._headers = {"x-apisports-key": key}
        self._timeout = timeout
        if min_interval is None:
            min_interval = float(
                getattr(
                    settings,
                    "API_FOOTBALL_MIN_INTERVAL",
                    0.5,
                ),
            )
        self._min_interval = min_interval
        self._last_request_at = 0.0
        self.request_count = 0

    def get_fixtures(
        self,
        league_id: int,
        season: int,
    ) -> list[dict[str, Any]]:
        """Fetch all fixtures for a league season."""
        params = {
            "league": league_id,
            "season": season,
        }
        data = self._get("/fixtures", params=params)
        response = data.get("response")
        if not isinstance(response, list):
            raise ApiFootballError(
                "Unexpected fixtures payload: "
                f"missing list for league={league_id}",
            )
        self._raise_for_api_errors(data, league_id)
        return response

    def get_status(self) -> dict[str, Any]:
        """Return account quota info."""
        data = self._get("/status", params={})
        self._raise_for_api_errors(data, context="status")
        response = data.get("response") or {}
        if not isinstance(response, dict):
            raise ApiFootballError("Bad status payload")
        return response

    def _raise_for_api_errors(
        self,
        data: dict[str, Any],
        league_id: int | None = None,
        context: str = "",
    ) -> None:
        errors = data.get("errors")
        if errors in (None, {}, []):
            return
        text = str(errors).lower()
        label = (
            f"league={league_id}"
            if league_id is not None
            else context or "request"
        )
        if "ratelimit" in text or "rate limit" in text:
            raise RateLimitError(
                f"Rate limit on {label}: {errors}",
            )
        if "request limit" in text:
            raise RateLimitError(
                f"Daily limit on {label}: {errors}",
            )
        raise ApiFootballError(
            f"API errors for {label}: {errors}",
        )

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)

    def _get(
        self,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        self._throttle()
        url = f"{self._base_url}{path}"
        logger.info(
            "API-Football GET %s params=%s",
            path,
            params,
        )
        try:
            with httpx.Client(
                timeout=self._timeout,
                headers=self._headers,
            ) as client:
                resp = client.get(url, params=params)
                self._last_request_at = time.monotonic()
                self.request_count += 1
                if resp.status_code == 429:
                    raise RateLimitError(
                        f"HTTP 429 on {path}",
                    )
                resp.raise_for_status()
        except RateLimitError:
            raise
        except httpx.HTTPError as exc:
            raise ApiFootballError(str(exc)) from exc
        payload = resp.json()
        if not isinstance(payload, dict):
            raise ApiFootballError(
                "API returned non-object JSON",
            )
        return payload
