"""Forecast-driven Digital Twin projection and UI-ready resilience metrics."""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from app.config import STATION_CONFIG
from app.digital_twin.simulation import SimulationEngine
from app.digital_twin.station_twin import StationTwin, StationTwinInputs
from app.ems.controller import EMSController
from app.ml.forecasting.multi_day import generate_multi_day_forecast


@dataclass(frozen=True)
class ProjectionResult:
    start_time: str
    horizon_hours: int
    points: list[dict]
    metrics: dict


def _input_provider_from_forecast(forecast_rows: list[dict]):
    controller = EMSController()

    def provider(step: int, timestamp: datetime, state):
        row = forecast_rows[step]
        temp = float(row["temperature_celsius"])
        wind = float(row["wind_speed_mps"])
        irradiance = float(row.get("solar_irradiance_w_m2", 0.0))
        base = StationTwinInputs(
            timestamp=timestamp,
            outdoor_temperature_celsius=temp,
            wind_speed_mps=wind,
            solar_irradiance_w_m2=irradiance,
            battery_temperature_celsius=max(-10.0, temp + 8.0),
            timestep_seconds=3600,
        )
        command = controller.decide(base, state, forecast=row)
        return StationTwinInputs(
            **{**base.__dict__,
               "battery_charge_request_kw": command.battery_charge_kw,
               "battery_discharge_request_kw": command.battery_discharge_kw,
               "diesel_power_request_kw": command.diesel_power_kw,
               "diesel_running": command.diesel_running}
        )
    return provider


def run_projection(
    start_time: datetime,
    hours: int,
    base_temperature_celsius: float = -30.0,
    base_wind_speed_mps: float = 8.0,
    initial_state=None,
) -> ProjectionResult:
    if hours < 1 or hours > 8760:
        raise ValueError("hours must be between 1 and 8760")
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    # Build a forecast that is anchored to the authoritative current Twin.
    # The displayed +0h point is the actual current state; subsequent points are
    # a closed-loop projection starting from that exact state.
    forecast_hours = min(8760, hours + 1)
    forecast_bundle = generate_multi_day_forecast(
        start_time=start_time,
        hours=forecast_hours,
        base_temperature_celsius=base_temperature_celsius,
        base_wind_speed_mps=base_wind_speed_mps,
    )
    rows = forecast_bundle["forecast"]

    twin = StationTwin()
    if initial_state is not None:
        twin.state = deepcopy(initial_state)

    current_state = twin.state
    points: list[dict] = [{
        "timestamp": current_state.time.timestamp.isoformat(),
        "hour_offset": 0,
        "temperature_celsius": current_state.weather.temperature_celsius,
        "wind_speed_mps": current_state.weather.wind_speed_mps,
        "solar_power_kw": current_state.generation.solar_power_kw,
        "wind_power_kw": current_state.generation.wind_power_kw,
        "diesel_power_kw": current_state.generation.diesel_power_kw,
        "load_kw": current_state.loads.requested_load_kw,
        "served_load_kw": current_state.loads.served_load_kw,
        "shed_load_kw": current_state.loads.shed_load_kw,
        "critical_load_kw": current_state.loads.critical_load_kw,
        "battery_soc_ratio": current_state.battery.soc_ratio,
        "fuel_remaining_liters": current_state.fuel.fuel_remaining_liters,
        "indoor_temperature_celsius": current_state.thermal.indoor_temperature_celsius,
        "operating_mode": current_state.status.operating_mode.value,
        "energy_status": current_state.status.energy_status.value,
        "diesel_running": current_state.system.diesel_running,
        "battery_charge_kw": max(0.0, -current_state.battery.battery_power_kw),
        "battery_discharge_kw": max(0.0, current_state.battery.battery_power_kw),
        "confidence": 1.0,
        "data_status": "ENGINEERING_MODEL",
    }]

    # Simulate the requested future horizon from the real current state.
    # One extra forecast row is generated so the final state at +N hours can be
    # used for metrics, while the public series remains exactly N points (0..N-1).
    future_steps = max(0, min(hours, len(rows) - 1))
    future_rows = rows[1:future_steps + 1]
    projection_controller = EMSController()
    def provider(step: int, timestamp: datetime, state):
        row = future_rows[step]
        base = StationTwinInputs(
            timestamp=timestamp,
            outdoor_temperature_celsius=float(row["temperature_celsius"]),
            wind_speed_mps=float(row["wind_speed_mps"]),
            solar_irradiance_w_m2=float(row.get("solar_irradiance_w_m2", 0.0)),
            snowfall_rate=float(row.get("snowfall_rate", 0.0)),
            solar_derate_factor=float(row.get("solar_derate_factor", 1.0)),
            wind_icing_factor=float(row.get("wind_icing_factor", 1.0)),
            battery_temperature_celsius=max(-10.0, float(row["temperature_celsius"]) + 8.0),
            timestep_seconds=3600,
        )
        command = projection_controller.decide(base, state, forecast=row)
        return StationTwinInputs(**{**base.__dict__,
            "battery_charge_request_kw": command.battery_charge_kw,
            "battery_discharge_request_kw": command.battery_discharge_kw,
            "diesel_power_request_kw": command.diesel_power_kw,
            "diesel_running": command.diesel_running,
        })

    # Reuse one controller instance for the whole projection rather than
    # constructing a new EMS controller for every simulated hour.
    history = SimulationEngine(twin).run(start_time + timedelta(hours=1), future_steps, provider) if future_steps else []
    solar_kwh = wind_kwh = diesel_kwh = load_kwh = served_kwh = shed_kwh = 0.0
    battery_charge_kwh = battery_discharge_kwh = 0.0
    critical_failures = 0
    diesel_runtime_hours = 0.0
    min_soc = current_state.battery.soc_ratio
    initial_fuel = current_state.fuel.fuel_remaining_liters

    for idx, sim_point in enumerate(history, start=1):
        result = sim_point.result
        state = result.state
        row = future_rows[idx - 1]

        # Metrics cover the complete requested horizon, including the terminal
        # +N state. The public series intentionally remains N points (0..N-1),
        # so +N is retained for terminal metrics but not rendered as an extra UI point.
        solar_kwh += result.solar_power_kw
        wind_kwh += result.wind_power_kw
        diesel_kwh += result.diesel_power_kw
        load_kwh += result.total_load_kw
        served_kwh += state.loads.served_load_kw
        shed_kwh += state.loads.shed_load_kw
        battery_charge_kwh += result.battery_charge_kw
        battery_discharge_kwh += result.battery_discharge_kw
        min_soc = min(min_soc, state.battery.soc_ratio)
        diesel_runtime_hours += 1.0 if state.system.diesel_running else 0.0
        if state.loads.critical_load_kw + 1e-6 < STATION_CONFIG.loads.critical_load_kw:
            critical_failures += 1

        if idx >= hours:
            continue
        points.append({
            "timestamp": state.time.timestamp.isoformat(),
            "hour_offset": idx,
            "temperature_celsius": state.weather.temperature_celsius,
            "wind_speed_mps": state.weather.wind_speed_mps,
            "solar_power_kw": result.solar_power_kw,
            "wind_power_kw": result.wind_power_kw,
            "diesel_power_kw": result.diesel_power_kw,
            "load_kw": result.total_load_kw,
            "served_load_kw": state.loads.served_load_kw,
            "shed_load_kw": state.loads.shed_load_kw,
            "critical_load_kw": state.loads.critical_load_kw,
            "battery_soc_ratio": state.battery.soc_ratio,
            "fuel_remaining_liters": state.fuel.fuel_remaining_liters,
            "indoor_temperature_celsius": state.thermal.indoor_temperature_celsius,
            "operating_mode": state.status.operating_mode.value,
            "energy_status": state.status.energy_status.value,
            "diesel_running": state.system.diesel_running,
            "battery_charge_kw": result.battery_charge_kw,
            "battery_discharge_kw": result.battery_discharge_kw,
            "confidence": row.get("confidence", 0.0),
            "data_status": "ENGINEERING_MODEL",
        })

    final = history[-1].result.state if history else current_state
    renewable_kwh = solar_kwh + wind_kwh
    diesel_share = diesel_kwh / max(1e-9, renewable_kwh + diesel_kwh)
    renewable_share = renewable_kwh / max(1e-9, renewable_kwh + diesel_kwh)
    fuel_consumed = max(0.0, initial_fuel - final.fuel.fuel_remaining_liters)
    avg_diesel_lph = fuel_consumed / max(1e-9, hours)
    autonomy_hours = None if avg_diesel_lph <= 1e-9 else final.fuel.fuel_remaining_liters / avg_diesel_lph

    critical_risk = 50.0 if critical_failures else 0.0
    soc_risk = max(0.0, (STATION_CONFIG.battery.min_soc_ratio - min_soc) / max(1e-9, STATION_CONFIG.battery.min_soc_ratio)) * 30.0
    fuel_risk = max(0.0, (STATION_CONFIG.fuel.emergency_reserve_liters - final.fuel.fuel_remaining_liters) / max(1e-9, STATION_CONFIG.fuel.emergency_reserve_liters)) * 20.0
    blackout_risk = min(100.0, critical_risk + soc_risk + fuel_risk)

    metrics = {
        "initial_fuel_liters": initial_fuel,
        "final_fuel_liters": final.fuel.fuel_remaining_liters,
        "fuel_consumed_liters": fuel_consumed,
        "fuel_remaining_fraction": final.fuel.fuel_remaining_liters / STATION_CONFIG.fuel.tank_capacity_liters,
        "estimated_autonomy_hours": autonomy_hours,
        "estimated_autonomy_days": None if autonomy_hours is None else autonomy_hours / 24.0,
        "minimum_soc_ratio": min_soc,
        "final_soc_ratio": final.battery.soc_ratio,
        "solar_energy_kwh": solar_kwh,
        "wind_energy_kwh": wind_kwh,
        "renewable_energy_kwh": renewable_kwh,
        "diesel_energy_kwh": diesel_kwh,
        "renewable_share": renewable_share,
        "diesel_share": diesel_share,
        "load_energy_kwh": load_kwh,
        "served_energy_kwh": served_kwh,
        "load_shed_energy_kwh": shed_kwh,
        "battery_charge_energy_kwh": battery_charge_kwh,
        "battery_discharge_energy_kwh": battery_discharge_kwh,
        "diesel_runtime_hours": diesel_runtime_hours,
        "critical_load_failure_steps": critical_failures,
        "blackout_risk_percent": round(blackout_risk, 2),
        "fuel_reserve_reached": final.fuel.fuel_remaining_liters <= STATION_CONFIG.fuel.emergency_reserve_liters,
        "forecast_confidence": forecast_bundle["confidence"],
    }
    return ProjectionResult(start_time.isoformat(), hours, points, metrics)
