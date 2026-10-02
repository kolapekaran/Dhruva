from dataclasses import dataclass
from app.config import SolarPVConfig

@dataclass(frozen=True)
class SolarModelInputs:
    irradiance_w_m2: float
    ambient_temperature_celsius: float
    snow_ice_derate_factor: float = 1.0

@dataclass(frozen=True)
class SolarModelResult:
    solar_power_kw: float
    irradiance_ratio: float
    temperature_factor: float
    snow_ice_factor: float

def calculate_solar(inputs: SolarModelInputs, config: SolarPVConfig) -> SolarModelResult:
    if inputs.irradiance_w_m2 < 0:
        raise ValueError("Irradiance must be non-negative")
    factor = max(config.snow_ice_derate_min, min(config.snow_ice_derate_max, inputs.snow_ice_derate_factor))
    irradiance_ratio = inputs.irradiance_w_m2 / 1000.0
    temp_factor = 1.0 + (config.temperature_coefficient_percent_per_celsius / 100.0) * (
        inputs.ambient_temperature_celsius - 25.0
    )
    temp_factor = max(0.0, min(1.3, temp_factor))
    power = config.installed_capacity_kw * irradiance_ratio * temp_factor * factor
    power = max(0.0, min(config.installed_capacity_kw, power))
    return SolarModelResult(power, irradiance_ratio, temp_factor, factor)
