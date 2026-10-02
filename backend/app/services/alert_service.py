def generate_alerts(state, config):
    alerts = []
    if state.fuel.fuel_remaining_liters <= config.fuel.emergency_reserve_liters:
        alerts.append({"severity":"critical","type":"fuel_reserve","message":"Fuel is at or below emergency reserve."})
    elif state.fuel.fuel_remaining_liters <= config.fuel.emergency_reserve_liters * 2:
        alerts.append({"severity":"warning","type":"fuel_low","message":"Fuel is approaching emergency reserve."})
    if state.battery.soc_ratio <= config.simulation.safe_battery_reserve_ratio:
        alerts.append({"severity":"warning","type":"battery_low","message":"Battery SOC is at or below safe reserve."})
    if state.status.energy_status.value in ("deficit", "critical") or state.system.deficit_kw > 1e-6:
        alerts.append({"severity":"critical","type":"energy_deficit","message":"Available supply is insufficient for requested demand."})
    if state.weather.icing_factor < 0.7:
        alerts.append({"severity":"warning","type":"icing","message":"Icing is reducing renewable generation."})
    if state.weather.temperature_celsius < -35:
        alerts.append({"severity":"warning","type":"extreme_cold","message":"Extreme cold may increase heating and equipment stress."})
    if state.loads.shed_load_kw > 1e-6:
        alerts.append({"severity":"critical","type":"load_shedding","message":"One or more non-priority loads are being shed."})
    return alerts
