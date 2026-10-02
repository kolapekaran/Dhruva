def generate_recommendations(state, config):
    recs = []
    if state.battery.soc_ratio <= config.simulation.safe_battery_reserve_ratio:
        recs.append({"priority":"high","action":"preserve_battery","message":"Preserve battery reserve and avoid discretionary discharge."})
    if state.fuel.fuel_remaining_liters <= config.fuel.emergency_reserve_liters * 2:
        recs.append({"priority":"high","action":"conserve_fuel","message":"Conserve diesel fuel and avoid unnecessary generator runtime."})
    if state.loads.shed_load_kw > 0:
        recs.append({"priority":"high","action":"protect_critical_loads","message":"Reduce flexible demand and protect critical loads."})
    if state.system.surplus_kw > 0 and state.battery.soc_ratio < config.battery.max_soc_ratio:
        recs.append({"priority":"medium","action":"charge_battery","message":"Use renewable surplus to restore battery reserve."})
    if not recs:
        recs.append({"priority":"low","action":"normal_operation","message":"Maintain normal operation and reserve margins."})
    return recs
