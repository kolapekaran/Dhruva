from dataclasses import dataclass
from app.config import WindTurbineConfig

@dataclass(frozen=True)
class WindModelInputs:
    wind_speed_mps: float
    icing_derate_factor: float = 1.0

@dataclass(frozen=True)
class WindModelResult:
    wind_power_kw: float
    ideal_power_kw: float
    icing_factor: float

def calculate_wind(inputs: WindModelInputs, config: WindTurbineConfig) -> WindModelResult:
    if inputs.wind_speed_mps < 0:
        raise ValueError("Wind speed must be non-negative")
    if not config.cut_in_wind_speed_mps < config.rated_wind_speed_mps < config.cut_out_wind_speed_mps:
        raise ValueError("Invalid wind power-curve limits")
    v = inputs.wind_speed_mps
    if v < config.cut_in_wind_speed_mps or v > config.cut_out_wind_speed_mps:
        ideal = 0.0
    elif v < config.rated_wind_speed_mps:
        x = (v - config.cut_in_wind_speed_mps) / (
            config.rated_wind_speed_mps - config.cut_in_wind_speed_mps
        )
        ideal = config.installed_capacity_kw * x**3
    else:
        ideal = config.installed_capacity_kw
    factor = max(config.icing_derate_min, min(config.icing_derate_max, inputs.icing_derate_factor))
    return WindModelResult(
        max(0.0, min(config.installed_capacity_kw, ideal * factor)),
        ideal, factor
    )
