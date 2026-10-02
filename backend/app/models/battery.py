from dataclasses import dataclass
import math
from app.config import BatteryConfig

@dataclass(frozen=True)
class BatteryModelInputs:
    soc_ratio: float
    requested_charge_power_kw: float
    requested_discharge_power_kw: float
    timestep_seconds: int
    battery_temperature_celsius: float

@dataclass(frozen=True)
class BatteryModelResult:
    initial_soc_ratio: float
    final_soc_ratio: float
    initial_energy_kwh: float
    final_energy_kwh: float
    actual_charge_power_kw: float
    actual_discharge_power_kw: float
    charged_energy_kwh: float
    discharged_energy_kwh: float
    available_for_charge: bool
    available_for_discharge: bool
    temperature_in_range: bool

def simulate_battery_step(inputs: BatteryModelInputs, config: BatteryConfig) -> BatteryModelResult:
    if not 0 <= inputs.soc_ratio <= 1:
        raise ValueError("SOC must be in [0,1]")
    if inputs.requested_charge_power_kw < 0 or inputs.requested_discharge_power_kw < 0:
        raise ValueError("Battery requests must be non-negative")
    if inputs.requested_charge_power_kw > 0 and inputs.requested_discharge_power_kw > 0:
        raise ValueError("Battery cannot charge and discharge simultaneously")
    if inputs.timestep_seconds <= 0:
        raise ValueError("Timestep must be positive")
    if not 0 < config.round_trip_efficiency_ratio <= 1:
        raise ValueError("Invalid round-trip efficiency")
    if not 0 <= config.min_soc_ratio < config.max_soc_ratio <= 1:
        raise ValueError("Invalid SOC limits")
    if config.capacity_kwh <= 0:
        raise ValueError("Battery capacity must be positive")

    hours = inputs.timestep_seconds / 3600.0
    eta = math.sqrt(config.round_trip_efficiency_ratio)
    energy = inputs.soc_ratio * config.capacity_kwh
    initial_energy = energy
    temp_ok = config.minimum_operating_temperature_celsius <= inputs.battery_temperature_celsius <= config.maximum_operating_temperature_celsius
    charge = discharge = 0.0

    if temp_ok and inputs.requested_charge_power_kw > 0:
        headroom = max(0.0, config.max_soc_ratio * config.capacity_kwh - energy)
        charge = min(inputs.requested_charge_power_kw, config.max_charge_power_kw, headroom / eta / hours)
        energy += charge * hours * eta
    elif temp_ok and inputs.requested_discharge_power_kw > 0:
        available = max(0.0, energy - config.min_soc_ratio * config.capacity_kwh)
        discharge = min(inputs.requested_discharge_power_kw, config.max_discharge_power_kw, available * eta / hours)
        energy -= discharge * hours / eta

    final_soc = max(0.0, min(1.0, energy / config.capacity_kwh))
    return BatteryModelResult(
        inputs.soc_ratio, final_soc, initial_energy, energy,
        charge, discharge, charge * hours, discharge * hours,
        temp_ok and final_soc < config.max_soc_ratio - 1e-9,
        temp_ok and final_soc > config.min_soc_ratio + 1e-9,
        temp_ok
    )
