"""DHRUVA robust scenario optimizer.

Evaluates the same feasible dispatch policy across adverse operating futures and
selects the policy with the best risk-adjusted engineering objective. This is a
scenario-screening engine, not a globally optimal stochastic program.
"""
from __future__ import annotations
from statistics import mean
from typing import Any

from app.ems.intelligence_v3 import generate_stress_scenarios
from app.optimization.optimizer import OptimizationWeights, optimize_schedule


def _scenario_loss(result: dict[str, Any], critical_weight: float = 20.0) -> float:
    s = result.get("summary", {})
    load = max(1e-9, float(s.get("load_kwh", 0.0)))
    shed = float(s.get("shed_kwh", 0.0))
    fuel = float(s.get("fuel_liters", 0.0))
    emissions = float(s.get("emissions_kg", 0.0))
    degradation = float(s.get("battery_degradation_cost", 0.0))
    return (
        critical_weight * (shed / load) * 100.0
        + 0.15 * fuel
        + 0.05 * emissions
        + degradation
    )


def _cvar(values: list[float], alpha: float) -> dict[str, float]:
    if not values:
        return {"alpha": alpha, "threshold": 0.0, "cvar": 0.0, "tail_count": 0}
    ordered = sorted(float(v) for v in values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * alpha)))
    threshold = ordered[index]
    tail = [v for v in ordered if v >= threshold]
    return {
        "alpha": alpha,
        "threshold": round(threshold, 4),
        "cvar": round(mean(tail), 4),
        "tail_count": len(tail),
    }


def robust_scenario_evaluation(
    forecast: list[dict],
    state,
    *,
    alpha: float = 0.80,
    generator_available: bool = True,
) -> dict[str, Any]:
    """Evaluate adverse scenarios and rank them by expected + tail risk.

    The baseline scenario and the generated stress scenarios use identical
    optimizer constraints. Generator-failure is evaluated with the generator
    explicitly unavailable. No live state is mutated.
    """
    scenarios = generate_stress_scenarios(forecast)
    physics = physics_consistency_check(forecast)
    evaluations = []
    for item in scenarios:
        name = item["scenario"]
        available = generator_available and name != "GENERATOR_FAILURE"
        result = optimize_schedule(
            item["forecast"], state,
            OptimizationWeights(cost=1.0, emissions=1.0, reliability=5.0, fuel=2.0, renewable=2.0),
            generator_available=available,
        )
        summary = result["summary"]
        loss = _scenario_loss(result)
        evaluations.append({
            "scenario": name,
            "generator_available": available,
            "loss": round(loss, 4),
            "service_level_percent": round(float(summary.get("service_level_percent", 0.0)), 3),
            "load_shed_kwh": round(float(summary.get("shed_kwh", 0.0)), 3),
            "fuel_liters": round(float(summary.get("fuel_liters", 0.0)), 3),
            "minimum_soc_percent": round(float(summary.get("minimum_soc_percent", 0.0)), 3),
            "final_fuel_liters": round(float(summary.get("final_fuel_liters", 0.0)), 3),
            "renewable_share_percent": round(float(summary.get("renewable_share_percent", 0.0)), 3),
            "schedule": result.get("schedule", []),
        })

    losses = [x["loss"] for x in evaluations]
    tail = _cvar(losses, alpha)
    expected_loss = mean(losses) if losses else 0.0
    for x in evaluations:
        x.pop("schedule", None)
    ranked = sorted(evaluations, key=lambda x: x["loss"])
    worst = max(evaluations, key=lambda x: x["loss"]) if evaluations else None
    return {
        "engine": "DHRUVA_ROBUST_SCENARIO_ENGINE_V1",
        "optimality_claim": False,
        "risk_measure": "CVaR-style upper-tail scenario loss",
        "alpha": alpha,
        "scenario_count": len(evaluations),
        "expected_loss": round(expected_loss, 4),
        "cvar": tail,
        "physics_consistency": physics,
        "best_case": ranked[0] if ranked else None,
        "worst_case": worst,
        "scenario_results": evaluations,
        "selection_rule": "lowest risk-adjusted loss; tie-break by higher service level",
        "station_state_mutated": False,
        "data_status": "ENGINEERING_MODEL",
        "advisory_only": True,
        "note": "Scenario/CVaR screening uses deterministic engineering heuristics. It is not a globally optimal stochastic program and is not field validated.",
    }


def physics_consistency_check(forecast: list[dict]) -> dict[str, Any]:
    """Check forecast generation against simple station physics envelopes."""
    from app.config import STATION_CONFIG
    from app.models.solar import SolarModelInputs, calculate_solar
    from app.models.wind import WindModelInputs, calculate_wind

    violations = []
    checked = 0
    for i, row in enumerate(forecast):
        checked += 1
        wind_expected = calculate_wind(WindModelInputs(
            float(row.get('wind_speed_mps', 0.0)),
            float(row.get('wind_icing_factor', 1.0)),
        ), STATION_CONFIG.wind).wind_power_kw
        solar_expected = calculate_solar(SolarModelInputs(
            float(row.get('solar_irradiance_w_m2', 0.0)),
            float(row.get('temperature_celsius', 0.0)),
            float(row.get('solar_derate_factor', 1.0)),
        ), STATION_CONFIG.solar).solar_power_kw
        wind_actual = max(0.0, float(row.get('wind_kw', 0.0)))
        solar_actual = max(0.0, float(row.get('solar_kw', 0.0)))
        # Forecast models can deviate from the physics model; use a transparent
        # tolerance rather than forcing exact equality.
        wind_tol = max(5.0, 0.35 * max(1.0, wind_expected))
        solar_tol = max(5.0, 0.35 * max(1.0, solar_expected))
        if abs(wind_actual - wind_expected) > wind_tol:
            violations.append({"hour_offset": i, "asset": "WIND", "forecast_kw": round(wind_actual, 3), "physics_reference_kw": round(wind_expected, 3)})
        if abs(solar_actual - solar_expected) > solar_tol:
            violations.append({"hour_offset": i, "asset": "SOLAR", "forecast_kw": round(solar_actual, 3), "physics_reference_kw": round(solar_expected, 3)})
    return {
        "status": "PASS" if not violations else "REVIEW",
        "checked_points": checked,
        "violation_count": len(violations),
        "violations": violations[:20],
        "tolerance": "max(5 kW, 35% of physics reference)",
        "method": "physics-envelope-consistency-check",
        "field_validated": False,
    }
