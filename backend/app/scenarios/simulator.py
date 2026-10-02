"""UI-oriented scenario simulation built on the Digital Twin.

This module deliberately keeps scenario manipulation outside the core Twin.
The Twin remains the physics authority; this layer only changes forecast/input
conditions and asks EMS to dispatch against them.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from app.config import STATION_CONFIG
from app.digital_twin.simulation import SimulationEngine
from app.digital_twin.station_twin import StationTwin, StationTwinInputs
from app.ems.controller import EMSController, DispatchCommand, validate_command
from app.ml.forecasting.multi_day import generate_multi_day_forecast


@dataclass(frozen=True)
class ScenarioParameters:
    name: str = "custom"
    wind_reduction_percent: float = 0.0
    wind_speed_override_mps: float | None = None
    solar_reduction_percent: float = 0.0
    temperature_override_celsius: float | None = None
    load_increase_percent: float = 0.0
    initial_soc_percent: float | None = None
    initial_fuel_liters: float | None = None
    battery_health_percent: float = 100.0
    diesel_available: bool = True
    resupply_delay_days: int = 0

    def validate(self) -> None:
        for name in ("wind_reduction_percent", "solar_reduction_percent"):
            value = getattr(self, name)
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.wind_speed_override_mps is not None and not 0 <= self.wind_speed_override_mps <= 40:
            raise ValueError("wind_speed_override_mps must be between 0 and 40")
        if self.load_increase_percent < 0:
            raise ValueError("load_increase_percent must be >= 0")
        if self.initial_soc_percent is not None and not 0 <= self.initial_soc_percent <= 100:
            raise ValueError("initial_soc_percent must be between 0 and 100")
        if self.initial_fuel_liters is not None and not 0 <= self.initial_fuel_liters <= STATION_CONFIG.fuel.tank_capacity_liters:
            raise ValueError("initial_fuel_liters is outside tank capacity")
        if not 0 <= self.battery_health_percent <= 100:
            raise ValueError("battery_health_percent must be between 0 and 100")
        if self.resupply_delay_days < 0:
            raise ValueError("resupply_delay_days must be >= 0")


def _provider(rows: list[dict], params: ScenarioParameters, ai_reoptimization: bool = True):
    controller = EMSController()
    wind_factor = 1.0 - params.wind_reduction_percent / 100.0
    solar_factor = 1.0 - params.solar_reduction_percent / 100.0
    load_factor = 1.0 + params.load_increase_percent / 100.0
    battery_factor = params.battery_health_percent / 100.0

    def provider(step: int, timestamp: datetime, state):
        row = rows[step]
        temp = float(row["temperature_celsius"])
        if params.temperature_override_celsius is not None:
            temp = params.temperature_override_celsius
        wind = max(0.0, float(row["wind_speed_mps"]) * wind_factor)
        if params.wind_speed_override_mps is not None:
            wind = params.wind_speed_override_mps
        irradiance = max(0.0, float(row.get("solar_irradiance_w_m2", 0.0)) * solar_factor)
        base = StationTwinInputs(
            timestamp=timestamp,
            outdoor_temperature_celsius=temp,
            wind_speed_mps=wind,
            solar_irradiance_w_m2=irradiance,
            battery_temperature_celsius=max(-10.0, temp + 8.0),
            critical_load_kw=STATION_CONFIG.loads.critical_load_kw * load_factor,
            important_load_kw=STATION_CONFIG.loads.important_load_kw * load_factor,
            flexible_load_kw=min(STATION_CONFIG.loads.max_flexible_load_kw, STATION_CONFIG.loads.flexible_load_kw * load_factor),
            timestep_seconds=3600,
        )
        if ai_reoptimization:
            command = controller.decide(base, state, forecast=row)
        else:
            # No-reoptimization mode holds the scenario twin's current dispatch
            # without invoking the closed-loop decision engine. The Twin still
            # applies the physical scenario disturbance and load-service rules.
            command = validate_command(DispatchCommand(
                battery_charge_kw=max(0.0, -float(state.battery.battery_power_kw)),
                battery_discharge_kw=max(0.0, float(state.battery.battery_power_kw)),
                diesel_power_kw=float(state.generation.diesel_power_kw),
                diesel_running=bool(state.system.diesel_running),
                reason="scenario_dispatch_held_without_reoptimization",
            ))
        # Scenario constraints are applied after EMS proposes a safe command.
        # If BESS availability is reduced, re-balance the remaining deficit with diesel
        # rather than silently creating an artificial load shed.
        battery_charge = command.battery_charge_kw * battery_factor
        battery_discharge = command.battery_discharge_kw * battery_factor
        diesel_power = command.diesel_power_kw
        diesel_running = command.diesel_running
        if command.battery_discharge_kw > 0 and battery_factor < 1.0:
            original_net_deficit = max(0.0, (float(row.get("load_kw", 0.0)) - float(row.get("wind_kw", 0.0)) - float(row.get("solar_kw", 0.0))))
            remaining_after_battery = max(0.0, original_net_deficit - battery_discharge)
            if params.diesel_available and remaining_after_battery > 0:
                diesel_power = max(diesel_power, min(STATION_CONFIG.diesel.rated_power_kw, remaining_after_battery))
                diesel_running = diesel_power > 0
        if not params.diesel_available:
            diesel_power = 0.0
            diesel_running = False
        command = replace(command, battery_charge_kw=battery_charge, battery_discharge_kw=battery_discharge, diesel_power_kw=diesel_power, diesel_running=diesel_running,
                          reason=("battery_unavailable_diesel_support" if battery_factor <= 0 and diesel_running else command.reason))
        return replace(
            base,
            battery_charge_request_kw=command.battery_charge_kw,
            battery_discharge_request_kw=command.battery_discharge_kw,
            diesel_power_request_kw=command.diesel_power_kw,
            diesel_running=command.diesel_running,
        )
    return provider


def _summarize(history, initial_fuel: float, hours: int) -> dict:
    if not history:
        raise ValueError("scenario produced no history")
    final = history[-1].result.state
    solar = sum(p.result.solar_power_kw for p in history)
    wind = sum(p.result.wind_power_kw for p in history)
    diesel = sum(p.result.diesel_power_kw for p in history)
    load = sum(p.result.total_load_kw for p in history)
    served = sum(p.result.state.loads.served_load_kw for p in history)
    shed = sum(p.result.state.loads.shed_load_kw for p in history)
    fuel_consumed = max(0.0, initial_fuel - final.fuel.fuel_remaining_liters)
    min_soc = min(p.result.state.battery.soc_ratio for p in history)
    critical_failures = sum(
        p.result.state.loads.critical_load_kw < STATION_CONFIG.loads.critical_load_kw - 1e-6
        for p in history
    )
    critical_served = sum(p.result.state.loads.critical_load_kw for p in history)
    critical_requested = STATION_CONFIG.loads.critical_load_kw * max(1, hours)
    renewable = solar + wind
    total_generation = renewable + diesel
    avg_diesel_lph = fuel_consumed / max(1.0, hours)
    autonomy_days = final.fuel.fuel_remaining_liters / avg_diesel_lph / 24.0 if avg_diesel_lph > 0 else None
    return {
        "horizon_hours": hours,
        "solar_energy_kwh": solar,
        "wind_energy_kwh": wind,
        "renewable_energy_kwh": renewable,
        "diesel_energy_kwh": diesel,
        "total_generation_kwh": total_generation,
        "average_generation_kw": total_generation / max(1.0, hours),
        "renewable_share_percent": 100.0 * renewable / max(1e-9, total_generation),
        "diesel_share_percent": 100.0 * diesel / max(1e-9, total_generation),
        "load_energy_kwh": load,
        "served_energy_kwh": served,
        "load_shed_energy_kwh": shed,
        "service_level_percent": 100.0 * served / max(1e-9, load),
        "fuel_consumed_liters": fuel_consumed,
        "initial_fuel_liters": initial_fuel,
        "final_fuel_liters": final.fuel.fuel_remaining_liters,
        "minimum_soc_percent": min_soc * 100.0,
        "final_soc_percent": final.battery.soc_ratio * 100.0,
        "diesel_runtime_hours": sum(p.result.state.system.diesel_running for p in history),
        "critical_load_failure_steps": int(critical_failures),
        "critical_load_coverage_percent": 100.0 * critical_served / max(1e-9, critical_requested),
        "fuel_reserve_reached": final.fuel.fuel_remaining_liters <= STATION_CONFIG.fuel.emergency_reserve_liters,
        "blackout_event": critical_failures > 0,
        "autonomy_days": autonomy_days,
    }


def simulate_scenario(params: ScenarioParameters, hours: int = 120, start_offset_hours: int = 0, forecast_bundle: dict | None = None, ai_reoptimization: bool = True) -> dict:
    params.validate()
    if not 1 <= hours <= 168:
        raise ValueError("hours must be between 1 and 168")
    if not 0 <= start_offset_hours <= 72:
        raise ValueError("start_offset_hours must be between 0 and 72")
    from datetime import timedelta
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=start_offset_hours)
    forecast = forecast_bundle if forecast_bundle is not None else generate_multi_day_forecast(
        start,
        hours,
        base_temperature_celsius=-30.0,
        base_wind_speed_mps=8.0,
    )
    if int(forecast.get("horizon_hours", hours)) < hours:
        raise ValueError("forecast_bundle horizon is shorter than requested simulation horizon")
    rows = forecast["forecast"]
    twin = StationTwin()
    if params.initial_soc_percent is not None:
        twin.state.battery.soc_ratio = params.initial_soc_percent / 100.0
    if params.initial_fuel_liters is not None:
        twin.state.fuel.fuel_remaining_liters = params.initial_fuel_liters
    initial_fuel = twin.state.fuel.fuel_remaining_liters
    history = SimulationEngine(twin).run(start, hours, _provider(rows, params, ai_reoptimization=ai_reoptimization))
    points = []
    for p in history:
        s = p.result.state
        points.append({
            "timestamp": s.time.timestamp.isoformat(),
            "hour_offset": s.time.simulation_step - 1,
            "solar_power_kw": p.result.solar_power_kw,
            "wind_power_kw": p.result.wind_power_kw,
            "diesel_power_kw": p.result.diesel_power_kw,
            "load_kw": p.result.total_load_kw,
            "served_load_kw": s.loads.served_load_kw,
            "shed_load_kw": s.loads.shed_load_kw,
            "battery_soc_percent": s.battery.soc_ratio * 100.0,
            "fuel_remaining_liters": s.fuel.fuel_remaining_liters,
            "outdoor_temperature_celsius": s.weather.temperature_celsius,
            "wind_speed_mps": s.weather.wind_speed_mps,
            "solar_irradiance_w_m2": s.weather.solar_irradiance_w_m2,
            "indoor_temperature_celsius": s.thermal.indoor_temperature_celsius,
            "energy_status": s.status.energy_status.value,
            "operating_mode": s.status.operating_mode.value,
        })
    metrics = _summarize(history, initial_fuel, hours)
    return {"scenario": params.__dict__, "points": points, "metrics": metrics, "ai_reoptimization_applied": bool(ai_reoptimization)}
