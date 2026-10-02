def estimate_fuel_autonomy_hours(fuel_liters: float, consumption_lph: float):
    if fuel_liters < 0 or consumption_lph < 0:
        raise ValueError("Fuel and consumption must be non-negative")
    return None if consumption_lph == 0 else fuel_liters / consumption_lph

def fuel_summary(state, tank_capacity_liters: float, reserve_liters: float):
    rate = state.fuel.consumption_rate_lph
    hours = estimate_fuel_autonomy_hours(state.fuel.fuel_remaining_liters, rate)
    return {
        "fuel_remaining_liters": state.fuel.fuel_remaining_liters,
        "tank_capacity_liters": tank_capacity_liters,
        "reserve_liters": reserve_liters,
        "remaining_fraction": state.fuel.fuel_remaining_liters / tank_capacity_liters,
        "consumption_rate_lph": rate,
        "autonomy_hours": hours,
        "autonomy_days": None if hours is None else hours / 24,
        "reserve_reached": state.fuel.fuel_remaining_liters <= reserve_liters,
    }
