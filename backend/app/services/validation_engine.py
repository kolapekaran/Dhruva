"""Phase-4 validation and evidence engine for DHRUVA.

This module reports measured engineering evidence from the existing reference
models and Digital Twin. It does not manufacture field-validation claims or
convert the results into an overall score.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.api.twin import twin
from app.config import STATION_CONFIG
from app.ems.decision_engine import build_decision_trace, run_72h_stress_test
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.ml.inference.predictor import ARTIFACT_DIR
from app.optimization.optimizer import optimize_schedule
from app.scenarios.simulator import ScenarioParameters, simulate_scenario


def _model_validation_metrics() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("load", "solar", "wind"):
        path = ARTIFACT_DIR / f"{name}_model_metrics.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            metrics = payload.get("metrics", {})
            out[name] = {
                key: metrics[key]
                for key in ("MAE", "RMSE", "R2", "MAPE_percent")
                if key in metrics
            }
            out[name]["samples"] = payload.get("samples")
            out[name]["synthetic_reference"] = bool(payload.get("synthetic", True))
        except (OSError, ValueError, TypeError):
            out[name] = {"status": "UNAVAILABLE"}
    return out


def _optimizer_evidence(hours: int = 24) -> dict[str, Any]:
    s = twin.state
    start = s.time.timestamp
    bundle = generate_multi_day_forecast(
        start,
        hours,
        s.weather.temperature_celsius,
        s.weather.wind_speed_mps,
    )
    forecast = bundle.get("forecast", [])
    started = time.perf_counter()
    result = optimize_schedule(forecast, s)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    summary = result.get("summary", {})
    return {
        "engine": result.get("engine"),
        "horizon_hours": len(forecast),
        "execution_time_ms": round(elapsed_ms, 3),
        "schedule_points": len(result.get("schedule", [])),
        "optimality_claim": bool(result.get("optimality_claim", False)),
        "service_level_percent": round(float(summary.get("service_level_percent", 0.0)), 3),
        "fuel_liters": round(float(summary.get("fuel_liters", 0.0)), 3),
        "minimum_soc_percent": round(float(summary.get("minimum_soc_percent", 0.0)), 3),
        "load_shed_kwh": round(float(summary.get("shed_kwh", 0.0)), 3),
        "safety_reserve_ratio": STATION_CONFIG.battery.min_soc_ratio,
    }


def _scenario_matrix(hours: int = 72) -> list[dict[str, Any]]:
    cases = [
        ("BASELINE", {}),
        ("WIND DROP", {"wind_reduction_percent": 60}),
        ("SOLAR LOSS", {"solar_reduction_percent": 100}),
        ("EXTREME COLD", {"temperature_override_celsius": -40, "load_increase_percent": 25}),
        ("GENERATOR FAILURE", {"diesel_available": False}),
        ("BATTERY FAILURE", {"battery_health_percent": 0}),
        ("RENEWABLE COLLAPSE + HIGH LOAD", {"wind_reduction_percent": 80, "solar_reduction_percent": 80, "load_increase_percent": 20}),
    ]
    # One shared forecast keeps the matrix comparable and avoids hidden per-case
    # weather differences.
    base_bundle = generate_multi_day_forecast(
        twin.state.time.timestamp,
        hours,
        twin.state.weather.temperature_celsius,
        twin.state.weather.wind_speed_mps,
    )
    rows: list[dict[str, Any]] = []
    baseline_metrics: dict[str, Any] | None = None
    for name, kwargs in cases:
        result = simulate_scenario(
            ScenarioParameters(name=name, **kwargs),
            hours,
            forecast_bundle=base_bundle,
        )
        m = result["metrics"]
        row = {
            "scenario": name,
            "status": "PASS" if m["critical_load_failure_steps"] == 0 else "CRITICAL_LOAD_GAP",
            "service_level_percent": round(float(m["service_level_percent"]), 3),
            "critical_load_failure_steps": int(m["critical_load_failure_steps"]),
            "load_shed_energy_kwh": round(float(m["load_shed_energy_kwh"]), 3),
            "minimum_soc_percent": round(float(m["minimum_soc_percent"]), 3),
            "fuel_consumed_liters": round(float(m["fuel_consumed_liters"]), 3),
            "final_fuel_liters": round(float(m["final_fuel_liters"]), 3),
            "renewable_share_percent": round(float(m["renewable_share_percent"]), 3),
            "safety_violations": int(m["critical_load_failure_steps"]),
        }
        if baseline_metrics is None:
            baseline_metrics = m
            row["fuel_delta_vs_baseline_liters"] = 0.0
            row["service_delta_vs_baseline_percent"] = 0.0
        else:
            row["fuel_delta_vs_baseline_liters"] = round(float(m["fuel_consumed_liters"] - baseline_metrics["fuel_consumed_liters"]), 3)
            row["service_delta_vs_baseline_percent"] = round(float(m["service_level_percent"] - baseline_metrics["service_level_percent"]), 3)
        rows.append(row)
    return rows


def mission_validation_report(hours: int = 72) -> dict[str, Any]:
    hours = max(24, min(72, int(hours)))
    decision = build_decision_trace(twin.state, min(72, hours))
    stress = run_72h_stress_test(twin.state)
    matrix = _scenario_matrix(hours)
    optimizer = _optimizer_evidence(min(24, hours))
    forecast_metrics = _model_validation_metrics()

    safety_checks = {
        "decision_trace_safety_passed": bool(decision.get("safety_validation", {}).get("passed", False)),
        "decision_trace_hard_violation_count": int(decision.get("safety_validation", {}).get("hard_violation_count", 0)),
        "stress_test_safety_violations": int(stress.get("metrics", {}).get("safety_violations", 0)),
        "stress_test_critical_load_failures": int(stress.get("metrics", {}).get("critical_load_failure_steps", 0)),
        "matrix_critical_load_failures": sum(int(x["critical_load_failure_steps"]) for x in matrix),
    }

    return {
        "engine": "DHRUVA_VALIDATION_EVIDENCE_V1",
        "station": getattr(twin.state, "station_name", "Maitri Research Station"),
        "horizon_hours": hours,
        "data_status": "ENGINEERING_MODEL",
        "validation_scope": [
            "decision_trace",
            "baseline_vs_dhruva",
            "72h_polar_stress_test",
            "scenario_matrix",
            "forecast_model_metrics",
            "optimizer_execution",
            "safety_violation_reporting",
        ],
        "baseline_vs_dhruva": decision.get("baseline_comparison", {}),
        "decision": {
            "decision_id": decision.get("decision_id"),
            "planning_case": decision.get("planning_case"),
            "dynamic_reserve_percent": decision.get("dynamic_reserve_percent"),
            "decision": decision.get("decision"),
            "optimality_claim": decision.get("optimality_claim", False),
        },
        "stress_test_72h": {
            "success": stress.get("success", False),
            "events": stress.get("events", []),
            "metrics": stress.get("metrics", {}),
        },
        "scenario_matrix": matrix,
        "forecast_model_metrics": forecast_metrics,
        "optimizer_evidence": optimizer,
        "safety": safety_checks,
        "evidence_summary": {
            "scenario_count": len(matrix),
            "scenarios_without_critical_load_gap": sum(1 for x in matrix if x["critical_load_failure_steps"] == 0),
            "minimum_matrix_service_level_percent": round(min((x["service_level_percent"] for x in matrix), default=0.0), 3),
            "total_reported_safety_violations": safety_checks["matrix_critical_load_failures"] + safety_checks["stress_test_safety_violations"],
            "optimizer_execution_time_ms": optimizer["execution_time_ms"],
        },
        "limitations": [
            "Reference forecast and model metrics may use synthetic/reference training data; they are not field-calibrated Maitri measurements.",
            "P10/P50/P90-style uncertainty is an engineering band, not a calibrated probabilistic forecast interval.",
            "Optimizer output is bounded heuristic dispatch and explicitly makes no global-optimality claim.",
            "Scenario results are engineering simulations, not evidence of live station performance.",
        ],
        "station_state_mutated": False,
    }
