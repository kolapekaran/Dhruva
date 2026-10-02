"""Phase-2 DHRUVA intelligence helpers.

This module adds uncertainty-aware planning, dynamic reserve calculation,
asset-aware penalties, and fuel-autonomy analysis without changing the
Digital Twin source-of-truth model.
"""
from __future__ import annotations

from typing import Any

from app.config import STATION_CONFIG


def uncertainty_summary(forecast: list[dict]) -> dict[str, Any]:
    if not forecast:
        return {"average_confidence_percent": 0.0, "minimum_confidence_percent": 0.0, "bands": {}}
    def avg(key: str) -> float:
        vals = [float(r.get(key, 0.0)) for r in forecast]
        return sum(vals) / max(1, len(vals))
    return {
        "average_confidence_percent": round(100.0 * avg("confidence"), 2),
        "minimum_confidence_percent": round(100.0 * min(float(r.get("confidence", 0.0)) for r in forecast), 2),
        "bands": {
            "load_kw": {"p10": round(avg("load_lower_kw"), 2), "p50": round(avg("load_kw"), 2), "p90": round(avg("load_upper_kw"), 2)},
            "solar_kw": {"p10": round(avg("solar_lower_kw"), 2), "p50": round(avg("solar_kw"), 2), "p90": round(avg("solar_upper_kw"), 2)},
            "wind_kw": {"p10": round(avg("wind_lower_kw"), 2), "p50": round(avg("wind_kw"), 2), "p90": round(avg("wind_upper_kw"), 2)},
        },
        "interpretation": "P10/P50/P90 are engineering uncertainty bands derived from model validation error; they are not calibrated probabilistic guarantees.",
    }


def robust_forecast(forecast: list[dict]) -> list[dict]:
    """Create a conservative planning trajectory: high load + low renewables."""
    robust: list[dict] = []
    for row in forecast:
        item = dict(row)
        item["load_kw"] = float(row.get("load_upper_kw", row.get("load_kw", 0.0)))
        item["solar_kw"] = float(row.get("solar_lower_kw", row.get("solar_kw", 0.0)))
        item["wind_kw"] = float(row.get("wind_lower_kw", row.get("wind_kw", 0.0)))
        item["renewable_kw"] = item["solar_kw"] + item["wind_kw"]
        item["planning_case"] = "P90_LOAD_P10_RENEWABLE"
        return_item = item
        robust.append(return_item)
    return robust


def dynamic_reserve_percent(state, forecast: list[dict]) -> float:
    if not forecast:
        return 25.0
    window = forecast[:24]
    confidence = min(float(r.get("confidence", 1.0)) for r in window)
    temperature = float(state.weather.temperature_celsius)
    snowfall = max(float(r.get("snowfall_rate", 0.0)) for r in window)
    failure_risk = max(float(r.get("failure_probability", 0.0)) for r in window)
    battery_soh = float(getattr(state.battery, "state_of_health_percent", 100.0))
    generator_health = float(getattr(state.generation, "generator_health_percent", 100.0))

    weather_risk = min(7.0, max(0.0, (-temperature - 15.0) / 8.0)) + min(4.0, snowfall)
    uncertainty_risk = (1.0 - max(0.0, min(1.0, confidence))) * 16.0
    asset_risk = max(0.0, (85.0 - min(battery_soh, generator_health)) / 20.0)
    failure_risk_points = min(6.0, failure_risk * 12.0)
    fuel = float(state.fuel.fuel_remaining_liters)
    fuel_ratio = fuel / max(1.0, STATION_CONFIG.fuel.tank_capacity_liters)
    fuel_risk = 4.0 if fuel_ratio < 0.30 else 2.0 if fuel_ratio < 0.50 else 0.0
    reserve = 20.0 + weather_risk + uncertainty_risk + asset_risk + failure_risk_points + fuel_risk
    return round(max(20.0, min(35.0, reserve)), 2)


def fuel_autonomy(state, forecast: list[dict]) -> dict[str, float | str]:
    fuel = float(state.fuel.fuel_remaining_liters)
    if not forecast:
        return {"current_fuel_liters": round(fuel, 2), "p50_days": 0.0, "p10_days": 0.0, "safe_days": 0.0, "status": "UNKNOWN"}

    def daily_liters(load_key: str, solar_key: str, wind_key: str) -> float:
        total = 0.0
        for row in forecast[:24]:
            load = max(0.0, float(row.get(load_key, row.get("load_kw", 0.0))))
            renewable = max(0.0, float(row.get(solar_key, row.get("solar_kw", 0.0))) + float(row.get(wind_key, row.get("wind_kw", 0.0))))
            diesel = max(0.0, min(STATION_CONFIG.diesel.rated_power_kw, load - renewable))
            if 0 < diesel < STATION_CONFIG.diesel.minimum_power_kw:
                diesel = STATION_CONFIG.diesel.minimum_power_kw
            total += STATION_CONFIG.diesel.fuel_intercept_lph + STATION_CONFIG.diesel.fuel_slope_l_per_kwh * diesel if diesel > 0 else 0.0
        return total

    p50_rate = daily_liters("load_kw", "solar_kw", "wind_kw")
    conservative_rate = daily_liters("load_upper_kw", "solar_lower_kw", "wind_lower_kw")
    safe_fuel = max(0.0, fuel - STATION_CONFIG.fuel.emergency_reserve_liters)
    p50_days = safe_fuel / max(1e-6, p50_rate)
    p10_days = safe_fuel / max(1e-6, conservative_rate)
    status = "WATCH" if p10_days < 7 else "ADEQUATE"
    return {
        "current_fuel_liters": round(fuel, 2),
        "p50_days": round(p50_days, 2),
        "p10_days": round(p10_days, 2),
        "safe_days": round(p10_days, 2),
        "status": status,
    }


def asset_health_context(state) -> dict[str, Any]:
    battery_soh = float(getattr(state.battery, "state_of_health_percent", getattr(state.battery, "health_percent", 100.0)))
    generator_health = float(getattr(state.generation, "generator_health_percent", 100.0))
    return {
        "battery_soh_percent": round(battery_soh, 2),
        "generator_health_percent": round(generator_health, 2),
        "battery_condition": "DEGRADED" if battery_soh < 85 else "NORMAL",
        "generator_condition": "DEGRADED" if generator_health < 85 else "NORMAL",
        "dispatch_penalty_active": battery_soh < 90 or generator_health < 90,
    }
