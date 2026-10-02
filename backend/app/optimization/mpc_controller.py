"""Physics-informed rolling-horizon controller for DHRUVA.

This module is deliberately advisory. It performs receding-horizon policy
selection over deterministic engineering scenarios, applies conservative
renewable physics envelopes, and never mutates the authoritative Digital Twin.
It is not a globally optimal MPC or a field-validated controller.
"""
from __future__ import annotations

from copy import deepcopy
from statistics import mean
from typing import Any

from app.config import STATION_CONFIG
from app.ems.intelligence_v3 import generate_stress_scenarios
from app.optimization.optimizer import OptimizationWeights, optimize_schedule
from app.optimization.robust_optimizer import _cvar, _scenario_loss, physics_consistency_check
from app.models.solar import SolarModelInputs, calculate_solar
from app.models.wind import WindModelInputs, calculate_wind


def _physics_constrained_forecast(forecast: list[dict]) -> tuple[list[dict], dict[str, Any]]:
    """Conservatively cap forecast renewable generation at engineering physics envelopes."""
    rows: list[dict] = []
    capped = []
    for i, row in enumerate(forecast):
        item = dict(row)
        wind_ref = calculate_wind(
            WindModelInputs(float(row.get("wind_speed_mps", 0.0)), float(row.get("wind_icing_factor", 1.0))),
            STATION_CONFIG.wind,
        ).wind_power_kw
        solar_ref = calculate_solar(
            SolarModelInputs(
                float(row.get("solar_irradiance_w_m2", 0.0)),
                float(row.get("temperature_celsius", 0.0)),
                float(row.get("solar_derate_factor", 1.0)),
            ),
            STATION_CONFIG.solar,
        ).solar_power_kw
        old_wind = max(0.0, float(row.get("wind_kw", 0.0)))
        old_solar = max(0.0, float(row.get("solar_kw", 0.0)))
        new_wind = min(old_wind, max(0.0, wind_ref))
        new_solar = min(old_solar, max(0.0, solar_ref))
        if new_wind < old_wind - 1e-9 or new_solar < old_solar - 1e-9:
            capped.append({
                "hour_offset": i,
                "wind_forecast_kw": round(old_wind, 3),
                "wind_physics_cap_kw": round(wind_ref, 3),
                "solar_forecast_kw": round(old_solar, 3),
                "solar_physics_cap_kw": round(solar_ref, 3),
            })
        item["wind_kw"] = new_wind
        item["solar_kw"] = new_solar
        item["renewable_kw"] = new_wind + new_solar
        rows.append(item)
    return rows, {
        "method": "conservative-physics-envelope-cap",
        "capped_points": len(capped),
        "caps": capped[:20],
        "over_credit_prevented": bool(capped),
        "field_validated": False,
    }


def _candidate_policies() -> list[dict[str, Any]]:
    return [
        {
            "id": "BALANCED_ROBUST",
            "weights": OptimizationWeights(cost=1.0, emissions=1.0, reliability=5.0, fuel=2.0, renewable=2.0),
            "reserve_multiplier": 1.00,
        },
        {
            "id": "HIGH_RELIABILITY",
            "weights": OptimizationWeights(cost=1.0, emissions=1.0, reliability=8.0, fuel=2.5, renewable=1.5),
            "reserve_multiplier": 1.10,
        },
        {
            "id": "FUEL_CONSERVATION",
            "weights": OptimizationWeights(cost=1.0, emissions=0.8, reliability=5.0, fuel=4.0, renewable=2.0),
            "reserve_multiplier": 1.05,
        },
        {
            "id": "RENEWABLE_MAXIMIZATION",
            "weights": OptimizationWeights(cost=1.0, emissions=1.5, reliability=4.0, fuel=2.0, renewable=4.0),
            "reserve_multiplier": 1.00,
        },
    ]


def _candidate_score(forecast: list[dict], state, policy: dict[str, Any], alpha: float) -> dict[str, Any]:
    scenarios = generate_stress_scenarios(forecast)
    base_reserve = STATION_CONFIG.simulation.safe_battery_reserve_ratio
    reserve = min(STATION_CONFIG.battery.max_soc_ratio, base_reserve * policy["reserve_multiplier"])
    results = []
    for scenario in scenarios:
        available = scenario["scenario"] != "GENERATOR_FAILURE"
        result = optimize_schedule(
            scenario["forecast"],
            state,
            policy["weights"],
            min_reserve_ratio=reserve,
            generator_available=available,
        )
        results.append(result)
    losses = [_scenario_loss(r) for r in results]
    tail = _cvar(losses, alpha)
    expected = mean(losses) if losses else 0.0
    nominal = results[0] if results else {"schedule": [], "summary": {}}
    return {
        "policy_id": policy["id"],
        "reserve_ratio": reserve,
        "expected_loss": expected,
        "cvar": tail["cvar"],
        "tail_threshold": tail["threshold"],
        "tail_count": tail["tail_count"],
        "worst_loss": max(losses) if losses else 0.0,
        "nominal_schedule": nominal.get("schedule", []),
        "nominal_summary": nominal.get("summary", {}),
        "weights": policy["weights"].__dict__,
    }


def _advance_planning_state(state, dispatch_row: dict[str, Any]) -> Any:
    """Advance only planning state by one hour; the live Twin is never touched."""
    next_state = deepcopy(state)
    dt = 3600.0
    charge = max(0.0, float(dispatch_row.get("battery_charge_kw", 0.0)))
    discharge = max(0.0, float(dispatch_row.get("battery_discharge_kw", 0.0)))
    eff = STATION_CONFIG.battery.round_trip_efficiency_ratio
    capacity = STATION_CONFIG.battery.capacity_kwh
    soc = float(next_state.battery.soc_ratio)
    soc += charge * eff * dt / 3600.0 / capacity
    soc -= discharge / max(eff, 1e-9) * dt / 3600.0 / capacity
    next_state.battery.soc_ratio = max(STATION_CONFIG.battery.min_soc_ratio, min(STATION_CONFIG.battery.max_soc_ratio, soc))
    diesel = max(0.0, float(dispatch_row.get("diesel_kw", 0.0)))
    fuel_use = 0.0
    if diesel > 0:
        fuel_use = STATION_CONFIG.diesel.fuel_intercept_lph + STATION_CONFIG.diesel.fuel_slope_l_per_kwh * diesel
    next_state.fuel.fuel_remaining_liters = max(0.0, next_state.fuel.fuel_remaining_liters - fuel_use)
    next_state.fuel.cumulative_consumed_liters += fuel_use
    next_state.battery.cycle_count += (charge + discharge) / max(2.0 * capacity, 1e-9)
    return next_state


def run_physics_informed_mpc(forecast: list[dict], state, *, control_horizon: int = 6, lookahead_hours: int = 12, alpha: float = 0.80) -> dict[str, Any]:
    if not forecast:
        raise ValueError("forecast must not be empty")
    control_horizon = max(1, min(int(control_horizon), len(forecast)))
    lookahead_hours = max(3, min(int(lookahead_hours), 24, len(forecast)))
    alpha = max(0.50, min(0.99, float(alpha)))

    constrained_forecast, physics = _physics_constrained_forecast(forecast)
    initial_physics_check = physics_consistency_check(constrained_forecast)
    planning_state = deepcopy(state)
    controls = []
    candidate_history = []

    for step in range(control_horizon):
        window = constrained_forecast[step: min(len(constrained_forecast), step + lookahead_hours)]
        candidates = [_candidate_score(window, planning_state, p, alpha) for p in _candidate_policies()]
        # CVaR dominates expected loss for survival planning; expected loss is a tie-break.
        chosen = min(candidates, key=lambda x: (x["cvar"], x["expected_loss"], x["worst_loss"]))
        schedule = chosen["nominal_schedule"]
        first = schedule[0] if schedule else {}
        controls.append({
            "step": step,
            "hour_offset": step,
            "policy_id": chosen["policy_id"],
            "battery_charge_kw": round(float(first.get("battery_charge_kw", 0.0)), 3),
            "battery_discharge_kw": round(float(first.get("battery_discharge_kw", 0.0)), 3),
            "diesel_kw": round(float(first.get("diesel_kw", 0.0)), 3),
            "load_shed_kw": round(float(first.get("load_shed_kw", 0.0)), 3),
            "soc_percent": round(float(first.get("soc_percent", planning_state.battery.soc_ratio * 100.0)), 3),
            "fuel_remaining_liters": round(float(first.get("fuel_remaining_liters", planning_state.fuel.fuel_remaining_liters)), 3),
            "risk": {"cvar": round(chosen["cvar"], 4), "expected_loss": round(chosen["expected_loss"], 4), "worst_loss": round(chosen["worst_loss"], 4)},
        })
        candidate_history.append({
            "step": step,
            "selected_policy": chosen["policy_id"],
            "candidates": [
                {k: round(v, 4) if isinstance(v, float) else v for k, v in c.items() if k in {"policy_id", "expected_loss", "cvar", "tail_threshold", "tail_count", "worst_loss", "reserve_ratio"}}
                for c in candidates
            ],
        })
        planning_state = _advance_planning_state(planning_state, first)

    return {
        "engine": "DHRUVA_PHYSICS_INFORMED_ROLLING_MPC_V1",
        "optimality_claim": False,
        "control_horizon_hours": control_horizon,
        "lookahead_hours": lookahead_hours,
        "risk_measure": f"CVaR-style upper-tail scenario loss (alpha={alpha:.2f})",
        "controls": controls,
        "candidate_evaluations": candidate_history,
        "physics_constraint": physics,
        "physics_consistency_after_cap": initial_physics_check,
        "final_planning_soc_percent": round(planning_state.battery.soc_ratio * 100.0, 3),
        "final_planning_fuel_liters": round(planning_state.fuel.fuel_remaining_liters, 3),
        "station_state_mutated": False,
        "data_status": "ENGINEERING_MODEL",
        "advisory_only": True,
        "replan_policy": "re-evaluate candidates at every control step using the latest planning state",
        "safety_note": "This controller is advisory. Production actuation requires the existing deterministic safety shield and field validation.",
    }
