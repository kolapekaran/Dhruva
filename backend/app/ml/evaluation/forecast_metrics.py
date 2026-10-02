"""Forecast evaluation helpers for aligned prediction/actual series."""
from __future__ import annotations

import math


def _validate(actual: list[float], predicted: list[float]) -> None:
    if not actual or not predicted:
        raise ValueError("actual and predicted must not be empty")
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")


def evaluate_forecast(actual: list[float], predicted: list[float]) -> dict:
    """Return MAE, RMSE and MAPE without external dependencies."""
    _validate(actual, predicted)
    errors = [p - a for a, p in zip(actual, predicted)]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    non_zero = [(a, p) for a, p in zip(actual, predicted) if abs(a) > 1e-9]
    mape = (
        sum(abs((p - a) / a) for a, p in non_zero) / len(non_zero) * 100.0
        if non_zero else 0.0
    )
    return {"mae": mae, "rmse": rmse, "mape_percent": mape}
