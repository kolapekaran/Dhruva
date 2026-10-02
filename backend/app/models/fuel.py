from dataclasses import dataclass
from app.config import FuelTankConfig

@dataclass(frozen=True)
class FuelModelInputs:
    fuel_remaining_liters: float
    requested_consumption_liters: float

@dataclass(frozen=True)
class FuelModelResult:
    initial_fuel_liters: float
    actual_consumed_liters: float
    final_fuel_liters: float
    remaining_fraction: float
    reserve_liters: float
    above_reserve: bool
    reserve_reached: bool
    tank_empty: bool
    allowed_consumption_liters: float

def calculate_fuel(inputs: FuelModelInputs, config: FuelTankConfig) -> FuelModelResult:
    if inputs.fuel_remaining_liters < 0 or inputs.requested_consumption_liters < 0:
        raise ValueError("Fuel values must be non-negative")
    if not 0 <= config.emergency_reserve_liters <= config.tank_capacity_liters:
        raise ValueError("Invalid fuel reserve")
    initial = min(inputs.fuel_remaining_liters, config.tank_capacity_liters)
    actual = min(initial, inputs.requested_consumption_liters)
    final = max(0.0, initial - actual)
    return FuelModelResult(
        initial, actual, final, final / config.tank_capacity_liters,
        config.emergency_reserve_liters, final > config.emergency_reserve_liters,
        final <= config.emergency_reserve_liters, final <= 1e-9, initial
    )
