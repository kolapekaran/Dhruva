"""Lightweight confidence estimates for the current forecast artifacts.

The installed models are trained on physically grounded synthetic data.  This
module therefore reports *model confidence estimates*, not statistical
probabilities that the forecast is correct.  Confidence decays with forecast
horizon and reflects the validation error stored beside each artifact.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"


@lru_cache(maxsize=1)
def _metrics() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for name in ("load", "solar", "wind"):
        path = ARTIFACT_DIR / f"{name}_model_metrics.json"
        if path.exists():
            try:
                result[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                result[name] = {}
    return result


def _base_confidence(model_name: str) -> float:
    metrics = _metrics().get(model_name, {}).get("metrics", {})
    r2 = metrics.get("R2")
    if r2 is not None:
        # R2 is a useful bounded signal for the current synthetic validation,
        # but we deliberately cap the displayed confidence below 100%.
        return float(np.clip(0.50 + 0.45 * float(r2), 0.50, 0.95))

    mape = metrics.get("MAPE_percent")
    if mape is None:
        mape = metrics.get("MAPE_percent_daytime", metrics.get("MAPE_percent_operating"))
    if mape is not None:
        return float(np.clip(1.0 - float(mape) / 100.0, 0.20, 0.90))
    return 0.60


def confidence_score(model_name: str, hour_offset: int = 0) -> float:
    """Return a 0-1 advisory confidence estimate for one forecast point."""
    if hour_offset < 0:
        raise ValueError("hour_offset must be non-negative")
    base = _base_confidence(model_name)
    horizon_decay = max(0.55, 1.0 - 0.0025 * hour_offset)
    return float(np.clip(base * horizon_decay, 0.20, 0.95))


def prediction_interval(value: float, model_name: str, hour_offset: int = 0) -> tuple[float, float, float]:
    """Return value, lower bound, upper bound and confidence.

    The interval is an engineering uncertainty band derived from validation
    RMSE. It is not a calibrated probabilistic prediction interval.
    """
    if value < 0:
        raise ValueError("value must be non-negative")
    metrics = _metrics().get(model_name, {}).get("metrics", {})
    rmse_key = "RMSE_kW"
    rmse = float(metrics.get(rmse_key, max(1.0, value * 0.10)))
    confidence = confidence_score(model_name, hour_offset)
    # Wider intervals farther into the future and for lower-confidence models.
    multiplier = 1.0 + 0.75 * (1.0 - confidence)
    margin = rmse * multiplier
    return float(value), max(0.0, float(value - margin)), float(value + margin), confidence


def confidence_summary(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    if not rows:
        return {"average_confidence": 0.0, "minimum_confidence": 0.0}
    values = [float(r.get("confidence", 0.0)) for r in rows]
    return {
        "average_confidence": round(float(np.mean(values)), 4),
        "minimum_confidence": round(float(np.min(values)), 4),
    }
