"""Calibration and walk-forward validation primitives for DHRUVA.

These utilities are intentionally model-agnostic. They do not manufacture field
accuracy; they require separate calibration and evaluation observations so that
reported interval coverage is out-of-sample.
"""
from __future__ import annotations

from math import sqrt
from statistics import mean


def _validate_pair(actual: list[float], predicted: list[float], name: str) -> None:
    if not actual or not predicted:
        raise ValueError(f"{name} arrays must not be empty")
    if len(actual) != len(predicted):
        raise ValueError(f"{name} actual/predicted lengths must match")


def absolute_residuals(actual: list[float], predicted: list[float]) -> list[float]:
    _validate_pair(actual, predicted, "calibration")
    return [abs(float(a) - float(p)) for a, p in zip(actual, predicted)]


def conformal_radius(calibration_actual: list[float], calibration_predicted: list[float], alpha: float = 0.10) -> float:
    """Finite-sample split-conformal absolute-residual radius.

    The returned radius is computed only from the calibration split. The caller
    must evaluate coverage on a separate holdout split.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    residuals = sorted(absolute_residuals(calibration_actual, calibration_predicted))
    # Conservative conformal quantile index: ceil((n+1)*(1-alpha))-1.
    rank = int(__import__("math").ceil((len(residuals) + 1) * (1.0 - alpha))) - 1
    rank = min(max(rank, 0), len(residuals) - 1)
    return float(residuals[rank])


def evaluate_interval_coverage(
    actual: list[float], predicted: list[float], radius: float
) -> dict:
    _validate_pair(actual, predicted, "evaluation")
    if radius < 0:
        raise ValueError("radius must be non-negative")
    covered = [abs(float(a) - float(p)) <= radius + 1e-12 for a, p in zip(actual, predicted)]
    return {
        "sample_count": len(actual),
        "coverage_percent": round(100.0 * sum(covered) / len(covered), 3),
        "covered_count": sum(covered),
        "missed_count": len(covered) - sum(covered),
        "radius": round(radius, 6),
    }


def split_conformal_evaluation(
    calibration_actual: list[float],
    calibration_predicted: list[float],
    evaluation_actual: list[float],
    evaluation_predicted: list[float],
    alpha: float = 0.10,
) -> dict:
    radius = conformal_radius(calibration_actual, calibration_predicted, alpha)
    coverage = evaluate_interval_coverage(evaluation_actual, evaluation_predicted, radius)
    return {
        "method": "split_conformal_absolute_residual",
        "alpha": alpha,
        "target_coverage_percent": round(100.0 * (1.0 - alpha), 3),
        "calibration_samples": len(calibration_actual),
        "evaluation_samples": len(evaluation_actual),
        "radius": round(radius, 6),
        "evaluation": coverage,
        "field_validated": False,
        "note": "Coverage is empirical on the supplied evaluation split; it is not evidence of field performance at Maitri.",
    }


def compare_forecasters(
    actual: list[float], candidates: dict[str, list[float]]
) -> dict:
    """Compare candidate predictions on the same held-out actual series."""
    if not actual:
        raise ValueError("actual must not be empty")
    results = []
    for name, predicted in candidates.items():
        _validate_pair(actual, predicted, name)
        errors = [float(p) - float(a) for a, p in zip(actual, predicted)]
        mae = mean(abs(e) for e in errors)
        rmse = sqrt(mean(e * e for e in errors))
        results.append({"model": name, "mae": round(mae, 6), "rmse": round(rmse, 6)})
    ranked = sorted(results, key=lambda x: (x["mae"], x["rmse"], x["model"]))
    return {
        "models": results,
        "ranking_basis": "held_out_mae_then_rmse",
        "recommended_model": ranked[0]["model"] if ranked else None,
        "promotion_requires_operator_review": True,
        "field_validated": False,
    }
