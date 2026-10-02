"""Operational telemetry anomaly scoring for UI/API early warnings."""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import IsolationForest

_MODEL = None

def _model():
    global _MODEL
    if _MODEL is None:
        rng = np.random.default_rng(42)
        # Synthetic normal operating envelope for the reference station.
        X = np.column_stack([
            rng.normal(60, 12, 1200),   # load kW
            rng.normal(55, 22, 1200),   # renewable kW
            rng.normal(12, 8, 1200),    # diesel kW
            rng.normal(0.65, 0.12, 1200), # SOC
            rng.normal(10000, 2500, 1200), # fuel L
        ])
        _MODEL = IsolationForest(n_estimators=200, contamination=0.03, random_state=42)
        _MODEL.fit(X)
    return _MODEL


def score_telemetry(load_kw: float, renewable_kw: float, diesel_kw: float, soc_ratio: float, fuel_liters: float) -> dict:
    values = [load_kw, renewable_kw, diesel_kw, soc_ratio, fuel_liters]
    if not all(np.isfinite(values)):
        raise ValueError("telemetry values must be finite")
    X = np.array([values], dtype=float)
    model = _model()
    label = int(model.predict(X)[0])
    raw = float(model.decision_function(X)[0])
    anomaly_score = float(np.clip(0.5 - raw, 0.0, 1.0))
    return {"is_anomaly": label == -1, "anomaly_score": round(anomaly_score, 4), "severity": "warning" if label == -1 else "normal", "model": "IsolationForest(reference-envelope)"}
