"""Tests for O2.5 / BTTS pick selection."""

from apps.predictions.services.signals import (
    build_signal_flags,
)


def test_o25_pick_when_above_threshold(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    settings.SIGNAL_THRESHOLD_BTTS = 0.62
    flags = build_signal_flags(0.90, 0.72, 0.50, p_btts=0.50)
    assert flags["primary"] == "o25"
    assert flags["o25"] is True
    assert flags["btts"] is False
    assert flags["o15"] is False
    assert flags["o35"] is False


def test_btts_only_pick(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    settings.SIGNAL_THRESHOLD_BTTS = 0.62
    flags = build_signal_flags(0.90, 0.60, 0.40, p_btts=0.70)
    assert flags["primary"] == "btts"
    assert flags["o25"] is False
    assert flags["btts"] is True


def test_dual_o25_and_btts(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    settings.SIGNAL_THRESHOLD_BTTS = 0.62
    flags = build_signal_flags(0.90, 0.72, 0.50, p_btts=0.68)
    assert flags["o25"] is True
    assert flags["btts"] is True
    assert flags["primary"] == "o25"


def test_no_pick_below_thresholds(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    settings.SIGNAL_THRESHOLD_BTTS = 0.62
    flags = build_signal_flags(0.95, 0.60, 0.40, p_btts=0.55)
    assert flags["primary"] is None
    assert flags["o25"] is False
    assert flags["btts"] is False


def test_never_picks_o15_or_o35(settings) -> None:
    settings.SIGNAL_THRESHOLD_O25 = 0.65
    settings.SIGNAL_THRESHOLD_BTTS = 0.62
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
    settings.SIGNAL_THRESHOLD_BTTS = 0.62
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
            p_btts=0.50,
            league_api_id=39,
        )["primary"]
        is None
    )
    assert (
        build_signal_flags(
            0.90,
            0.72,
            0.40,
            p_btts=0.50,
            league_api_id=39,
        )["primary"]
        == "o25"
    )
    lt.clear_threshold_cache()
