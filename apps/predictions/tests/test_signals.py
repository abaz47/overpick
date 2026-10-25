"""Tests for Over 2.5 pick selection (hybrid)."""

from apps.predictions.services.signals import (
    build_signal_flags,
)


def test_o25_pick_when_above_threshold(settings, monkeypatch) -> None:
    from apps.predictions.services import signals as sig

    monkeypatch.setattr(sig, "calibrate_o25", lambda p: p)
    monkeypatch.setattr(
        sig,
        "predict_proba",
        lambda feats: 0.70,
    )
    settings.SIGNAL_THRESHOLD_O25 = 0.60
    flags = build_signal_flags(
        0.90,
        0.72,
        0.50,
        p_btts=0.90,
        gbm_features={"p_pois_25": 0.72},
    )
    assert flags["primary"] == "o25"
    assert flags["o25"] is True
    assert flags["tip_scale"] == "hybrid"
    assert abs(flags["p_hybrid"] - 0.71) < 1e-9  # 0.5*0.72+0.5*0.70


def test_no_pick_below_o25_threshold(settings, monkeypatch) -> None:
    from apps.predictions.services import signals as sig

    monkeypatch.setattr(sig, "calibrate_o25", lambda p: p)
    monkeypatch.setattr(sig, "predict_proba", lambda feats: 0.50)
    settings.SIGNAL_THRESHOLD_O25 = 0.60
    flags = build_signal_flags(
        0.95,
        0.55,
        0.40,
        p_btts=0.90,
        gbm_features={"p_pois_25": 0.55},
    )
    assert flags["primary"] is None
    assert flags["o25"] is False


def test_fallback_without_gbm(settings, monkeypatch) -> None:
    from apps.predictions.services import signals as sig

    monkeypatch.setattr(sig, "calibrate_o25", lambda p: p)
    settings.SIGNAL_THRESHOLD_O25 = 0.60
    flags = build_signal_flags(0.90, 0.72, 0.50)
    assert flags["tip_scale"] == "cal"
    assert flags["primary"] == "o25"
    assert flags["p_gbm"] is None


def test_never_picks_btts(settings, monkeypatch) -> None:
    from apps.predictions.services import signals as sig

    monkeypatch.setattr(sig, "calibrate_o25", lambda p: p)
    settings.SIGNAL_THRESHOLD_O25 = 0.60
    flags = build_signal_flags(0.90, 0.55, 0.40, p_btts=0.99)
    assert flags["primary"] is None
    assert flags["btts"] is False


def test_never_picks_o15_or_o35(settings, monkeypatch) -> None:
    from apps.predictions.services import signals as sig

    monkeypatch.setattr(sig, "calibrate_o25", lambda p: p)
    monkeypatch.setattr(sig, "predict_proba", lambda feats: 0.80)
    settings.SIGNAL_THRESHOLD_O25 = 0.60
    flags = build_signal_flags(
        0.99,
        0.70,
        0.97,
        p_btts=0.40,
        gbm_features={"x": 1},
    )
    assert flags["primary"] == "o25"
    assert flags["o15"] is False
    assert flags["o35"] is False


def test_league_stricter_o25(
    settings,
    tmp_path,
    monkeypatch,
):
    from apps.predictions.services import league_thresholds as lt
    from apps.predictions.services import signals as sig

    monkeypatch.setattr(sig, "calibrate_o25", lambda p: p)
    monkeypatch.setattr(sig, "predict_proba", lambda feats: feats["p"])
    settings.SIGNAL_THRESHOLD_O25 = 0.60
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
            gbm_features={"p": 0.68},
        )["primary"]
        is None
    )
    assert (
        build_signal_flags(
            0.90,
            0.72,
            0.40,
            league_api_id=39,
            gbm_features={"p": 0.72},
        )["primary"]
        == "o25"
    )
    lt.clear_threshold_cache()
