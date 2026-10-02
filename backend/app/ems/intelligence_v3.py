"""DHRUVA Intelligence Engine V3.

Adds deeper ML/decision-support primitives without taking control of the live
Digital Twin: operating-regime detection, uncertainty envelopes, asset RUL
estimates, model-drift checks, scenario generation, dependency propagation and
counterfactual planning.

All outputs are advisory engineering estimates unless explicitly backed by
measured/calibrated data.
"""
from __future__ import annotations

from statistics import mean
from typing import Any
import math

from app.config import STATION_CONFIG
from app.ems.intelligence_engine import asset_health_context, uncertainty_summary


def polar_regime(state) -> dict[str, Any]:
    t = float(state.weather.temperature_celsius)
    wind = float(state.weather.wind_speed_mps)
    snow = float(state.weather.snowfall_rate)
    solar = float(state.weather.solar_irradiance_w_m2)
    load = float(state.loads.requested_load_kw)
    renewable = float(state.generation.solar_power_kw + state.generation.wind_power_kw)

    if t <= -40:
        regime = "EXTREME_COLD"
        reason = "temperature at or below -40 C"
    elif snow >= 4.0 and wind >= 12.0:
        regime = "BLIZZARD"
        reason = "high snowfall and high wind"
    elif wind >= 20.0:
        regime = "HIGH_WIND"
        reason = "high wind conditions"
    elif solar <= 1.0 and state.time.timestamp.month in (5, 6, 7, 8):
        regime = "POLAR_NIGHT"
        reason = "low solar availability during winter months"
    elif renewable < 0.35 * max(load, 1.0):
        regime = "RENEWABLE_COLLAPSE"
        reason = "renewable generation below 35% of load"
    elif renewable > 1.10 * max(load, 1.0):
        regime = "RENEWABLE_SURPLUS"
        reason = "renewable generation exceeds load"
    else:
        regime = "NORMAL"
        reason = "no dominant stress regime detected"
    severity = {
        "NORMAL": "LOW", "RENEWABLE_SURPLUS": "LOW", "HIGH_WIND": "MODERATE",
        "POLAR_NIGHT": "MODERATE", "RENEWABLE_COLLAPSE": "HIGH",
        "EXTREME_COLD": "HIGH", "BLIZZARD": "HIGH",
    }[regime]
    return {"regime": regime, "severity": severity, "reason": reason,
            "features": {"temperature_celsius": t, "wind_speed_mps": wind,
                         "snowfall_rate": snow, "solar_irradiance_w_m2": solar,
                         "load_kw": load, "renewable_kw": renewable},
            "model": "rule-based-polar-regime-classifier"}


def empirical_prediction_intervals(forecast: list[dict]) -> dict[str, Any]:
    """Return transparent reference intervals using stored validation errors.

    These are deliberately *not* labelled calibrated conformal intervals because
    the project archive does not contain a held-out residual calibration set.
    """
    metrics = {
        "load_kw": (1.6589, 2.33),
        "solar_kw": (6.6368, 2.33),
        "wind_kw": (2.7462, 2.33),
    }
    bands = {}
    for key, (rmse, z) in metrics.items():
        vals = [max(0.0, float(row.get(key, 0.0))) for row in forecast]
        center = mean(vals) if vals else 0.0
        radius = rmse * z
        bands[key] = {"center_mean": round(center, 3),
                      "lower_reference": round(max(0.0, center - radius), 3),
                      "upper_reference": round(center + radius, 3),
                      "radius_kw": round(radius, 3)}
    return {
        "method": "validation-error-envelope",
        "calibration_status": "NOT_CALIBRATED",
        "coverage_claim": False,
        "bands": bands,
        "note": "Reference uncertainty envelope derived from stored synthetic/reference RMSE; a held-out residual calibration set is required before claiming calibrated coverage.",
    }


def battery_rul(state) -> dict[str, Any]:
    soh = max(0.0, min(100.0, float(getattr(state.battery, "state_of_health_percent", 100.0))))
    cycles = max(0.0, float(getattr(state.battery, "cycle_count", 0.0)))
    # Engineering screening estimate, not a manufacturer warranty/RUL claim.
    assumed_end_of_life = 80.0
    remaining_soh = max(0.0, soh - assumed_end_of_life)
    observed_fade = max(0.01, (100.0 - soh) / max(cycles, 1.0))
    estimated_cycles = remaining_soh / observed_fade if soh < 99.99 else 5000.0
    return {
        "soh_percent": round(soh, 2),
        "cycle_count": round(cycles, 2),
        "estimated_remaining_equivalent_cycles": round(max(0.0, estimated_cycles), 1),
        "screening_threshold_soh_percent": assumed_end_of_life,
        "status": "DEGRADED" if soh < 85 else "NORMAL",
        "method": "engineering-degradation-screening",
        "field_validated": False,
    }


def model_drift_check(actual: list[float], predicted: list[float], threshold_ratio: float = 1.5) -> dict[str, Any]:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted must be non-empty arrays of equal length")
    errors = [abs(float(a) - float(p)) for a, p in zip(actual, predicted)]
    mae = mean(errors)
    baseline = max(1e-9, mean([abs(float(p)) for p in predicted]) * 0.10)
    ratio = mae / baseline
    return {"sample_count": len(errors), "mae": round(mae, 4),
            "baseline_error_reference": round(baseline, 4), "drift_ratio": round(ratio, 3),
            "status": "DRIFT" if ratio >= threshold_ratio else "STABLE",
            "threshold_ratio": threshold_ratio,
            "method": "rolling-error-screen",
            "note": "Screening signal only; production drift detection should use time-windowed reference residuals."}


def generate_stress_scenarios(forecast: list[dict]) -> list[dict[str, Any]]:
    scenarios = [
        ("BASELINE", 0, 0, 0),
        ("LOW_WIND", 0, -60, 0),
        ("SOLAR_LOSS", 0, 0, -100),
        ("HIGH_LOAD", 25, 0, 0),
        ("BLIZZARD", 20, -70, -80),
        ("EXTREME_COLD", 30, -30, -50),
        ("RENEWABLE_COLLAPSE", 20, -80, -90),
        ("GENERATOR_FAILURE", 0, 0, 0),
        ("COMBINED_ASSET_STRESS", 30, -80, -90),
    ]
    out = []
    for name, load_pct, wind_pct, solar_pct in scenarios:
        rows = []
        for row in forecast:
            item = dict(row)
            item["load_kw"] = max(0.0, float(row.get("load_kw", 0.0)) * (1 + load_pct / 100))
            item["wind_kw"] = max(0.0, float(row.get("wind_kw", 0.0)) * (1 + wind_pct / 100))
            item["solar_kw"] = max(0.0, float(row.get("solar_kw", 0.0)) * (1 + solar_pct / 100))
            item["renewable_kw"] = item["wind_kw"] + item["solar_kw"]
            rows.append(item)
        out.append({"scenario": name, "assumptions": {
            "load_change_percent": load_pct, "wind_change_percent": wind_pct,
            "solar_change_percent": solar_pct}, "forecast": rows})
    return out


def dependency_graph(state) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "WIND", "type": "renewable"}, {"id": "SOLAR", "type": "renewable"},
            {"id": "BATTERY", "type": "storage"}, {"id": "DG", "type": "dispatchable"},
            {"id": "FUEL", "type": "resource"}, {"id": "BUS", "type": "electrical_bus"},
            {"id": "CRITICAL_LOAD", "type": "load"}, {"id": "FLEXIBLE_LOAD", "type": "load"},
        ],
        "edges": [
            ["WIND", "BUS"], ["SOLAR", "BUS"], ["BATTERY", "BUS"], ["DG", "BUS"],
            ["FUEL", "DG"], ["BUS", "CRITICAL_LOAD"], ["BUS", "FLEXIBLE_LOAD"],
        ],
        "failure_propagation": {
            "DG": ["FUEL", "BUS", "CRITICAL_LOAD"],
            "BATTERY": ["BUS", "CRITICAL_LOAD"],
            "WIND": ["BUS", "BATTERY", "DG", "FUEL"],
            "SOLAR": ["BUS", "BATTERY", "DG", "FUEL"],
        },
        "state_source": "Digital Twin",
    }


def counterfactual(state, forecast: list[dict], scenario: str) -> dict[str, Any]:
    scenarios = {s["scenario"]: s for s in generate_stress_scenarios(forecast)}
    selected = scenarios.get(scenario)
    if selected is None:
        raise ValueError(f"unknown scenario: {scenario}")
    total_load = sum(float(r.get("load_kw", 0.0)) for r in selected["forecast"])
    renewable = sum(float(r.get("renewable_kw", 0.0)) for r in selected["forecast"])
    residual = max(0.0, total_load - renewable)
    if scenario == "GENERATOR_FAILURE":
        # Screening case: dispatchable generation is unavailable, so only the
        # renewable trajectory is credited. The full simulator remains the
        # authoritative calculation for load-service consequences.
        residual = max(0.0, total_load - renewable)
    generator_available = scenario != "GENERATOR_FAILURE"
    diesel_hours = math.ceil(residual / max(1.0, STATION_CONFIG.diesel.rated_power_kw)) if generator_available else 0
    fuel_est = diesel_hours * STATION_CONFIG.diesel.fuel_intercept_lph if generator_available else 0.0
    return {
        "scenario": scenario,
        "total_load_kwh_reference": round(total_load, 2),
        "renewable_kwh_reference": round(renewable, 2),
        "residual_energy_kwh_reference": round(residual, 2),
        "estimated_diesel_runtime_hours": diesel_hours,
        "estimated_additional_fuel_liters": round(fuel_est, 2),
        "estimated_unserved_energy_kwh_reference": round(residual if not generator_available else 0.0, 2),
        "generator_available": generator_available,
        "decision_use": "advisory_counterfactual",
        "station_state_mutated": False,
        "note": "Screening estimate; run the full simulator/optimizer before operational approval.",
    }
