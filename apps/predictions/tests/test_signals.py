"""Tests for Over 2.5 pick selection."""

from apps.predictions.services.signals import (
    build_signal_flags,
)


def test_o25_pick_when_above_threshold(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    flags = build_signal_flags(0.90, 0.72, 0.50, p_btts=0.90)
    assert flags["primary"] == "o25"
    assert flags["o25"] is True
    assert flags["btts"] is False
    assert flags["o15"] is False
    assert flags["o35"] is False
    assert "p_over_25_cal" in flags
    # Identity calibration file → cal ≈ raw.
    assert abs(flags["p_over_25_cal"] - 0.72) < 0.05


def test_no_pick_below_o25_threshold(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    flags = build_signal_flags(0.95, 0.60, 0.40, p_btts=0.90)
    assert flags["primary"] is None
    assert flags["o25"] is False
    assert flags["btts"] is False


def test_never_picks_btts(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    flags = build_signal_flags(0.90, 0.60, 0.40, p_btts=0.99)
    assert flags["primary"] is None
    assert flags["btts"] is False


def test_never_picks_o15_or_o35(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    flags = build_signal_flags(0.99, 0.70, 0.97, p_btts=0.40)
    assert flags["primary"] == "o25"
    assert flags["o15"] is False
    assert flags["o35"] is False


def test_league_stricter_o25(
    settings,
    tmp_path,
    monkeypatch,
):
    from apps.predictions.services import league_thresholds as lt

    settings.SIGNAL_THRESHOLD_O25 = 0.65
    path = tmp_path / "league_thresholds.json"
    path.write_text(
        '{"39": {"o25": 0.70}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(lt, "_DATA_PATH", path)
    lt.clear_threshold_cache()
    assert (
        build_signal_flags(
            0.90,
            0.68,
            0.40,
            league_api_id=39,
        )["primary"]
        is None
    )
    assert (
        build_signal_flags(
            0.90,
            0.72,
            0.40,
            league_api_id=39,
        )["primary"]
        == "o25"
    )
    lt.clear_threshold_cache()
