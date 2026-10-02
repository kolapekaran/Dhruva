"""Transparent station resilience and early-warning risk scoring.

Scores are engineering indicators derived from the Digital Twin projection,
not calibrated real-world probabilities. This distinction is intentionally
kept in the API so synthetic/reference data is never presented as telemetry.
"""
from __future__ import annotations

from app.config import STATION_CONFIG


def _clip(v: float) -> float:
    return max(0.0, min(100.0, float(v)))


def _point_risk(point: dict, initial_fuel: float, reserve_fuel: float) -> dict:
    soc = float(point.get("battery_soc_ratio", 1.0))
    if soc > 1.0:
        soc /= 100.0
    fuel = float(point.get("fuel_remaining_liters", initial_fuel))
    load = max(0.0, float(point.get("load_kw", 0.0)))
    served = max(0.0, float(point.get("served_load_kw", load)))
    critical_required = float(STATION_CONFIG.loads.critical_load_kw)
    critical_served = float(point.get("critical_load_kw", critical_required))
    shed = max(0.0, float(point.get("shed_load_kw", max(0.0, load-served))))
    confidence = float(point.get("confidence", 1.0))
    if confidence > 1.0:
        confidence /= 100.0

    critical = 100.0 if critical_served + 1e-6 < critical_required else 0.0
    soc_risk = _clip((0.25 - soc) / 0.25 * 100.0)
    fuel_risk = _clip((reserve_fuel - fuel) / max(1.0, reserve_fuel) * 100.0)
    service = _clip((1.0 - served / max(1.0, load)) * 100.0 + min(40.0, shed / 10.0))
    uncertainty = _clip((0.75 - confidence) / 0.75 * 40.0)
    weather = _clip(
        (100.0 if float(point.get("temperature_celsius", 0.0)) <= -35 else 0.0)
        + (100.0 if float(point.get("wind_speed_mps", 0.0)) >= 20 else 0.0)
    ) / 2.0
    overall = _clip(0.40*critical + 0.20*soc_risk + 0.20*fuel_risk + 0.10*service + 0.05*uncertainty + 0.05*weather)
    return {
        "overall": round(overall, 2),
        "critical": round(critical, 2),
        "battery": round(soc_risk, 2),
        "fuel": round(fuel_risk, 2),
        "service": round(service, 2),
        "uncertainty": round(uncertainty, 2),
        "weather": round(weather, 2),
    }


def assess_projection_risk(metrics: dict, points: list[dict] | None = None) -> dict:
    points = points or []
    min_soc = float(metrics.get("minimum_soc_ratio", metrics.get("minimum_soc_percent", 100.0) / 100.0))
    if min_soc > 1.0:
        min_soc /= 100.0
    final_fuel = float(metrics.get("final_fuel_liters", 0.0))
    reserve = float(metrics.get("emergency_reserve_liters", STATION_CONFIG.fuel.emergency_reserve_liters))
    service_level = float(metrics.get("service_level_percent", 100.0))
    critical_failures = int(metrics.get("critical_load_failure_steps", 0))
    load_shed = float(metrics.get("load_shed_energy_kwh", 0.0))
    confidence = float(metrics.get("forecast_confidence", {}).get("average_confidence", 0.75))

    critical = 100.0 if critical_failures else 0.0
    soc = _clip((0.25 - min_soc) / 0.25 * 100.0)
    fuel = _clip((reserve - final_fuel) / max(1.0, reserve) * 100.0)
    service = _clip((100.0 - service_level) * 2.0 + min(40.0, load_shed / 10.0))
    uncertainty = _clip((0.75 - confidence) / 0.75 * 40.0)

    extreme_weather = 0.0
    if points:
        cold = sum(float(p.get("temperature_celsius", 0)) <= -35 for p in points)
        high_wind = sum(float(p.get("wind_speed_mps", 0)) >= 20 for p in points)
        extreme_weather = _clip((cold + high_wind) / max(1, len(points)) * 100.0)

    overall = _clip(0.40*critical + 0.20*soc + 0.20*fuel + 0.10*service + 0.05*uncertainty + 0.05*extreme_weather)
    if overall < 20:
        level = "LOW"
    elif overall < 40:
        level = "MEDIUM"
    elif overall < 70:
        level = "HIGH"
    else:
        level = "CRITICAL"

    risk_series = []
    initial_fuel = float(metrics.get("initial_fuel_liters", final_fuel))
    for point in points:
        point_risk = _point_risk(point, initial_fuel, reserve)
        risk_series.append({
            "hour_offset": int(point.get("hour_offset", len(risk_series))),
            **point_risk,
        })

    return {
        "overall_risk_percent": round(overall, 2),
        "risk_level": level,
        "blackout_risk_percent": round(max(critical, overall), 2),
        "components": {
            "critical_load_risk_percent": round(critical, 2),
            "battery_soc_risk_percent": round(soc, 2),
            "fuel_reserve_risk_percent": round(fuel, 2),
            "service_level_risk_percent": round(service, 2),
            "forecast_uncertainty_risk_percent": round(uncertainty, 2),
            "extreme_weather_risk_percent": round(extreme_weather, 2),
        },
        "risk_series": risk_series,
        "is_advisory": True,
        "calibration_note": "Engineering risk indicator based on the synthetic/reference Digital Twin projection; not a field-calibrated probability.",
    }
