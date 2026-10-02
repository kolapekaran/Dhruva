"""Report aggregation for dashboard/report screens."""
from __future__ import annotations

from datetime import datetime, timezone

from app.api.twin import twin
from app.config import STATION_CONFIG
from app.digital_twin.projection import run_projection
from app.ml.risk.risk_engine import assess_projection_risk


def build_report(hours: int = 24) -> dict:
    if not 1 <= hours <= 8760:
        raise ValueError("hours must be between 1 and 8760")
    s = twin.state
    projection = run_projection(
        s.time.timestamp,
        hours,
        base_temperature_celsius=s.weather.temperature_celsius,
        base_wind_speed_mps=s.weather.wind_speed_mps,
        initial_state=s,
    )
    risk = assess_projection_risk(projection.metrics, projection.points)
    m = projection.metrics
    return {
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "station": STATION_CONFIG.station.name,
        "horizon_hours": hours,
        "data_status": "ENGINEERING_MODEL",
        "calibration_note": "Reference Digital Twin projection; not field-calibrated telemetry unless supplied by ingestion.",
        "current": {
            "timestamp": s.time.timestamp.isoformat(),
            "temperature_celsius": s.weather.temperature_celsius,
            "wind_speed_mps": s.weather.wind_speed_mps,
            "battery_soc_percent": s.battery.soc_ratio * 100.0,
            "fuel_remaining_liters": s.fuel.fuel_remaining_liters,
            "load_kw": s.loads.requested_load_kw,
            "served_load_kw": s.loads.served_load_kw,
            "renewable_power_kw": s.system.renewable_generation_kw,
            "diesel_power_kw": s.generation.diesel_power_kw,
        },
        "forecast_summary": {
            "solar_energy_kwh": m["solar_energy_kwh"],
            "wind_energy_kwh": m["wind_energy_kwh"],
            "renewable_energy_kwh": m["renewable_energy_kwh"],
            "diesel_energy_kwh": m["diesel_energy_kwh"],
            "renewable_share_percent": m["renewable_share"] * 100.0,
            "diesel_share_percent": m["diesel_share"] * 100.0,
            "load_energy_kwh": m["load_energy_kwh"],
            "served_energy_kwh": m["served_energy_kwh"],
            "load_shed_energy_kwh": m["load_shed_energy_kwh"],
            "generator_runtime_hours": float(m.get("diesel_runtime_hours", 0.0)),
        },
        "resilience": {
            "minimum_soc_percent": m["minimum_soc_ratio"] * 100.0,
            "final_soc_percent": m["final_soc_ratio"] * 100.0,
            "fuel_consumed_liters": m["fuel_consumed_liters"],
            "final_fuel_liters": m["final_fuel_liters"],
            "autonomy_days": m["estimated_autonomy_days"],
            "critical_load_failure_steps": m["critical_load_failure_steps"],
            "blackout_risk_percent": m["blackout_risk_percent"],
            "fuel_reserve_reached": m["fuel_reserve_reached"],
        },
        "risk": risk,
        "series": projection.points,
    }
