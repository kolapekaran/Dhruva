from dataclasses import dataclass

TOLERANCE_KW = 1e-6

@dataclass(frozen=True)
class EnergyBalanceInputs:
    solar_power_kw: float
    wind_power_kw: float
    diesel_power_kw: float
    battery_discharge_kw: float
    battery_charge_kw: float
    total_load_kw: float

@dataclass(frozen=True)
class EnergyBalanceResult:
    total_generation_kw: float
    power_balance_kw: float
    surplus_kw: float
    deficit_kw: float
    is_balanced: bool

def calculate_energy_balance(inputs: EnergyBalanceInputs) -> EnergyBalanceResult:
    vals = vars(inputs)
    if any(v < -TOLERANCE_KW for v in vals.values()):
        raise ValueError("Energy-balance inputs must be non-negative")
    generation = (
        max(0.0, inputs.solar_power_kw)
        + max(0.0, inputs.wind_power_kw)
        + max(0.0, inputs.diesel_power_kw)
        + max(0.0, inputs.battery_discharge_kw)
    )
    balance = generation - max(0.0, inputs.battery_charge_kw) - max(0.0, inputs.total_load_kw)
    return EnergyBalanceResult(
        generation, balance, max(balance, 0.0), max(-balance, 0.0),
        abs(balance) <= TOLERANCE_KW
    )
