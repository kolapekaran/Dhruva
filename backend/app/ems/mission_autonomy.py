"""DHRUVA mission-autonomy orchestration layer.

This module does not control equipment. It composes the existing forecast,
mission-assurance, decision, health and counterfactual engines into one
operator-supervised mission plan. All outputs are advisory and read-only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.api.mission_survival import SurvivalRequest, _simulate
from app.api.twin import twin
from app.config import STATION_CONFIG
from app.ems.decision_engine import build_decision_trace
from app.ems.intelligence_engine import asset_health_context, fuel_autonomy
from app.ems.intelligence_v3 import counterfactual
from app.ml.forecasting.multi_day import generate_multi_day_forecast


def _forecast(hours: int) -> list[dict[str, Any]]:
    s = twin.state
    return generate_multi_day_forecast(
        s.time.timestamp, hours, s.weather.temperature_celsius, s.weather.wind_speed_mps
    ).get("forecast", [])


def _assurance(hours: int = 168, members: int = 120) -> dict[str, Any]:
    s = twin.state
    scenarios = [
        ("BASELINE", dict(wind_factor=1.0, solar_factor=1.0, load_factor=1.0, generator_available=True, resupply_delay_hours=0)),
        ("LOW_WIND", dict(wind_factor=0.45, solar_factor=1.0, load_factor=1.0, generator_available=True, resupply_delay_hours=24)),
        ("SOLAR_LOSS", dict(wind_factor=1.0, solar_factor=0.05, load_factor=1.0, generator_available=True, resupply_delay_hours=24)),
        ("EXTREME_COLD_LOAD", dict(wind_factor=0.75, solar_factor=0.65, load_factor=1.25, generator_available=True, resupply_delay_hours=48)),
        ("BLIZZARD", dict(wind_factor=0.35, solar_factor=0.10, load_factor=1.20, generator_available=True, resupply_delay_hours=48)),
        ("GENERATOR_FAILURE", dict(wind_factor=0.70, solar_factor=0.35, load_factor=1.15, generator_available=False, resupply_delay_hours=72)),
        ("COMBINED_ASSET_STRESS", dict(wind_factor=0.30, solar_factor=0.05, load_factor=1.30, generator_available=False, resupply_delay_hours=72)),
    ]
    rows = []
    for name, kwargs in scenarios:
        req = SurvivalRequest(horizon_hours=hours, ensemble_members=members, resupply_quantity_liters=5000.0, **kwargs)
        results = [_simulate(i, hours, s, req) for i in range(members)]
        survival = sorted([hours if r[0] is None else max(0, r[0] - 1) for r in results])
        p10 = survival[max(0, int(0.10 * len(survival)) - 1)]
        p50 = survival[max(0, int(0.50 * len(survival)) - 1)]
        rows.append({
            "scenario": name,
            "survival_percent": round(100 * sum(r[0] is None for r in results) / len(results), 1),
            "p10_survival_hours": int(p10),
            "p50_survival_hours": int(p50),
            "minimum_fuel_liters": round(min(r[2] for r in results), 1),
            "thermal_unserved_kwh": round(sum(r[5] for r in results) / len(results), 2),
            "generator_available": kwargs["generator_available"],
            "resupply_delay_hours": kwargs["resupply_delay_hours"],
        })
    worst = min(rows, key=lambda r: (r["survival_percent"], r["p10_survival_hours"], -r["minimum_fuel_liters"]))
    return {"rows": rows, "worst": worst, "members": members, "horizon_hours": hours}


def _posture(assurance: dict[str, Any], trace: dict[str, Any], health: dict[str, Any], fuel: dict[str, Any]) -> tuple[str, list[str]]:
    worst = assurance["worst"]
    reserve = float(trace.get("dynamic_reserve_percent", 20.0))
    soc = float(twin.state.battery.soc_ratio * 100)
    fuel_l = float(twin.state.fuel.fuel_remaining_liters)
    reasons: list[str] = []
    if worst["p10_survival_hours"] < 72:
        reasons.append(f"7-day stress envelope has a P10 survival horizon of {worst['p10_survival_hours']} h in {worst['scenario']}.")
    if soc < reserve:
        reasons.append(f"Battery SOC {soc:.1f}% is below the dynamic reserve target {reserve:.1f}%.")
    if fuel.get("status") in {"WATCH", "CRITICAL"}:
        reasons.append(f"Fuel autonomy status is {fuel.get('status')} under conservative planning.")
    if health.get("generator_health_percent", 100) < 80:
        reasons.append("Generator health signal is below the contingency threshold.")
    if health.get("battery_soh_percent", 100) < 80:
        reasons.append("Battery SOH signal is below the contingency threshold.")
    if worst["scenario"] in {"GENERATOR_FAILURE", "COMBINED_ASSET_STRESS"} and worst["p10_survival_hours"] < 168:
        reasons.append("The mission envelope contains a dispatchable-generation loss case that constrains autonomy.")

    if worst["survival_percent"] < 35 or fuel_l <= STATION_CONFIG.fuel.emergency_reserve_liters:
        return "SURVIVAL", reasons
    if worst["p10_survival_hours"] < 72 or len(reasons) >= 3:
        return "CONTINGENCY", reasons
    if worst["p10_survival_hours"] < 120 or len(reasons) >= 1:
        return "CONSERVATION", reasons
    return "NORMAL", reasons


def _options(posture: str, trace: dict[str, Any], assurance: dict[str, Any]) -> list[dict[str, Any]]:
    reserve = float(trace.get("dynamic_reserve_percent", 20.0))
    worst = assurance["worst"]
    base = [
        ("MAINTAIN", "Maintain the current safety-constrained strategy and monitor the next decision window.", "NORMAL", False),
        ("CONSERVE", f"Raise operating reserve toward {max(reserve, 25):.0f}%, defer flexible demand and protect BESS headroom.", "CONSERVATION", True),
        ("CONTINGENCY", "Commit dispatchable readiness, protect critical loads, confirm resupply and freeze avoidable load growth.", "CONTINGENCY", True),
        ("SURVIVAL", "Protect only mission-critical demand, preserve emergency fuel/SOC and prepare for loss of dispatchable generation.", "SURVIVAL", True),
    ]
    order = {"NORMAL": 0, "CONSERVATION": 1, "CONTINGENCY": 2, "SURVIVAL": 3}
    current = order[posture]
    out = []
    for code, action, mode, approval in base:
        distance = order[mode] - current
        trigger = "READY"
        if distance > 0:
            trigger = f"Escalate if {worst['scenario']} reaches the mission trigger window or reserve margin deteriorates."
        elif distance < 0:
            trigger = "Use only after the mission envelope returns inside the safer operating band."
        out.append({"strategy": code, "mode": mode, "action": action, "approval_required": approval, "trigger": trigger})
    return out


def build_mission_autopilot(hours: int = 168, members: int = 120) -> dict[str, Any]:
    hours = max(72, min(168, int(hours)))
    members = max(50, min(1000, int(members)))
    state = twin.state
    trace = build_decision_trace(state, min(72, hours))
    forecast = _forecast(hours)
    health = asset_health_context(state)
    fuel = fuel_autonomy(state, forecast)
    assurance = _assurance(hours, members)
    posture, reasons = _posture(assurance, trace, health, fuel)
    options = _options(posture, trace, assurance)

    cf_scenarios = ["LOW_WIND", "SOLAR_LOSS", "GENERATOR_FAILURE", "HIGH_LOAD", "COMBINED_ASSET_STRESS"]
    counterfactuals = []
    for scenario in cf_scenarios:
        try:
            cf = counterfactual(state, forecast[:72], scenario)
            counterfactuals.append(cf)
        except ValueError:
            continue

    worst = assurance["worst"]
    if posture == "NORMAL":
        now = "Maintain current strategy; no escalation is triggered by the current reference envelope."
        prepare = "Keep generator readiness, reserve margin and resupply plan visible to the operator."
        when = "Re-evaluate when the forecast, asset health, fuel autonomy or stress envelope materially changes."
    elif posture == "CONSERVATION":
        now = "Shift advisory objective toward reserve preservation and flexible-load deferral."
        prepare = "Confirm resupply readiness and generator/battery maintenance posture before the next stress window."
        when = "Escalate if P10 survival falls below 72 h, reserve is breached, or dispatchable capacity is degraded."
    elif posture == "CONTINGENCY":
        now = "Prepare contingency dispatch and protect critical-load service before the limiting scenario arrives."
        prepare = "Confirm resupply, generator readiness, BESS reserve and flexible-load shedding sequence."
        when = "Escalate to survival only if critical-load coverage or emergency reserve can no longer be protected."
    else:
        now = "Enter operator-approved survival planning posture and protect mission-critical demand."
        prepare = "Preserve emergency fuel/SOC and validate generator-loss recovery actions."
        when = "Remain in survival planning until the stress envelope and reserve margins recover."

    timeline = [
        {"window": "NOW", "action": now},
        {"window": "+6H", "action": "Re-run forecast + safety shield; confirm reserve trajectory and asset availability."},
        {"window": "+12H", "action": "Re-score adverse scenarios and review flexible-load posture."},
        {"window": "+24H", "action": "Reconfirm fuel/resupply plan and generator readiness."},
        {"window": "+48H", "action": "Validate mission posture against the updated assurance envelope."},
        {"window": "+72H", "action": prepare},
    ]

    decision_id = f"AUTO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
    return {
        "engine": "DHRUVA_MISSION_AUTOPILOT_V1",
        "decision_id": decision_id,
        "mission_horizon_hours": hours,
        "current_posture": posture,
        "posture_reasons": reasons,
        "now": now,
        "prepare_for": prepare,
        "change_strategy_when": when,
        "worst_case": worst,
        "timeline": timeline,
        "strategy_options": options,
        "counterfactual_lab": counterfactuals,
        "decision_trace": {
            "steps": [
                "DATA", "FORECAST", "RISK", "OPTIONS", "CONSTRAINTS", "SELECTED_POSTURE", "EXPECTED_IMPACT", "SAFETY_CHECK", "OPERATOR_APPROVAL"
            ],
            "selected_posture": posture,
            "safety_passed": bool(trace.get("safety_validation", {}).get("passed", False)),
            "dynamic_reserve_percent": trace.get("dynamic_reserve_percent"),
            "forecast_confidence_percent": trace.get("forecast", {}).get("minimum_confidence_percent"),
            "planning_case": trace.get("planning_case"),
        },
        "hierarchical_control": ["DAY_AHEAD_MISSION_POSTURE", "ROLLING_PHYSICS_INFORMED_MPC", "REAL_TIME_DETERMINISTIC_SAFETY_SHIELD"],
        "operator_gate": {
            "approval_required_for_strategy_change": True,
            "automatic_equipment_control": False,
            "recommended_action_is_advisory": True,
        },
        "provenance": {
            "data_status": "ENGINEERING_MODEL + REFERENCE_STRESS_ENSEMBLE",
            "field_validated": False,
            "calibrated_failure_probability": False,
            "station_state_mutated": False,
        },
        "limitations": "Mission-autonomy output is a deterministic engineering advisory. It is not autonomous equipment control, a calibrated probability of failure, or a field-performance claim.",
    }
