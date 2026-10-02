from dataclasses import dataclass
from app.config import DieselGeneratorConfig

@dataclass(frozen=True)
class DieselModelInputs:
    requested_power_kw: float
    timestep_seconds: int
    generator_running: bool

@dataclass(frozen=True)
class DieselModelResult:
    generator_running: bool
    requested_power_kw: float
    actual_power_kw: float
    fuel_rate_lph: float
    fuel_consumed_liters: float
    at_minimum_output: bool
    at_rated_output: bool

def simulate_diesel_step(inputs: DieselModelInputs, config: DieselGeneratorConfig) -> DieselModelResult:
    if inputs.requested_power_kw < 0 or inputs.timestep_seconds <= 0:
        raise ValueError("Invalid diesel inputs")
    if not 0 < config.minimum_power_kw <= config.rated_power_kw:
        raise ValueError("Invalid diesel power limits")
    if not inputs.generator_running:
        return DieselModelResult(False, inputs.requested_power_kw, 0.0, 0.0, 0.0, False, False)

    if inputs.requested_power_kw <= 0:
        actual = 0.0
    elif inputs.requested_power_kw < config.minimum_power_kw:
        actual = config.minimum_power_kw
    else:
        actual = min(inputs.requested_power_kw, config.rated_power_kw)

    rate = 0.0 if actual <= 0 else config.fuel_intercept_lph + config.fuel_slope_l_per_kwh * actual
    consumed = rate * inputs.timestep_seconds / 3600.0
    return DieselModelResult(
        True, inputs.requested_power_kw, actual, rate, consumed,
        0 < actual <= config.minimum_power_kw,
        actual >= config.rated_power_kw
    )
