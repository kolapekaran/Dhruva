"""Phase-3 operational intelligence for DHRUVA.

Adds a human-in-the-loop layer around the existing authoritative Digital Twin,
forecast, optimizer and resilience engines. It is deliberately advisory by
default: assessment and recommendations never mutate the station state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.api.twin import twin
from app.config import STATION_CONFIG
from app.ems.decision_engine import build_decision_trace
from app.ems.intelligence_engine import asset_health_context, dynamic_reserve_percent, fuel_autonomy
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.ml.inference.predictor import asset_failure_probabilities

_ACTION_LOG: list[dict[str, Any]] = []
_MAX_ACTION_LOG = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _forecast(hours: int) -> list[dict[str, Any]]:
    s = twin.state
    return generate_multi_day_forecast(
        s.time.timestamp,
        hours,
        s.weather.temperature_celsius,
        s.weather.wind_speed_mps,
    ).get("forecast", [])


def failure_risk_context(state) -> dict[str, Any]:
    fuel_pct = 100.0 * state.fuel.fuel_remaining_liters / max(1.0, STATION_CONFIG.fuel.tank_capacity_liters)
    probs = asset_failure_probabilities(
        state.weather.temperature_celsius,
        state.weather.wind_speed_mps,
        state.weather.solar_irradiance_w_m2,
        state.loads.requested_load_kw,
        state.battery.soc_ratio * 100.0,
        fuel_pct,
        state.battery.state_of_health_percent,
        state.system.diesel_runtime_seconds / 3600.0,
    )
    return {
        "probabilities": probs,
        "data_status": "ML_MODEL",
        "note": "Model outputs are risk indicators from the bundled reference models, not calibrated probabilities of field failure.",
    }


def maintenance_posture(state) -> dict[str, Any]:
    health = asset_health_context(state)
    risks = failure_risk_context(state)
    actions: list[str] = []
    if health["generator_health_percent"] < 90:
        actions.append("Reduce unnecessary generator runtime and review preventive maintenance readiness.")
    if health["battery_soh_percent"] < 90:
        actions.append("Avoid aggressive battery cycling and review battery maintenance readiness.")
    if health["generator_health_percent"] < 80:
        actions.append("Treat the generator as degraded for contingency planning.")
    if health["battery_soh_percent"] < 80:
        actions.append("Treat the battery as degraded for contingency planning.")
    if not actions:
        actions.append("No immediate maintenance restriction is indicated by current reference health signals.")
    return {"health": health, "failure_risk": risks, "actions": actions}


def emergency_posture(hours: int = 24) -> dict[str, Any]:
    s = twin.state
    trace = build_decision_trace(s, hours)
    health = maintenance_posture(s)
    fuel = trace.get("fuel_autonomy", {})
    reserve = float(trace.get("dynamic_reserve_percent", 20.0))
    soc = float(s.battery.soc_ratio * 100.0)
    fuel_l = float(s.fuel.fuel_remaining_liters)
    emergency_fuel = float(STATION_CONFIG.fuel.emergency_reserve_liters)
    reasons: list[str] = []
    if soc < reserve:
        reasons.append(f"Battery SOC {soc:.1f}% is below the dynamic reserve target {reserve:.1f}%.")
    if fuel_l <= emergency_fuel:
        reasons.append("Fuel is at or below the configured emergency reserve.")
    if float(health["health"]["generator_health_percent"]) < 75:
        reasons.append("Generator health is below the contingency planning threshold.")
    if float(health["health"]["battery_soh_percent"]) < 75:
        reasons.append("Battery state of health is below the contingency planning threshold.")
    if str(fuel.get("status", "ADEQUATE")) == "WATCH":
        reasons.append("Conservative fuel autonomy is below the configured seven-day watch threshold.")

    if len(reasons) >= 2 or fuel_l <= emergency_fuel:
        posture = "SURVIVAL_MODE"
        priority = "CRITICAL"
        actions = [
            "Protect critical loads and freeze discretionary load growth.",
            "Preserve battery reserve and minimize avoidable diesel runtime.",
            "Review generator readiness and resupply options immediately.",
        ]
    elif reasons:
        posture = "CONTINGENCY_READY"
        priority = "WATCH"
        actions = [
            "Preserve reserve margins and monitor the next forecast window.",
            "Prepare flexible-load shifting and resupply contingencies.",
        ]
    else:
        posture = "NORMAL"
        priority = "NORMAL"
        actions = ["Maintain the current safety-constrained dispatch and monitor forecast changes."]

    return {
        "posture": posture,
        "priority": priority,
        "triggered": bool(reasons),
        "reasons": reasons,
        "recommended_actions": actions,
        "dynamic_reserve_percent": round(reserve, 2),
        "battery_soc_percent": round(soc, 2),
        "fuel_remaining_liters": round(fuel_l, 2),
        "fuel_autonomy": fuel,
        "maintenance": health,
        "data_status": "ENGINEERING_MODEL",
        "advisory_only": True,
        "station_state_mutated": False,
    }


def resupply_decision(hours: int = 168, lead_time_hours: int = 72) -> dict[str, Any]:
    s = twin.state
    forecast = _forecast(max(24, min(168, hours)))
    autonomy = fuel_autonomy(s, forecast)
    reserve = float(STATION_CONFIG.fuel.emergency_reserve_liters)
    capacity = float(STATION_CONFIG.fuel.tank_capacity_liters)
    current = float(s.fuel.fuel_remaining_liters)

    # Use the conservative P10 fuel rate already computed by the intelligence
    # layer, rather than inventing a new consumption model here.
    safe_days = float(autonomy.get("safe_days", 0.0))
    conservative_rate_lpd = max(0.0, (current - reserve) / max(1e-6, safe_days)) if safe_days > 0 else 0.0
    lead_burn = conservative_rate_lpd * (lead_time_hours / 24.0)
    projected_at_lead = max(0.0, current - lead_burn)
    target_after_delivery = min(capacity, reserve + lead_burn * 1.20)
    required_quantity = max(0.0, target_after_delivery - projected_at_lead)

    if projected_at_lead <= reserve:
        action = "RESUPPLY_NOW"
        priority = "CRITICAL"
    elif safe_days < 7:
        action = "SCHEDULE_RESUPPLY"
        priority = "HIGH"
    elif safe_days < 14:
        action = "PREPARE_RESUPPLY"
        priority = "WATCH"
    else:
        action = "NO_IMMEDIATE_RESUPPLY"
        priority = "NORMAL"

    return {
        "decision_id": f"SUP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}",
        "action": action,
        "priority": priority,
        "current_fuel_liters": round(current, 2),
        "emergency_reserve_liters": round(reserve, 2),
        "safe_autonomy_days": round(safe_days, 2),
        "lead_time_hours": lead_time_hours,
        "projected_fuel_at_lead_time_liters": round(projected_at_lead, 2),
        "target_stock_after_delivery_liters": round(target_after_delivery, 2),
        "recommended_quantity_liters": round(required_quantity, 2),
        "reason": f"Conservative fuel planning estimates {safe_days:.1f} safe days after preserving the {reserve:.0f} L emergency reserve.",
        "data_status": "ENGINEERING_MODEL",
        "advisory_only": True,
        "station_state_mutated": False,
    }


def record_operator_action(decision_id: str, action: str, operator: str = "OPERATOR", notes: str = "") -> dict[str, Any]:
    allowed = {"APPROVE", "REJECT", "DEFER", "ACKNOWLEDGE"}
    normalized = action.upper().strip()
    if normalized not in allowed:
        raise ValueError(f"Unsupported operator action: {action}")
    entry = {
        "action_id": f"ACT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}",
        "decision_id": decision_id,
        "action": normalized,
        "operator": operator.strip() or "OPERATOR",
        "notes": notes.strip(),
        "timestamp": _now(),
        "data_status": "OPERATOR_AUDIT",
    }
    _ACTION_LOG.append(entry)
    if len(_ACTION_LOG) > _MAX_ACTION_LOG:
        del _ACTION_LOG[:-_MAX_ACTION_LOG]
    return entry


def operator_action_log(limit: int = 50) -> list[dict[str, Any]]:
    return list(reversed(_ACTION_LOG[-max(1, min(500, limit)):]))
