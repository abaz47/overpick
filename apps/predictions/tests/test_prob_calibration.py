"""Tests for O2.5 probability calibration."""

from apps.predictions.services.prob_calibration import (
    _pav,
    calibrate_o25,
    clear_calibration_cache,
    fit_o25_calibration,
    interpolate,
    save_o25_calibration,
)


def test_pav_enforces_monotone() -> None:
    assert _pav([0.2, 0.5, 0.4, 0.7]) == [0.2, 0.45, 0.45, 0.7]


def test_interpolate_linear() -> None:
    knots = [(0.0, 0.0), (0.5, 0.4), (1.0, 1.0)]
    assert abs(interpolate(knots, 0.25) - 0.2) < 1e-9


def test_fit_and_apply(tmp_path, monkeypatch) -> None:
    from apps.predictions.services import prob_calibration as pc

    path = tmp_path / "cal.json"
    monkeypatch.setattr(pc, "_DATA_PATH", path)
    clear_calibration_cache()
    # Overconfident model: high P, lower hits.
    pairs = []
    for _ in range(40):
        pairs.append((0.55, True))
        pairs.append((0.55, False))
    for _ in range(40):
        pairs.append((0.75, True))
        pairs.append((0.75, False))
        pairs.append((0.75, False))
    knots = fit_o25_calibration(pairs)
    save_o25_calibration(knots, path=path)
    clear_calibration_cache()
    cal_high = calibrate_o25(0.75)
    assert cal_high < 0.75
    clear_calibration_cache()
