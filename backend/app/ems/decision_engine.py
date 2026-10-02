from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import STATION_CONFIG
from app.digital_twin.station_twin import StationTwin, StationTwinInputs
from app.ems.controller import EMSController, DispatchCommand, validate_command
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.optimization.optimizer import OptimizationWeights, optimize_schedule
from app.ems.intelligence_engine import uncertainty_summary, robust_forecast, dynamic_reserve_percent, fuel_autonomy, asset_health_context


def _dynamic_reserve(state, forecast: list[dict]) -> float:
    return dynamic_reserve_percent(state, forecast)


def validate_plan(schedule: list[dict], state, dynamic_reserve_percent: float) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    critical = float(state.loads.critical_load_kw)
    min_soc = float(STATION_CONFIG.battery.min_soc_ratio * 100.0)
    max_soc = float(STATION_CONFIG.battery.max_soc_ratio * 100.0)
    emergency_fuel = float(STATION_CONFIG.fuel.emergency_reserve_liters)

    for row in schedule:
        h = int(row.get("hour_offset", 0))
        load = max(0.0, float(row.get("load_kw", 0.0)))
        shed = max(0.0, float(row.get("load_shed_kw", 0.0)))
        soc = float(row.get("soc_percent", 0.0))
        fuel = float(row.get("fuel_remaining_liters", 0.0))
        diesel = max(0.0, float(row.get("diesel_kw", 0.0)))
        charge = max(0.0, float(row.get("battery_charge_kw", 0.0)))
        discharge = max(0.0, float(row.get("battery_discharge_kw", 0.0)))

        if charge > 0 and discharge > 0:
            violations.append({"hour": h, "code": "BATTERY_SIMULTANEOUS_CHARGE_DISCHARGE", "severity": "HARD"})
        if soc < min_soc - 1e-6 or soc > max_soc + 1e-6:
            violations.append({"hour": h, "code": "BATTERY_SOC_LIMIT", "severity": "HARD"})
        if diesel > STATION_CONFIG.diesel.rated_power_kw + 1e-6:
            violations.append({"hour": h, "code": "DIESEL_RATED_POWER", "severity": "HARD"})
        if 0 < diesel < STATION_CONFIG.diesel.minimum_power_kw - 1e-6:
            violations.append({"hour": h, "code": "DIESEL_MINIMUM_OUTPUT", "severity": "HARD"})
        if fuel < -1e-6:
            violations.append({"hour": h, "code": "NEGATIVE_FUEL", "severity": "HARD"})
        # Shed is only acceptable when it is from non-critical demand.
        non_critical = max(0.0, load - critical)
        if shed > non_critical + 1e-6:
            violations.append({"hour": h, "code": "CRITICAL_LOAD_SHED", "severity": "HARD"})

    minimum_soc = min((float(r.get("soc_percent", 0.0)) for r in schedule), default=state.battery.soc_ratio * 100.0)
    final_fuel = float(schedule[-1].get("fuel_remaining_liters", state.fuel.fuel_remaining_liters)) if schedule else state.fuel.fuel_remaining_liters
    reserve_margin = minimum_soc - dynamic_reserve_percent
    return {
        "passed": not violations,
        "violations": violations,
        "hard_violation_count": len(violations),
        "critical_load_protected": not any(v["code"] == "CRITICAL_LOAD_SHED" for v in violations),
        "minimum_soc_percent": round(minimum_soc, 2),
        "final_fuel_liters": round(final_fuel, 2),
        "dynamic_reserve_percent": round(dynamic_reserve_percent, 2),
        "reserve_margin_percent": round(reserve_margin, 2),
        "emergency_fuel_liters": round(emergency_fuel, 2),
    }


def _baseline_dispatch(forecast: list[dict], state) -> dict:
    """Simple incumbent/rule baseline: renewable first, then diesel, no planned BESS discharge."""
    cfg = STATION_CONFIG
    fuel = float(state.fuel.fuel_remaining_liters)
    rows: list[dict] = []
    fuel_used = 0.0
    diesel_kwh = 0.0
    renewable_kwh = 0.0
    load_kwh = 0.0
    shed_kwh = 0.0
    for i, row in enumerate(forecast):
        load = max(0.0, float(row.get("load_kw", 0.0)))
        renewable = min(load, max(0.0, float(row.get("solar_kw", 0.0)) + float(row.get("wind_kw", 0.0))))
        deficit = max(0.0, load - renewable)
        diesel = 0.0
        if deficit > 0 and fuel > cfg.fuel.emergency_reserve_liters:
            diesel = min(cfg.diesel.rated_power_kw, max(cfg.diesel.minimum_power_kw, deficit))
            hours = 1.0
            fuel_step = cfg.diesel.fuel_intercept_lph * hours + cfg.diesel.fuel_slope_l_per_kwh * diesel * hours
            if fuel - fuel_step < cfg.fuel.emergency_reserve_liters:
                available = max(0.0, fuel - cfg.fuel.emergency_reserve_liters)
                max_diesel = max(0.0, (available - cfg.diesel.fuel_intercept_lph) / cfg.diesel.fuel_slope_l_per_kwh)
                diesel = min(diesel, max_diesel)
                fuel_step = cfg.diesel.fuel_intercept_lph + cfg.diesel.fuel_slope_l_per_kwh * diesel if diesel >= cfg.diesel.minimum_power_kw else 0.0
            fuel = max(0.0, fuel - fuel_step)
            fuel_used += fuel_step
        served = min(load, renewable + diesel)
        shed = max(0.0, load - served)
        renewable_kwh += renewable
        diesel_kwh += diesel
        load_kwh += load
        shed_kwh += shed
        rows.append({"hour_offset": i, "load_kw": load, "renewable_kw": renewable, "diesel_kw": diesel, "load_shed_kw": shed, "fuel_remaining_liters": fuel, "soc_percent": state.battery.soc_ratio * 100.0, "battery_charge_kw": 0.0, "battery_discharge_kw": 0.0})
    total_generation = renewable_kwh + diesel_kwh
    return {
        "engine": "rule_based_baseline",
        "schedule": rows,
        "fuel_liters": round(fuel_used, 2),
        "renewable_share_percent": round(100.0 * renewable_kwh / max(1e-9, total_generation), 2),
        "service_level_percent": round(100.0 * (load_kwh - shed_kwh) / max(1e-9, load_kwh), 2),
        "unserved_energy_kwh": round(shed_kwh, 2),
        "final_fuel_liters": round(fuel, 2),
    }


def build_decision_trace(state, hours: int = 24) -> dict[str, Any]:
    hours = max(6, min(72, int(hours)))
    forecast_bundle = generate_multi_day_forecast(state.time.timestamp, hours, state.weather.temperature_celsius, state.weather.wind_speed_mps)
    forecast = forecast_bundle["forecast"]
    reserve = _dynamic_reserve(state, forecast)
    uncertainty = uncertainty_summary(forecast)
    planning_forecast = robust_forecast(forecast)
    weights = OptimizationWeights(cost=1.0, emissions=1.0, reliability=5.0, fuel=4.0, renewable=3.0)
    plan = optimize_schedule(
        planning_forecast,
        state,
        weights,
        min_reserve_ratio=max(STATION_CONFIG.battery.min_soc_ratio, reserve / 100.0),
        soc_min_ratio=STATION_CONFIG.battery.min_soc_ratio,
        soc_max_ratio=STATION_CONFIG.battery.max_soc_ratio,
    )
    safety = validate_plan(plan["schedule"], state, reserve)
    baseline = _baseline_dispatch(forecast, state)
    summary = plan["summary"]
    fuel_delta = baseline["fuel_liters"] - float(summary["fuel_liters"])
    service_delta = float(summary["service_level_percent"]) - baseline["service_level_percent"]
    selected_first = plan["schedule"][0] if plan["schedule"] else {}
    confidence = min(float(r.get("confidence", 1.0)) for r in forecast) if forecast else 0.0

    why = [
        {"step": 1, "title": "Forecast", "detail": f"{hours}h forecast uses the integrated ML/reference-weather pipeline with minimum confidence {confidence*100:.0f}%."},
        {"step": 2, "title": "Reserve", "detail": f"Dynamic reserve target is {reserve:.1f}% based on forecast confidence and polar weather stress."},
        {"step": 3, "title": "Optimization", "detail": f"The bounded multi-objective engine evaluates renewable, battery, diesel, fuel and service constraints."},
        {"step": 4, "title": "Safety Shield", "detail": "The candidate dispatch is checked for SOC, generator, fuel and critical-load constraints before recommendation."},
    ]
    if not safety["passed"]:
        decision = "FALLBACK_TO_SAFE_DISPATCH"
        decision_reason = "Candidate rejected by safety shield; operator should use the bounded fallback controller."
    elif fuel_delta > 0:
        decision = "USE_DHRUVA_STRATEGY"
        decision_reason = f"Projected fuel use is {fuel_delta:.1f} L lower than the rule-based baseline while preserving service constraints."
    else:
        decision = "USE_FEASIBLE_DHRUVA_STRATEGY"
        decision_reason = "The DHRUVA plan is feasible; baseline comparison does not show a fuel reduction for this snapshot."

    return {
        "engine": "DHRUVA_DECISION_ENGINE_V1",
        "data_status": "ENGINEERING_MODEL",
        "horizon_hours": hours,
        "decision": decision,
        "decision_reason": decision_reason,
        "decision_id": f"DEC-{state.time.timestamp.strftime('%Y%m%d%H%M%S')}-{hours}H",
        "inputs": {
            "load_kw": round(float(state.loads.total_load_kw), 2),
            "battery_soc_percent": round(float(state.battery.soc_ratio * 100.0), 2),
            "fuel_liters": round(float(state.fuel.fuel_remaining_liters), 2),
            "temperature_celsius": round(float(state.weather.temperature_celsius), 2),
            "wind_speed_mps": round(float(state.weather.wind_speed_mps), 2),
            "forecast_confidence_percent": round(confidence * 100.0, 2),
        },
        "forecast": {
            "peak_load_kw": round(max((float(r.get("load_kw", 0.0)) for r in forecast), default=0.0), 2),
            "peak_solar_kw": round(max((float(r.get("solar_kw", 0.0)) for r in forecast), default=0.0), 2),
            "avg_wind_mps": round(sum(float(r.get("wind_speed_mps", 0.0)) for r in forecast) / max(1, len(forecast)), 2),
            "minimum_confidence_percent": round(confidence * 100.0, 2),
        },
        "dynamic_reserve_percent": reserve,
        "uncertainty": uncertainty,
        "asset_health": asset_health_context(state),
        "fuel_autonomy": fuel_autonomy(state, forecast),
        "planning_case": "P90_LOAD_P10_RENEWABLE",
        "candidate_plan": plan,
        "safety_validation": safety,
        "baseline_comparison": {
            "baseline": baseline,
            "dhruva": {
                "fuel_liters": round(float(summary["fuel_liters"]), 2),
                "renewable_share_percent": round(float(summary["renewable_share_percent"]), 2),
                "service_level_percent": round(float(summary["service_level_percent"]), 2),
                "unserved_energy_kwh": round(float(summary["shed_kwh"]), 2),
                "minimum_soc_percent": round(float(summary["minimum_soc_percent"]), 2),
            },
            "delta": {
                "fuel_saved_liters": round(fuel_delta, 2),
                "service_level_delta_percent": round(service_delta, 2),
                "unserved_energy_delta_kwh": round(float(summary["shed_kwh"]) - baseline["unserved_energy_kwh"], 2),
            },
        },
        "first_action": {
            "solar_kw": round(float(selected_first.get("solar_kw", 0.0)), 2),
            "wind_kw": round(float(selected_first.get("wind_kw", 0.0)), 2),
            "battery_charge_kw": round(float(selected_first.get("battery_charge_kw", 0.0)), 2),
            "battery_discharge_kw": round(float(selected_first.get("battery_discharge_kw", 0.0)), 2),
            "diesel_kw": round(float(selected_first.get("diesel_kw", 0.0)), 2),
        },
        "trace": why,
        "operator_action_required": decision.startswith("FALLBACK"),
        "optimality_claim": False,
        "note": "Decision-support output from bounded engineering/ML models; not field-validated operational control.",
    }


def run_72h_stress_test(state) -> dict[str, Any]:
    hours = 72
    start = state.time.timestamp if state.time.timestamp.tzinfo else state.time.timestamp.replace(tzinfo=timezone.utc)
    forecast = generate_multi_day_forecast(start, hours, state.weather.temperature_celsius, state.weather.wind_speed_mps)["forecast"]
    twin = StationTwin()
    twin.state.battery.soc_ratio = float(state.battery.soc_ratio)
    twin.state.fuel.fuel_remaining_liters = float(state.fuel.fuel_remaining_liters)
    controller = EMSController()
    points: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for i, row in enumerate(forecast):
        wind_factor = 1.0
        solar_factor = 1.0
        temp_offset = 0.0
        load_factor = 1.0
        diesel_available = True
        battery_available = True
        event = "NORMAL"
        if 6 <= i < 12:
            wind_factor, event = 0.60, "WIND_DROP"
        elif 12 <= i < 18:
            solar_factor, event = 0.0, "SOLAR_UNAVAILABLE"
        elif 18 <= i < 24:
            temp_offset, load_factor, event = -8.0, 1.10, "EXTREME_COLD_LOAD_RISE"
        elif 24 <= i < 36:
            diesel_available, event = False, "GENERATOR_FAILURE"
        elif 36 <= i < 48:
            battery_available, event = False, "BATTERY_FAILURE"
        elif 48 <= i < 60:
            wind_factor, solar_factor, event = 0.35, 0.0, "RENEWABLE_COLLAPSE"
        elif 60 <= i < 72:
            load_factor, event = 1.20, "HIGH_RESEARCH_LOAD"

        if not events or events[-1]["event"] != event:
            events.append({"hour_offset": i, "event": event})

        temp = float(row.get("temperature_celsius", -30.0)) + temp_offset
        wind = max(0.0, float(row.get("wind_speed_mps", 0.0)) * wind_factor)
        solar = max(0.0, float(row.get("solar_irradiance_w_m2", 0.0)) * solar_factor)
        base = StationTwinInputs(
            timestamp=start + timedelta(hours=i),
            outdoor_temperature_celsius=temp,
            wind_speed_mps=wind,
            solar_irradiance_w_m2=solar,
            snowfall_rate=float(row.get("snowfall_rate", 0.0)),
            battery_temperature_celsius=max(-10.0, temp + 8.0),
            critical_load_kw=STATION_CONFIG.loads.critical_load_kw,
            important_load_kw=STATION_CONFIG.loads.important_load_kw * load_factor,
            flexible_load_kw=min(STATION_CONFIG.loads.max_flexible_load_kw, STATION_CONFIG.loads.flexible_load_kw * load_factor),
            timestep_seconds=3600,
        )
        command = controller.decide(base, twin.state, forecast=row)
        if not diesel_available:
            command = replace(command, diesel_power_kw=0.0, diesel_running=False, reason="generator_failure_safety_override")
        if not battery_available:
            command = replace(command, battery_charge_kw=0.0, battery_discharge_kw=0.0, reason="battery_failure_safety_override")
        command = validate_command(command)
        result = twin.step(replace(base,
            battery_charge_request_kw=command.battery_charge_kw,
            battery_discharge_request_kw=command.battery_discharge_kw,
            diesel_power_request_kw=command.diesel_power_kw,
            diesel_running=command.diesel_running,
        ))
        s = result.state
        points.append({
            "hour_offset": i,
            "event": event,
            "load_kw": round(float(s.loads.total_load_kw), 2),
            "served_load_kw": round(float(s.loads.served_load_kw), 2),
            "critical_load_kw": round(float(s.loads.critical_load_kw), 2),
            "shed_load_kw": round(float(s.loads.shed_load_kw), 2),
            "solar_kw": round(float(s.generation.solar_power_kw), 2),
            "wind_kw": round(float(s.generation.wind_power_kw), 2),
            "diesel_kw": round(float(s.generation.diesel_power_kw), 2),
            "battery_soc_percent": round(float(s.battery.soc_ratio * 100.0), 2),
            "fuel_remaining_liters": round(float(s.fuel.fuel_remaining_liters), 2),
            "operating_mode": s.status.operating_mode.value,
        })

    critical_steps = sum(1 for p in points if p["served_load_kw"] + 1e-6 < p["critical_load_kw"])
    min_soc = min((p["battery_soc_percent"] for p in points), default=0.0)
    final_fuel = points[-1]["fuel_remaining_liters"] if points else state.fuel.fuel_remaining_liters
    fuel_used = max(0.0, float(state.fuel.fuel_remaining_liters) - final_fuel)
    renewable = sum(p["solar_kw"] + p["wind_kw"] for p in points)
    diesel = sum(p["diesel_kw"] for p in points)
    load = sum(p["load_kw"] for p in points)
    shed = sum(p["shed_load_kw"] for p in points)
    return {
        "engine": "DHRUVA_72H_POLAR_STRESS_TEST_V1",
        "data_status": "ENGINEERING_MODEL",
        "horizon_hours": 72,
        "events": events,
        "points": points,
        "metrics": {
            "fuel_consumed_liters": round(fuel_used, 2),
            "final_fuel_liters": round(final_fuel, 2),
            "minimum_battery_soc_percent": round(min_soc, 2),
            "critical_load_failure_steps": critical_steps,
            "critical_load_coverage_percent": round(100.0 * (1.0 - critical_steps / 72.0), 2),
            "load_shed_energy_kwh": round(shed, 2),
            "service_level_percent": round(100.0 * (load - shed) / max(1e-9, load), 2),
            "renewable_share_percent": round(100.0 * renewable / max(1e-9, renewable + diesel), 2),
            "safety_violations": critical_steps,
        },
        "success": critical_steps == 0,
        "optimality_claim": False,
        "note": "72-hour staged stress test uses the isolated Digital Twin; live station state is never mutated.",
    }
