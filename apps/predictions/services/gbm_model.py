"""Train / load / predict O2.5 LightGBM (hybrid tip)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.predictions.services.gbm_features import (
    FEATURE_NAMES,
    feature_vector,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_MODEL_PATH = _DATA_DIR / "gbm_o25.txt"
_META_PATH = _DATA_DIR / "gbm_o25_meta.json"


def model_path() -> Path:
    return _MODEL_PATH


def meta_path() -> Path:
    return _META_PATH


def clear_gbm_cache() -> None:
    """Drop loaded booster after retrain."""
    _load_booster.cache_clear()


def train_and_save(
    x: list[list[float]],
    y: list[int],
    *,
    path: Path | None = None,
) -> Path:
    """Fit LightGBM on full history and persist."""
    import lightgbm as lgb

    if len(x) < 500:
        raise ValueError(f"Need ≥500 rows to train GBM, got {len(x)}")
    cat_idx = FEATURE_NAMES.index("league_api_id")
    model = lgb.LGBMClassifier(
        n_estimators=250,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=40,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        random_state=42,
        verbosity=-1,
        n_jobs=2,
    )
    model.fit(x, y, categorical_feature=[cat_idx])
    target = path or _MODEL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(target))
    meta = {
        "features": list(FEATURE_NAMES),
        "n_train": len(x),
        "backend": "lightgbm",
        "params": {
            "n_estimators": 250,
            "learning_rate": 0.05,
            "num_leaves": 31,
        },
    }
    _META_PATH.write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )
    clear_gbm_cache()
    return target


@lru_cache(maxsize=1)
def _load_booster() -> Any | None:
    if not _MODEL_PATH.exists():
        return None
    try:
        import lightgbm as lgb

        return lgb.Booster(model_file=str(_MODEL_PATH))
    except Exception as exc:
        logger.warning("Failed to load GBM model: %s", exc)
        return None


def predict_proba(feats: dict[str, float]) -> float | None:
    """P(O2.5) from saved GBM; None if model missing."""
    booster = _load_booster()
    if booster is None:
        return None
    vec = feature_vector(feats)
    # LightGBM Booster.predict returns P(class=1) for binary.
    raw = booster.predict([vec])
    return float(raw[0])


def is_model_ready() -> bool:
    """Whether a usable booster file is on disk."""
    return _load_booster() is not None


def train_production_gbm(*, limit: int | None = None) -> Path:
    """Collect walk-forward ML rows and fit production booster."""
    from apps.predictions.services.gbm_prototype import (
        collect_ml_rows,
    )

    rows = collect_ml_rows(limit=limit)
    x = [[float(r.features[name]) for name in FEATURE_NAMES] for r in rows]
    y = [1 if r.hit_25 else 0 for r in rows]
    return train_and_save(x, y)


def hybrid_tip_prob(feats: dict[str, float], p_pois_25: float) -> float:
    """Production tip probability from features + raw Poisson P."""
    from apps.predictions.services.gbm_features import (
        hybrid_probability,
    )
    from apps.predictions.services.prob_calibration import (
        calibrate_o25,
    )

    p_cal = calibrate_o25(p_pois_25)
    p_gbm = predict_proba(feats)
    if p_gbm is None:
        return p_cal
    return hybrid_probability(p_cal, p_gbm)
