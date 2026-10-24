"""Per-league Pick thresholds (api_id → markets)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

MARKETS = ("o15", "o25", "o35", "btts")

_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "league_thresholds.json"
)


def default_thresholds() -> dict[str, float]:
    """Global Pick thresholds."""
    return {
        "o15": float(settings.SIGNAL_THRESHOLD_O15),
        "o25": float(settings.SIGNAL_THRESHOLD_O25),
        "o35": float(settings.SIGNAL_THRESHOLD_O35),
        "btts": float(
            getattr(settings, "SIGNAL_THRESHOLD_BTTS", 0.62),
        ),
    }


@lru_cache(maxsize=1)
def _load_file() -> dict[str, dict[str, float]]:
    if not _DATA_PATH.exists():
        return {}
    try:
        raw = json.loads(
            _DATA_PATH.read_text(encoding="utf-8"),
        )
    except OSError, json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        out[str(key)] = {m: float(val[m]) for m in MARKETS if m in val}
    return out


def clear_threshold_cache() -> None:
    """Drop cached JSON (after recalibration)."""
    _load_file.cache_clear()


def stricter_only(
    data: dict[str, dict[str, float]],
    global_thr: dict[str, float] | None = None,
) -> dict[str, dict[str, float]]:
    """Drop overrides that would weaken global floors."""
    base = global_thr or default_thresholds()
    out: dict[str, dict[str, float]] = {}
    for league_id, markets in data.items():
        kept: dict[str, float] = {}
        for market, thr in markets.items():
            if market not in MARKETS:
                continue
            if float(thr) > float(base[market]):
                kept[market] = float(thr)
        if kept:
            out[str(league_id)] = kept
    return out


def thresholds_for_league(
    league_api_id: int | None,
) -> dict[str, float]:
    """Merge global defaults with stricter league overrides."""
    base = default_thresholds()
    if league_api_id is None:
        return base
    overrides = _load_file().get(str(league_api_id)) or {}
    merged = dict(base)
    for market, thr in overrides.items():
        if market in MARKETS and float(thr) > merged[market]:
            merged[market] = float(thr)
    return merged


def save_league_thresholds(
    data: dict[str, dict[str, float]],
    path: Path | None = None,
) -> Path:
    """Write league threshold map to JSON (stricter only)."""
    target = path or _DATA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    cleaned = stricter_only(data)
    target.write_text(
        json.dumps(cleaned, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    clear_threshold_cache()
    return target
