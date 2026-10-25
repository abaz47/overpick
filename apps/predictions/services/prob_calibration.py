"""Empirical calibration map for model probabilities (O2.5).

Fits a monotone map raw P → calibrated P from walk-forward
reliability bins (no sklearn). Tips and min-odds use the
calibrated value.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "prob_calibration_o25.json"
)


def _pav(ys: list[float]) -> list[float]:
    """Pool Adjacent Violators — non-decreasing means."""
    if not ys:
        return []
    blocks: list[tuple[float, float]] = []
    for y in ys:
        blocks.append((1.0, float(y)))
        while len(blocks) >= 2 and blocks[-2][1] > blocks[-1][1]:
            w1, v1 = blocks[-2]
            w2, v2 = blocks[-1]
            blocks[-2:] = [
                (w1 + w2, (w1 * v1 + w2 * v2) / (w1 + w2)),
            ]
    out: list[float] = []
    for weight, value in blocks:
        out.extend([value] * int(round(weight)))
    n = len(ys)
    if len(out) < n:
        out.extend([out[-1]] * (n - len(out)))
    return out[:n]


def reliability_knots(
    pairs: list[tuple[float, bool]],
    *,
    step: float = 0.05,
    min_bin: int = 30,
) -> list[tuple[float, float]]:
    """Build (raw_avg, empirical_freq) knots, monotone in freq."""
    if not pairs:
        return [(0.0, 0.0), (1.0, 1.0)]
    buckets: dict[int, list[tuple[float, bool]]] = {}
    n_bins = int(round(1.0 / step))
    for p, hit in pairs:
        p = max(0.0, min(1.0, float(p)))
        idx = min(int(p / step), n_bins - 1)
        buckets.setdefault(idx, []).append((p, hit))
    xs: list[float] = []
    ys: list[float] = []
    for idx in sorted(buckets):
        items = buckets[idx]
        if len(items) < min_bin:
            continue
        avg_p = sum(p for p, _ in items) / len(items)
        freq = sum(1 for _, h in items if h) / len(items)
        xs.append(avg_p)
        ys.append(freq)
    if len(xs) < 2:
        base = sum(1 for _, h in pairs if h) / len(pairs)
        return [(0.0, 0.0), (0.5, base), (1.0, 1.0)]
    ys_m = _pav(ys)
    knots = list(zip(xs, ys_m, strict=True))
    if knots[0][0] > 0.0:
        knots.insert(0, (0.0, max(0.0, knots[0][1] * 0.5)))
    if knots[-1][0] < 1.0:
        last_y = min(
            1.0,
            knots[-1][1] + (1.0 - knots[-1][1]) * 0.5,
        )
        knots.append((1.0, last_y))
    return knots


def interpolate(
    knots: list[tuple[float, float]],
    x: float,
) -> float:
    """Piecewise-linear map through knots; clamp to [0, 1]."""
    if not knots:
        return max(0.0, min(1.0, x))
    x = max(0.0, min(1.0, float(x)))
    if x <= knots[0][0]:
        return max(0.0, min(1.0, knots[0][1]))
    if x >= knots[-1][0]:
        return max(0.0, min(1.0, knots[-1][1]))
    for i in range(len(knots) - 1):
        x0, y0 = knots[i]
        x1, y1 = knots[i + 1]
        if x0 <= x <= x1:
            if x1 <= x0:
                return y1
            t = (x - x0) / (x1 - x0)
            return max(0.0, min(1.0, y0 + t * (y1 - y0)))
    return max(0.0, min(1.0, x))


def fit_o25_calibration(
    pairs: list[tuple[float, bool]],
) -> list[tuple[float, float]]:
    """Fit O2.5 calibration knots from (p_raw, hit) pairs."""
    return reliability_knots(pairs)


def save_o25_calibration(
    knots: list[tuple[float, float]],
    path: Path | None = None,
) -> Path:
    """Persist knots as JSON."""
    target = path or _DATA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "market": "o25",
        "knots": [{"x": x, "y": y} for x, y in knots],
    }
    target.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    clear_calibration_cache()
    return target


@lru_cache(maxsize=1)
def _load_knots() -> tuple[tuple[float, float], ...]:
    if not _DATA_PATH.exists():
        return ((0.0, 0.0), (1.0, 1.0))
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return ((0.0, 0.0), (1.0, 1.0))
    knots = raw.get("knots") or []
    out: list[tuple[float, float]] = []
    for row in knots:
        try:
            out.append((float(row["x"]), float(row["y"])))
        except KeyError, TypeError, ValueError:
            continue
    if len(out) < 2:
        return ((0.0, 0.0), (1.0, 1.0))
    return tuple(out)


def clear_calibration_cache() -> None:
    """Drop cached knots after refit."""
    _load_knots.cache_clear()


def calibrate_o25(p_raw: float) -> float:
    """Map raw model P(O2.5) → calibrated probability."""
    return interpolate(list(_load_knots()), p_raw)
