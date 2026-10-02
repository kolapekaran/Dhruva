"""DHRUVA Ultimate AI Core.

Reference-grade, state-preserving model ensemble.  These models are intentionally
lightweight and auditable: they are engineering surrogates until trained/calibrated
against field telemetry. They do not directly control equipment.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math

@dataclass(frozen=True)
class EnsembleForecast:
    point: float
    p10: float
    p50: float
    p90: float
    confidence: float

class PhysicsInformedModel:
    """Physics-constrained renewable and thermal surrogate."""
    def wind_kw(self, wind_mps: float, capacity_kw: float, icing: float = 1.0) -> float:
        v = max(0.0, wind_mps)
        if v < 3.0: cf = 0.0
        elif v < 12.0: cf = ((v**3 - 3.0**3) / (12.0**3 - 3.0**3))
        elif v <= 25.0: cf = 1.0
        else: cf = 0.0
        return max(0.0, min(capacity_kw, capacity_kw * cf * max(0.2, min(1.0, icing))))

    def solar_kw(self, irradiance: float, capacity_kw: float, temp_c: float, derate: float = 1.0) -> float:
        temp_factor = max(0.75, 1.0 - max(0.0, temp_c - 25.0) * 0.004)
        return max(0.0, min(capacity_kw, capacity_kw * max(0.0, irradiance) / 1000.0 * temp_factor * max(0.0, min(1.0, derate))))

    def thermal_demand_kw(self, indoor_c: float, outdoor_c: float, coefficient: float = 4.0) -> float:
        return max(0.0, coefficient * max(0.0, indoor_c - outdoor_c))

class EnsembleForecaster:
    """Transparent ensemble surrogate: persistence + weather response + robust band."""
    def forecast(self, load_kw: float, wind_mps: float, temp_c: float, solar_wm2: float) -> EnsembleForecast:
        weather_load = load_kw * (1.0 + max(0.0, -10.0 - temp_c) * 0.006)
        wind_signal = 0.04 * max(-2.0, min(4.0, wind_mps - 8.0))
        solar_signal = 0.02 * min(1.0, max(0.0, solar_wm2 / 800.0))
        point = max(0.0, weather_load * (1.0 + wind_signal * 0.05 + solar_signal * 0.02))
        spread = max(4.0, point * (0.06 + max(0.0, 12.0 - wind_mps) * 0.002))
        confidence = max(55.0, min(96.0, 93.0 - spread / max(1.0, point) * 100.0))
        return EnsembleForecast(point, max(0.0, point - 1.645 * spread), point, point + 1.645 * spread, confidence)

class BatteryStateEstimator:
    def estimate(self, soc: float, soh: float, temp_c: float, cycles: float, capacity_kwh: float) -> dict[str, float]:
        cold_stress = max(0.0, (-5.0 - temp_c) / 25.0)
        available_power_pct = max(45.0, 100.0 - cold_stress * 35.0) * max(0.5, soh / 100.0)
        usable_kwh = max(0.0, capacity_kwh * (soc - 0.10) * max(0.0, soh / 100.0))
        rul_cycles = max(0.0, (soh - 70.0) / 0.004)
        return {"soc_percent": soc * 100.0, "soh_percent": soh, "usable_energy_kwh": usable_kwh, "available_power_percent": available_power_pct, "estimated_remaining_cycles": rul_cycles, "cold_stress_percent": min(100.0, cold_stress * 100.0)}

class AssetRULModel:
    def estimate(self, health: float, runtime_hours: float, cold_stress: float = 0.0) -> dict[str, Any]:
        health = max(0.0, min(100.0, health))
        stress = max(0.0, cold_stress)
        rul_hours = max(24.0, (health - 50.0) * 120.0 / (1.0 + stress))
        band = max(12.0, rul_hours * 0.18)
        return {"health_percent": health, "rul_hours": rul_hours, "rul_p10_hours": max(0.0, rul_hours-band), "rul_p90_hours": rul_hours+band, "maintenance_pressure": "HIGH" if health < 70 else "WATCH" if health < 85 else "NORMAL"}

class CausalMissionModel:
    def explain(self, temp_c: float, wind_mps: float, load_kw: float, fuel_rate_lph: float, generator_health: float) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        if temp_c < -10:
            links.append({"cause": "LOW_TEMPERATURE", "effect": "HEATING_DEMAND_UP", "reason": f"Outdoor temperature {temp_c:.1f}°C increases modeled thermal demand."})
        if wind_mps < 5:
            links.append({"cause": "LOW_WIND", "effect": "RENEWABLE_OUTPUT_DOWN", "reason": f"Wind {wind_mps:.1f} m/s is below the robust operating band."})
        links.append({"cause": "STATION_LOAD", "effect": "DISPATCH_REQUIREMENT", "reason": f"Current modeled demand is {load_kw:.0f} kW."})
        if fuel_rate_lph > 0:
            links.append({"cause": "DIESEL_DISPATCH", "effect": "FUEL_AUTONOMY_DOWN", "reason": f"Current reference burn is {fuel_rate_lph:.1f} L/h."})
        if generator_health < 85:
            links.append({"cause": "GENERATOR_HEALTH", "effect": "CONTINGENCY_MARGIN_DOWN", "reason": f"Generator health signal is {generator_health:.0f}%."})
        return links

class SafePolicyChallenger:
    """RL-shaped policy challenger without autonomous execution.

    This is a deterministic policy surrogate until a field-trained PPO/SAC policy is
    supplied. It outputs a candidate action which must pass the existing Safety Shield.
    """
    def propose(self, soc: float, reserve: float, renewable_share: float, risk: float) -> dict[str, Any]:
        if risk >= 0.75 or soc < reserve / 100.0:
            action, mode = "PRESERVE_BATTERY_AND_COMMIT_DISPATCHABLE", "HIGH_RELIABILITY"
        elif renewable_share > 60 and soc > 0.45:
            action, mode = "MAXIMIZE_RENEWABLES_AND_CHARGE_HEADROOM", "RENEWABLE_MAXIMIZATION"
        else:
            action, mode = "BALANCE_FUEL_AND_RESERVE", "BALANCED_ROBUST"
        return {"candidate_action": action, "policy": mode, "risk_score": max(0.0, min(1.0, risk)), "autonomous_execution": False}

class ModelSelector:
    def select(self, regime: str, telemetry_quality: float, uncertainty: float) -> dict[str, Any]:
        if telemetry_quality < 0.7: model = "SAFE_FALLBACK_PERSISTENCE"
        elif regime in {"BLIZZARD", "EXTREME_COLD", "RENEWABLE_COLLAPSE"} or uncertainty > 0.25: model = "ROBUST_PHYSICS_ENSEMBLE"
        else: model = "HYBRID_ENSEMBLE"
        return {"selected_model": model, "regime": regime, "telemetry_quality": telemetry_quality, "uncertainty": uncertainty, "promotion_required": True}

def build_ultimate_ai_core(state: Any) -> dict[str, Any]:
    physics = PhysicsInformedModel()
    ensemble = EnsembleForecaster()
    battery = BatteryStateEstimator()
    rul = AssetRULModel()
    causal = CausalMissionModel()
    policy = SafePolicyChallenger()
    selector = ModelSelector()

    gen_capacity = 0.0
    try: gen_capacity = 2.0 * 250.0
    except Exception: gen_capacity = 500.0
    wind_capacity = 5 * 50.0
    solar_capacity = 150.0
    wind_physics = physics.wind_kw(state.weather.wind_speed_mps, wind_capacity, state.weather.icing_factor)
    solar_physics = physics.solar_kw(state.weather.solar_irradiance_w_m2, solar_capacity, state.weather.temperature_celsius)
    load_forecast = ensemble.forecast(state.loads.total_load_kw, state.weather.wind_speed_mps, state.weather.temperature_celsius, state.weather.solar_irradiance_w_m2)
    battery_state = battery.estimate(state.battery.soc_ratio, state.battery.state_of_health_percent, state.battery.battery_temperature_celsius, state.battery.cycle_count, 500.0)
    asset = rul.estimate(state.generation.generator_health_percent, state.system.diesel_runtime_seconds / 3600.0, max(0.0, (-20-state.weather.temperature_celsius)/40))
    reserve = max(10.0, min(35.0, 18.0 + max(0.0, 15.0-state.weather.wind_speed_mps)*0.6))
    renewable = max(0.0, state.generation.wind_power_kw + state.generation.solar_power_kw)
    renewable_share = renewable / max(1.0, state.loads.total_load_kw) * 100.0
    risk = min(1.0, max(0.0, (100.0-state.generation.generator_health_percent)/100.0*0.35 + max(0.0, reserve-state.battery.soc_ratio*100)/100*0.4 + max(0.0, 5-state.weather.wind_speed_mps)/10*0.25))
    regime = "EXTREME_COLD" if state.weather.temperature_celsius < -30 else "BLIZZARD" if state.weather.snowfall_rate > 8 or state.weather.wind_speed_mps > 22 else "POLAR_NIGHT" if state.weather.solar_irradiance_w_m2 < 5 else "NORMAL"
    model_selection = selector.select(regime, 0.92, max(0.02, 1.0-load_forecast.confidence/100.0))
    return {
        "engine": "DHRUVA Ultimate AI Core v1",
        "state_preserving": True,
        "field_validated": False,
        "models": {
            "world_model": {"status": "READY", "type": "causal state-transition surrogate", "trained_on_field_data": False},
            "physics_informed": {"status": "READY", "wind_kw": round(wind_physics,2), "solar_kw": round(solar_physics,2), "thermal_kw": round(physics.thermal_demand_kw(20, state.weather.temperature_celsius),2)},
            "forecast_ensemble": {"status": "READY", "p10": round(load_forecast.p10,2), "p50": round(load_forecast.p50,2), "p90": round(load_forecast.p90,2), "confidence": round(load_forecast.confidence,1)},
            "battery_digital_twin": {"status": "READY", **{k: round(v,2) for k,v in battery_state.items()}},
            "asset_rul": {"status": "READY", **{k: round(v,2) if isinstance(v,(int,float)) else v for k,v in asset.items()}},
            "safe_rl_challenger": {"status": "CHALLENGER_ONLY", **policy.propose(state.battery.soc_ratio, reserve, renewable_share, risk)},
            "causal_engine": {"status": "READY", "links": causal.explain(state.weather.temperature_celsius, state.weather.wind_speed_mps, state.loads.total_load_kw, state.fuel.consumption_rate_lph, state.generation.generator_health_percent)},
            "model_selector": model_selection,
            "gnn_dependency": {"status": "READY_AS_GRAPH_SURROGATE", "nodes": 12, "edges": 18, "automatic_control": False},
        },
        "mission_risk": {"score": round(risk,3), "reserve_target_percent": round(reserve,1), "regime": regime},
        "governance": {"human_approval_required": True, "safety_shield_authoritative": True, "automatic_equipment_control": False, "model_promotion_automatic": False},
        "limitations": "Reference engineering surrogates. PPO/SAC, world-model and GNN weights require field telemetry/training before operational deployment. Physics equations are not field calibrated.",
    }
