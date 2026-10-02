from dataclasses import dataclass, replace
from datetime import datetime, timezone
from app.digital_twin.simulation import SimulationEngine, closed_loop_input_provider, reference_input_provider

@dataclass(frozen=True)
class ScenarioMetrics:
    name: str
    steps: int
    duration_hours: float
    renewable_energy_kwh: float
    diesel_energy_kwh: float
    load_energy_kwh: float
    deficit_energy_kwh: float
    fuel_consumed_liters: float
    minimum_soc_ratio: float
    final_soc_ratio: float
    minimum_fuel_liters: float
    final_fuel_liters: float
    diesel_runtime_hours: float
    autonomy_days: float | None

def _metrics(name, history, timestep_seconds):
    if not history:
        raise ValueError("Scenario produced no history")
    dt = timestep_seconds / 3600
    renewable = sum((p.result.solar_power_kw + p.result.wind_power_kw) * dt for p in history)
    diesel = sum(p.result.diesel_power_kw * dt for p in history)
    load = sum(p.result.total_load_kw * dt for p in history)
    deficit = sum(p.result.state.system.deficit_kw * dt for p in history)
    fuel = sum(p.result.fuel_consumed_liters for p in history)
    diesel_runtime = sum(p.result.state.system.diesel_running for p in history) * dt
    final = history[-1].result.state
    rate = final.fuel.consumption_rate_lph
    autonomy = final.fuel.fuel_remaining_liters / rate / 24 if rate > 0 else None
    return ScenarioMetrics(
        name, len(history), len(history) * dt, renewable, diesel, load, deficit, fuel,
        min(p.result.state.battery.soc_ratio for p in history),
        final.battery.soc_ratio,
        min(p.result.state.fuel.fuel_remaining_liters for p in history),
        final.fuel.fuel_remaining_liters,
        diesel_runtime, autonomy,
    )

def run_scenario(name: str, days: float, transform=None):
    steps = max(1, round(days * 24 * 3600 / 60))
    engine = SimulationEngine()
    def provider(step, timestamp, state):
        base = reference_input_provider(step, timestamp, state)
        if transform:
            base = transform(base, step)
        # Recompute dispatch after scenario changes so the Twin responds.
        from app.ems.controller import EMSController
        command = EMSController().decide(base, state)
        return replace(base, battery_charge_request_kw=command.battery_charge_kw,
                       battery_discharge_request_kw=command.battery_discharge_kw,
                       diesel_power_request_kw=command.diesel_power_kw,
                       diesel_running=command.diesel_running)
    history = engine.run(datetime(2026,1,1,tzinfo=timezone.utc), steps, provider)
    return _metrics(name, history, 60)

def wind_reduction(percent: float):
    factor = max(0.0, min(1.0, 1 - percent / 100))
    return lambda x, step: replace(x, wind_icing_factor=x.wind_icing_factor * factor)

def solar_reduction(percent: float):
    factor = max(0.0, min(1.0, 1 - percent / 100))
    return lambda x, step: replace(x, solar_derate_factor=x.solar_derate_factor * factor)

def extreme_temperature(temp_celsius: float):
    return lambda x, step: replace(x, outdoor_temperature_celsius=temp_celsius)
