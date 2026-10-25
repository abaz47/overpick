"""Tests for per-league tip floors."""

from apps.predictions.services import league_thresholds as lt


def test_save_keeps_max_with_previous(tmp_path, monkeypatch) -> None:
    path = tmp_path / "league_thresholds.json"
    path.write_text(
        '{"2": {"o25": 0.62}, "39": {"o25": 0.70}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(lt, "_DATA_PATH", path)
    lt.clear_threshold_cache()
    lt.save_league_thresholds(
        {
            "39": {"o25": 0.65},
            "140": {"o25": 0.63},
        },
    )
    data = lt._load_file()
    assert data["2"]["o25"] == 0.62
    assert data["39"]["o25"] == 0.70
    assert data["140"]["o25"] == 0.63
