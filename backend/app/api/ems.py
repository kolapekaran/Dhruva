from fastapi import APIRouter, Query
from app.api.twin import twin
from app.database.schemas import state_to_dict
from app.digital_twin.station_twin import StationTwinInputs
from app.ems.controller import EMSController
from app.services.forecast_service import current_forecast, horizon_forecast
from app.optimization.optimizer import optimize_schedule, OptimizationWeights
from app.services.performance_cache import get_or_compute

router = APIRouter(prefix="/ems", tags=["EMS"] )
controller = EMSController()

@router.get("/dispatch")
def latest_dispatch():
    forecast = current_forecast()
    state = twin.state
    # Reconstruct the current physical input from the Twin weather state.
    inputs = StationTwinInputs(
        timestamp=state.time.timestamp,
        outdoor_temperature_celsius=state.weather.temperature_celsius,
        wind_speed_mps=state.weather.wind_speed_mps,
        solar_irradiance_w_m2=state.weather.solar_irradiance_w_m2,
        snowfall_rate=state.weather.snowfall_rate,
        wind_icing_factor=state.weather.icing_factor,
        battery_temperature_celsius=state.battery.battery_temperature_celsius,
    )
    command = controller.decide(inputs, state, forecast)
    return {"source":"closed_loop_ems", "forecast":forecast["prediction"], "dispatch":command.__dict__}

@router.post("/dispatch")
def dispatch_step(strategy_id: str | None = Query(None, pattern="^[A-D]$")):
    state = twin.state
    inputs = StationTwinInputs(
        timestamp=state.time.timestamp,
        outdoor_temperature_celsius=state.weather.temperature_celsius,
        wind_speed_mps=state.weather.wind_speed_mps,
        solar_irradiance_w_m2=state.weather.solar_irradiance_w_m2,
        snowfall_rate=state.weather.snowfall_rate,
        wind_icing_factor=state.weather.icing_factor,
        battery_temperature_celsius=state.battery.battery_temperature_celsius,
    )
    if strategy_id:
        forecast = horizon_forecast(1)["forecast"]
        weights = {
            "A": OptimizationWeights(cost=1, emissions=1, reliability=5, fuel=3, renewable=1),
            "B": OptimizationWeights(cost=1, emissions=1, reliability=5, fuel=4, renewable=2),
            "C": OptimizationWeights(cost=1, emissions=1, reliability=5, fuel=5, renewable=4),
            "D": OptimizationWeights(cost=1, emissions=1, reliability=5, fuel=6, renewable=5),
        }[strategy_id]
        plan = optimize_schedule(forecast, state, weights)
        row = plan["schedule"][0] if plan["schedule"] else {}
        command = controller.decide(inputs, state)
        command = command.__class__(
            battery_charge_kw=float(row.get("battery_charge_kw", command.battery_charge_kw)),
            battery_discharge_kw=float(row.get("battery_discharge_kw", command.battery_discharge_kw)),
            diesel_power_kw=float(row.get("diesel_kw", command.diesel_power_kw)),
            diesel_running=float(row.get("diesel_kw", 0)) > 0,
            reason=f"strategy_{strategy_id.lower()}_dispatch",
        )
    else:
        command = controller.decide(inputs, state)
    result = twin.step(StationTwinInputs(**{**inputs.__dict__,
        "battery_charge_request_kw": command.battery_charge_kw,
        "battery_discharge_request_kw": command.battery_discharge_kw,
        "diesel_power_request_kw": command.diesel_power_kw,
        "diesel_running": command.diesel_running}))
    return {"dispatch":command.__dict__, "strategy_id":strategy_id, "state":state_to_dict(result.state)}


@router.get("/strategy")
def strategy(hours: int = 24, cost_weight: float = 1.0, emission_weight: float = 1.0, reliability_weight: float = 5.0, fuel_weight: float = 3.0, renewable_weight: float = 1.0, min_reserve_percent: float = 20.0, soc_min_percent: float = 20.0, soc_max_percent: float = 95.0):
    s = twin.state
    key = ("strategy", int(hours), round(cost_weight,3), round(emission_weight,3), round(reliability_weight,3), round(fuel_weight,3), round(renewable_weight,3), round(min_reserve_percent,3), round(soc_min_percent,3), round(soc_max_percent,3), round(float(s.weather.temperature_celsius),3), round(float(s.weather.wind_speed_mps),3), round(float(s.weather.solar_irradiance_w_m2),1), round(float(s.loads.total_load_kw),3), round(float(s.battery.soc_ratio),4), round(float(s.fuel.fuel_remaining_liters),2))
    return get_or_compute(key, lambda: _strategy_uncached(hours, cost_weight, emission_weight, reliability_weight, fuel_weight, renewable_weight, min_reserve_percent, soc_min_percent, soc_max_percent), ttl_seconds=15.0)

def _strategy_uncached(hours: int = 24, cost_weight: float = 1.0, emission_weight: float = 1.0, reliability_weight: float = 5.0, fuel_weight: float = 3.0, renewable_weight: float = 1.0, min_reserve_percent: float = 20.0, soc_min_percent: float = 20.0, soc_max_percent: float = 95.0):
    """Unified read-only decision snapshot for the frontend."""
    state = twin.state
    forecast_bundle = horizon_forecast(hours)
    forecast = forecast_bundle["forecast"]
    option_weights = [
        ("A", "Diesel fleet", OptimizationWeights(cost=cost_weight, emissions=emission_weight, reliability=reliability_weight, fuel=fuel_weight, renewable=renewable_weight)),
        ("B", "Battery + diesel", OptimizationWeights(cost=cost_weight, emissions=emission_weight, reliability=reliability_weight, fuel=fuel_weight + 1, renewable=renewable_weight + 1)),
        ("C", "Renewable + battery + diesel", OptimizationWeights(cost=cost_weight, emissions=emission_weight, reliability=reliability_weight, fuel=fuel_weight + 2, renewable=renewable_weight + 3)),
        ("D", "Renewable + battery + heat recovery", OptimizationWeights(cost=cost_weight, emissions=emission_weight, reliability=reliability_weight, fuel=fuel_weight + 3, renewable=renewable_weight + 4)),
    ]
    options=[]
    plans_by_code={}
    for code,name,w in option_weights:
        result=optimize_schedule(forecast,state,w, min_reserve_ratio=min_reserve_percent/100.0, soc_min_ratio=soc_min_percent/100.0, soc_max_ratio=soc_max_percent/100.0)
        plans_by_code[code]=result
        summary=result["summary"]
        feasible=summary["service_level_percent"] >= 99.0 and summary["final_fuel_liters"] >= 0
        options.append({"id":code,"name":name,"feasible":feasible,"fuel_liters":round(summary["fuel_liters"],2),"service_level_percent":round(summary["service_level_percent"],2),"minimum_soc_percent":round(summary["minimum_soc_percent"],2),"renewable_share_percent":round(summary["renewable_share_percent"],2),"objective_value":round(summary["objective_value"],2)})
    feasible=[x for x in options if x["feasible"]]
    candidates=feasible or options
    # Map the operator's selected objective emphasis to the candidate policies.
    # The optimizer still determines feasibility/outcomes; this only chooses the policy family.
    objective_strength = cost_weight + emission_weight + reliability_weight + fuel_weight + renewable_weight
    if objective_strength <= 0.0:
        preferred_code = "A"
    elif renewable_weight >= max(fuel_weight, reliability_weight, cost_weight, emission_weight) and renewable_weight > 0:
        preferred_code = "D"
    elif fuel_weight >= max(reliability_weight, renewable_weight, cost_weight, emission_weight) and fuel_weight > 0:
        preferred_code = "C"
    elif reliability_weight > 0 and reliability_weight >= max(fuel_weight, renewable_weight):
        preferred_code = "B"
    else:
        preferred_code = "A"
    selected=next((x for x in candidates if x["id"]==preferred_code), min(candidates,key=lambda x:x["objective_value"]))
    selected_weights=dict((x[0],x[2]) for x in option_weights)[selected["id"]]
    selected_plan=plans_by_code[selected["id"]]
    schedule=selected_plan["schedule"]
    reserve=max(float(min_reserve_percent), min(30.0, float(min_reserve_percent)+(1.0-float(forecast[0].get("confidence",1.0)))*20.0)) if forecast else float(min_reserve_percent)
    first=schedule[0] if schedule else {}
    diesel=max(0.0,float(first.get("diesel_kw",0.0)))
    renewable=max(0.0,float(first.get("renewable_kw",0.0)))
    batt_dis=max(0.0,float(first.get("battery_discharge_kw",0.0)))
    batt_ch=max(0.0,float(first.get("battery_charge_kw",0.0)))
    heat_recovery_kwth=(diesel/0.38)*0.55*0.65 if diesel>0 else 0.0
    flexible_opportunity=max(0.0,state.loads.flexible_load_kw if reserve >= 20 else state.loads.flexible_load_kw*0.5)
    suggestions=[]
    if renewable > 0: suggestions.append("Prioritize available renewable generation before diesel energy.")
    if batt_ch > 0: suggestions.append(f"Use renewable surplus to charge the battery at up to {batt_ch:.1f} kW in the first horizon step.")
    if batt_dis > 0: suggestions.append(f"Use battery discharge ({batt_dis:.1f} kW first step) before increasing diesel output, subject to reserve limits.")
    if heat_recovery_kwth > 0: suggestions.append(f"Recover approximately {heat_recovery_kwth:.1f} kWth from diesel waste heat using the configured engineering model.")
    if flexible_opportunity > 0: suggestions.append(f"Consider shifting up to {flexible_opportunity:.1f} kW of flexible load when operationally acceptable.")
    baseline_fuel = float(options[0]["fuel_liters"]) if options else 0.0
    def legacy_option(o):
        code=o["id"]
        fuel_liters=float(o["fuel_liters"])
        fuel_delta=fuel_liters-baseline_fuel
        co2_delta=(fuel_delta/max(1e-9,baseline_fuel))*100.0
        first_plan=plans_by_code[code]
        first_row=first_plan["schedule"][0] if first_plan["schedule"] else {}
        first_batt_ch=max(0.0,float(first_row.get("battery_charge_kw",0.0)))
        first_batt_dis=max(0.0,float(first_row.get("battery_discharge_kw",0.0)))
        dispatch_schedule=[{
            "hourOffset": int(row.get("hour_offset", i)),
            "loadKw": round(float(row.get("load_kw", 0.0)), 2),
            "solarKw": round(float(row.get("solar_kw", 0.0)), 2),
            "windKw": round(float(row.get("wind_kw", 0.0)), 2),
            "renewableKw": round(float(row.get("renewable_kw", 0.0)), 2),
            "batteryChargeKw": round(float(row.get("battery_charge_kw", 0.0)), 2),
            "batteryDischargeKw": round(float(row.get("battery_discharge_kw", 0.0)), 2),
            "dieselKw": round(float(row.get("diesel_kw", 0.0)), 2),
            "socPercent": round(float(row.get("soc_percent", 0.0)), 2),
        } for i, row in enumerate(first_plan.get("schedule", []))]
        return {"id":f"strat-{code.lower()}","code":code,"name":o["name"],"description":f"Backend-generated feasible strategy: {o['name']}.","fuelConsumptionDeltaL":round(fuel_delta,2),"renewableUtilizationPercent":round(float(o.get("renewable_share_percent",0.0)),2),"reserveLevelPercent":reserve,"co2DeltaPercent":round(co2_delta,2),"confidencePercent":max(0.0,min(100.0,100.0-float(next((x.get('failure_probability',0) for x in forecast[:1]),0))*100.0)),"isRecommended":code==selected["id"],"generatorsOnline":["DG-01"] if float(first_row.get("diesel_kw",0))>0 else [],"batteryAction":"CHARGE" if first_batt_ch>0 else ("DISCHARGE" if first_batt_dis>0 else "HOLD"),"projectedFuelL":fuel_liters,"projectedFuel24hL":fuel_liters,"unservedLoadKw":max(0.0,100.0-float(o["service_level_percent"])),"dispatchSchedule":dispatch_schedule}
    legacy=[legacy_option(x) for x in options]
    recommended=next(x for x in legacy if x["code"]==selected["id"])
    return {"source":"closed_loop_ems","data_status":"ENGINEERING_MODEL","horizon_hours":hours,"selected":selected,"options":options,"dynamic_reserve_percent":reserve,"critical_load_protected":True,"optimality_claim":False,"battery_strategy":{"first_step_charge_kw":batt_ch,"first_step_discharge_kw":batt_dis,"minimum_soc_percent":selected["minimum_soc_percent"],"reserve_percent":reserve,"configured_soc_min_percent":soc_min_percent,"configured_soc_max_percent":soc_max_percent},"generator_strategy":{"first_step_diesel_kw":diesel,"dispatch_mode":"ON_DEMAND_WITH_N_PLUS_1_RESERVE","fleet_size":3,"standby_generators":max(0,3-(1 if diesel>0 else 0))},"heat_recovery":{"enabled":True,"first_step_recovered_heat_kwth":round(heat_recovery_kwth,2),"electrical_efficiency_ratio":0.38,"waste_heat_fraction":0.55,"heat_recovery_efficiency_ratio":0.65,"data_status":"ENGINEERING_MODEL"},"flexible_load":{"shiftable_kw":round(flexible_opportunity,2),"critical_load_protected":True},"energy_saving_opportunities":suggestions,"projected_outcomes":{"fuel_liters":selected["fuel_liters"],"service_level_percent":selected["service_level_percent"],"minimum_soc_percent":selected["minimum_soc_percent"],"renewable_share_percent":selected_plan["summary"]["renewable_share_percent"]},"recommendedStrategy":recommended,"alternativeStrategies":[x for x in legacy if x["code"]!=selected["id"]],"reasoningPoints":[
        {"icon":"ShieldCheck","title":"Feasibility","explanation":f"Selected strategy is feasible with {selected['service_level_percent']:.1f}% projected service and critical-load protection."},
        {"icon":"Battery","title":"Battery dispatch","explanation":f"First-step battery action is {'discharge' if batt_dis > 0 else 'charge' if batt_ch > 0 else 'idle'} at {max(batt_dis,batt_ch):.1f} kW while preserving a {reserve:.0f}% dynamic reserve."},
        {"icon":"Fuel","title":"Fuel outlook","explanation":f"Projected fuel use is {selected['fuel_liters']:.1f} L over the {hours}h horizon."},
        {"icon":"CloudSnow","title":"Forecast-aware planning","explanation":f"Renewable contribution is projected at {selected_plan['summary']['renewable_share_percent']:.1f}% over the optimization horizon."},
    ],"opportunities":[{"id":f"opp-{i+1}","title":title,"category":"BATTERY_TIMING" if "battery" in title.lower() else ("HEAT_RECOVERY" if "heat" in title.lower() else "LOAD_SHIFT"),"description":desc,"metricLabel":"Estimated action","metricValue":value,"potentialSavings":saving,"isApplied":False} for i,(title,desc,value,saving) in enumerate([(
        "Renewable-first dispatch", "Use available renewable energy before increasing diesel output.", f"{renewable:.1f} kW renewable", f"Fuel delta {legacy_option(selected).get('fuelConsumptionDeltaL',0):+.1f} L"),
        ("Battery timing", "Charge or discharge within configured SOC and reserve limits.", f"{max(batt_ch,batt_dis):.1f} kW", f"SOC floor {selected['minimum_soc_percent']:.1f}%"),
        ("Heat recovery", "Recover diesel waste heat for station thermal demand.", f"{heat_recovery_kwth:.1f} kWth", "Thermal offset")
    ])],"impactComparison":[{"strategyName":x["name"],"fuelLiters24h":x["fuel_liters"],"reservePercent":reserve,"renewableSharePercent":x["renewable_share_percent"]} for x in options],"predictedPeakLoadKw":max((float(x.get("load_kw",0)) for x in forecast),default=0),"predictedAvgWindMs":sum(float(x.get("wind_speed_mps",0)) for x in forecast)/max(1,len(forecast)),"predictedPeakSolarKw":max((float(x.get("solar_kw",0)) for x in forecast),default=0),"predictedMinTempC":min((float(x.get("temperature_celsius",0)) for x in forecast),default=0),"note":"Bounded heuristic decision support; not a global mathematical optimum."}
