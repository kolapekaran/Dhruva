from dataclasses import dataclass
from app.config import HeatingConfig

@dataclass(frozen=True)
class HeatingModelInputs:
    outdoor_temperature_celsius: float
    indoor_temperature_celsius: float
    heating_electrical_power_kw: float
    timestep_seconds: int

@dataclass(frozen=True)
class HeatingModelResult:
    heat_loss_kw: float
    required_heating_power_kw: float
    actual_heating_power_kw: float
    useful_heating_energy_kwh: float
    net_thermal_change_kwh: float
    next_indoor_temperature_celsius: float
    target_achieved: bool

def calculate_heating(inputs: HeatingModelInputs, config: HeatingConfig) -> HeatingModelResult:
    if inputs.heating_electrical_power_kw < 0 or inputs.timestep_seconds <= 0:
        raise ValueError("Invalid heating inputs")
    if not 0 < config.heating_efficiency_ratio <= 1:
        raise ValueError("Heating efficiency must be in (0,1]")
    if config.thermal_mass_kwh_per_celsius <= 0:
        raise ValueError("Thermal mass must be positive")

    hours = inputs.timestep_seconds / 3600.0
    heat_loss_kw = config.heat_loss_coefficient_kw_per_celsius * max(
        inputs.indoor_temperature_celsius - inputs.outdoor_temperature_celsius, 0.0
    )
    # Power required to offset losses and move toward the target during this timestep.
    target_gap_kwh = max(
        config.target_indoor_temperature_celsius - inputs.indoor_temperature_celsius, 0.0
    ) * config.thermal_mass_kwh_per_celsius
    required_power = (
        heat_loss_kw * hours + target_gap_kwh
    ) / hours / config.heating_efficiency_ratio

    actual = inputs.heating_electrical_power_kw
    useful = actual * hours * config.heating_efficiency_ratio
    net = useful - heat_loss_kw * hours
    next_temp = inputs.indoor_temperature_celsius + net / config.thermal_mass_kwh_per_celsius
    return HeatingModelResult(
        heat_loss_kw, required_power, actual, useful, net, next_temp,
        next_temp >= config.target_indoor_temperature_celsius - 1e-6
    )
