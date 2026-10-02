from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.api.twin import twin
from app.config import STATION_CONFIG
from app.database.schemas import state_to_dict
from app.api.intelligence import _forecast
from app.api.ems import strategy as ems_strategy
from app.scenarios.simulator import ScenarioParameters, simulate_scenario
from app.ml.risk.risk_engine import assess_projection_risk
from app.services.ai_insights import generate_ai_insights
from app.digital_twin.projection import run_projection
from app.models.heating import HeatingModelInputs, calculate_heating
from app.services.performance_cache import get_or_compute

router = APIRouter(prefix="/api", tags=["Frontend Integration"])


def _snapshot(hour_offset: int = 0, strategy_result: dict | None = None):
    state = state_to_dict(twin.state)
    f = _forecast(max(72, hour_offset + 1))["forecast"]
    point = next((x for x in f if int(x.get("hour_offset", 0)) == hour_offset), f[min(len(f)-1, hour_offset)])
    projection_point = None
    if hour_offset > 0:
        # Future timeline state comes from the closed-loop Digital Twin projection,
        # not from a frontend-only interpolation. This keeps load, generation, SOC,
        # fuel and thermal state on the same backend trajectory.
        projection = run_projection(
            twin.state.time.timestamp,
            max(72, hour_offset + 1),
            base_temperature_celsius=twin.state.weather.temperature_celsius,
            base_wind_speed_mps=twin.state.weather.wind_speed_mps,
            initial_state=twin.state,
        )
        projection_point = next((x for x in projection.points if int(x.get("hour_offset", -1)) == hour_offset), None)
    s = twin.state
    strategy_horizon = max(24, min(72, hour_offset or 24))
    if strategy_result is None:
        strategy_result = ems_strategy(strategy_horizon)
    # Keep the frontend contract stable while deriving values from the authoritative Twin.
    # For a non-zero timeline offset, expose the selected forecast point as the displayed
    # predicted state so the time-machine controls visibly change the station state.
    is_future = hour_offset > 0
    diesel_now = float(getattr(s.generation, "diesel_power_kw", 0.0))
    wind_now = float(getattr(s.generation, "wind_power_kw", 0.0))
    solar_now = float(getattr(s.generation, "solar_power_kw", 0.0))
    load_now = float(getattr(s.loads, "requested_load_kw", 0.0))
    battery_now = float(getattr(s.battery, "battery_power_kw", 0.0))
    fuel = float(getattr(s.fuel, "fuel_remaining_liters", 0.0))
    soc = float(getattr(s.battery, "soc_ratio", 0.0)) * 100
    if is_future:
        projected = projection_point or {}
        load = max(0.0, float(projected.get("load_kw", point.get("load_kw", load_now))))
        wind = max(0.0, float(projected.get("wind_power_kw", point.get("wind_kw", wind_now))))
        solar = max(0.0, float(projected.get("solar_power_kw", point.get("solar_kw", solar_now))))
        # Reconcile the displayed future operating point before exposing it to the UI.
        # Projection values can contain a planned battery flow that, together with
        # renewable generation, would otherwise create an impossible generation
        # surplus. The backend remains authoritative; this is only the physical
        # balance closure for the selected projected state.
        residual_load = load - wind - solar
        projected_battery = float(projected.get("battery_discharge_kw", 0.0)) - float(projected.get("battery_charge_kw", 0.0))
        if residual_load <= 0.0:
            battery = residual_load  # absorb renewable surplus by charging
        else:
            battery = min(max(0.0, projected_battery), residual_load)
        diesel_required = residual_load - battery
        diesel = max(0.0, min(STATION_CONFIG.diesel.rated_power_kw, diesel_required))
        configured_reserve = float(strategy_result.get("battery_strategy", {}).get("configured_soc_min_percent", 20.0))
        confidence = float(projected.get("confidence", 1.0))
        if confidence > 1.0:
            confidence /= 100.0
        reserve = max(configured_reserve, min(30.0, configured_reserve + (1.0 - confidence) * 20.0))
        ts = str(projected.get("timestamp", point.get("timestamp", s.time.timestamp.isoformat())))
        soc = float(projected.get("battery_soc_ratio", soc / 100.0)) * 100.0
        fuel = float(projected.get("fuel_remaining_liters", fuel))
    else:
        diesel, wind, solar, load, battery = diesel_now, wind_now, solar_now, load_now, battery_now
        reserve = float(strategy_result.get("dynamic_reserve_percent", 20.0))
        ts = s.time.timestamp.isoformat()
    thermal_temp = float((projection_point or point).get("temperature_celsius", s.weather.temperature_celsius)) if is_future else float(s.weather.temperature_celsius)
    thermal_model = calculate_heating(HeatingModelInputs(
        outdoor_temperature_celsius=thermal_temp,
        indoor_temperature_celsius=float(getattr(s.thermal, "indoor_temperature_celsius", 20.0)),
        heating_electrical_power_kw=0.0,
        timestep_seconds=3600,
    ), STATION_CONFIG.heating)
    waste_heat_kwth = (diesel / 0.38) * 0.55 * 0.65 if diesel > 0 else 0.0
    recovered_heat_kwth = min(thermal_model.required_heating_power_kw, waste_heat_kwth)
    electrical_heating_kw = max(0.0, thermal_model.required_heating_power_kw - recovered_heat_kwth)

    generators = []
    for i in range(1, 4):
        generators.append({
            "id": f"DG-0{i}", "name": f"Diesel Generator {i}", "type": "Diesel Generator",
            "capacityKw": 150, "currentOutputKw": diesel if i == 1 and diesel > 0 else 0,
            "status": "ONLINE" if i == 1 and diesel > 0 else "STANDBY", "fuelConsumptionLhr": float(getattr(s.fuel, "consumption_rate_lph", 0.0)) if i == 1 and diesel > 0 else 0.0,
            "electricalEfficiency": 0.38, "runtimeHours": float(s.system.diesel_runtime_seconds)/3600,
            "healthPercent": float(s.generation.generator_health_percent), "nextMaintenanceHours": 0,
            "wasteHeatAvailableKw": 0, "isRecoveringHeat": i == 1 and diesel > 0,
        })
    base_components = [
        ("L-CRITICAL", "Critical Operations", "LIFE_SAFETY", "P0", float(getattr(s.loads, "critical_load_kw", 0.0))),
        ("L-IMPORTANT", "Research & Labs", "CRITICAL_RESEARCH", "P1", float(getattr(s.loads, "important_load_kw", 0.0))),
        ("L-FLEX", "Workshop & Utilities", "WORKSHOP_UTILITIES", "P2", float(getattr(s.loads, "flexible_load_kw", 0.0))),
        ("L-HEAT", "Heating", "HEATING", "P0", float(getattr(s.loads, "heating_load_kw", 0.0))),
    ]
    base_sum = sum(x[4] for x in base_components)
    scale = (load / base_sum) if is_future and base_sum > 0 else 1.0
    load_items = [(i,n,c,pr,v*scale) for i,n,c,pr,v in base_components]
    loads = [{"id": i, "name": n, "category": c, "priority": pr, "currentLoadKw": round(v, 3), "peakLoadKw": round(v, 3), "isFlexible": pr == "P2", "shedStatus": "SERVED" if v > 0 else "SERVED"} for i,n,c,pr,v in load_items if v > 0]
    # Keep the aggregate load and component loads consistent. If the configured
    # components do not sum to the aggregate, expose a balancing "Other Loads" row.
    component_sum = sum(x["currentLoadKw"] for x in loads)
    residual = max(0.0, load - component_sum)
    if residual > 0.001:
        loads.append({"id":"L-OTHER","name":"Other Loads","category":"SECONDARY","priority":"P2","currentLoadKw":round(residual,3),"peakLoadKw":round(residual,3),"isFlexible":True,"shedStatus":"SERVED"})
    total_gen = diesel + wind + solar
    efficiency = 100.0 * min(1.0, max(0.0, total_gen + max(0.0, battery)) / load) if load > 0 else 0.0
    return {
        "stationName": "Maitri Research Station", "selectedHourOffset": int(hour_offset), "location": "Schirmacher Oasis, Dronning Maud Land, Antarctica",
        "coordinates": {"lat": -70.7504583, "lng": 11.7170694}, "systemTime": ts, "mode": "LIVE",
        "weather": {
            "temperature": thermal_temp, "humidity": 0.0,
            "windSpeed": float(((projection_point or point).get("wind_speed_mps", s.weather.wind_speed_mps) if is_future else s.weather.wind_speed_mps)), "windDirection": "UNKNOWN",
            "visibilityKm": -1, "condition": "MODELLED", "solarRadiation": float(point.get("solar_irradiance_w_m2", s.weather.solar_irradiance_w_m2)),
            "cloudCover": float(getattr(s.weather, "cloud_cover_percent", 0)), "pressureHpa": float(getattr(s.weather, "pressure_hpa", 0)),
            "snowfallCm": float(getattr(s.weather, "snowfall_cm", 0)), "polarDayNight": "Polar Night",
            "provenance": "ENGINEERING MODEL", "lastUpdated": ts, "confidence": 100.0 * (1.0 - float(point.get("failure_probability", 0.0))),
        },
        "powerBalance": {
            "totalGenerationKw": diesel + wind + solar, "totalLoadKw": load, "netBalanceKw": diesel + wind + solar + battery - load,
            "dieselGenKw": diesel, "windGenKw": wind, "solarGenKw": solar, "batteryPowerKw": battery,
            "renewableSharePercent": 100 * (wind + solar) / max(1, diesel + wind + solar), "systemEfficiencyPercent": round(efficiency, 2),
        },
        "battery": {
            "capacityKwh": STATION_CONFIG.battery.capacity_kwh, "currentChargeKwh": soc / 100.0 * STATION_CONFIG.battery.capacity_kwh,
            "socPercent": soc, "currentPowerKw": battery, "status": "CHARGING" if battery < 0 else ("DISCHARGING" if battery > 0 else "IDLE"),
            "minSocPercent": STATION_CONFIG.battery.min_soc_ratio * 100.0, "maxSocPercent": STATION_CONFIG.battery.max_soc_ratio * 100.0,
            "temperatureC": float(getattr(s.battery, "battery_temperature_celsius", 0)), "healthPercent": float(getattr(s.battery, "state_of_health_percent", 0)),
            "cyclesCompleted": int(getattr(s.battery, "cycle_count", 0)),
        },
        "fuel": {"capacityLiters": 20000, "currentVolumeLiters": fuel, "fillPercent": 100*fuel/20000,
                 "currentConsumptionRateLhr": float(getattr(s.fuel, "consumption_rate_lph", 0)),
                 "estimatedAutonomyDays": (fuel/float(getattr(s.fuel,"consumption_rate_lph",0))/24) if float(getattr(s.fuel,"consumption_rate_lph",0)) > 0 else None,
                 "emergencyReserveLiters": STATION_CONFIG.fuel.emergency_reserve_liters, "lastDeliveryDaysAgo": 0, "nextScheduledDeliveryDays": 0},
        "thermal": {"indoorTemperatureC": float(getattr(s.thermal, "indoor_temperature_celsius", 20.0)), "outdoorTemperatureC": thermal_temp,
                     "totalHeatingDemandKw": round(thermal_model.required_heating_power_kw, 2), "recoveredHeatKw": round(recovered_heat_kwth, 2),
                     "electricalHeatingKw": round(electrical_heating_kw, 2), "heatRecoveryEfficiency": .65,
                     "heatRecoveryEnabled": recovered_heat_kwth > 0, "thermalOffsetPercent": round(100.0 * recovered_heat_kwth / max(1e-9, thermal_model.required_heating_power_kw), 1)},
        "reserve": {"currentReservePercent": reserve, "targetReservePercent": reserve, "spinningReserveKw": 0,
                     "status": "ADEQUATE", "drivers": {"windRisk":0,"snowfallRisk":0,"temperatureColdStress":0,"forecastConfidence":100.0 * (1.0 - float(point.get("failure_probability",0.0)))},
                     "reasoning": "; ".join(strategy_result.get("energy_saving_opportunities", [])) or "Derived from the backend forecast/EMS model."},
        "generators": generators,
        "renewables": [
            {"id":"WT-01","name":"Wind Turbines","type":"Wind Turbine","capacityKw":100,"currentOutputKw":wind,"status":"ONLINE","efficiencyPercent":0,"operatingMetrics":{"windSpeedOrIrradiance":float(s.weather.wind_speed_mps),"unit":"m/s"}},
            {"id":"PV-01","name":"Solar Array","type":"Solar Array","capacityKw":50,"currentOutputKw":solar,"status":"ONLINE","efficiencyPercent":0,"operatingMetrics":{"windSpeedOrIrradiance":float(s.weather.solar_irradiance_w_m2),"unit":"W/m²"}},
        ],
        "loads": loads,
        "decisionStrategy": strategy_result,
        "topRecommendation": {
            "title": str(strategy_result.get("recommendedStrategy", {}).get("name", "Strategy unavailable")),
            "description": str(strategy_result.get("recommendedStrategy", {}).get("description", "Backend strategy is unavailable.")),
            "urgency": "HIGH" if float(strategy_result.get("dynamic_reserve_percent", 20.0)) >= 28 else ("MEDIUM" if strategy_result.get("recommendedStrategy") else "LOW"),
            "confidencePercent": float(strategy_result.get("recommendedStrategy", {}).get("confidencePercent", 0.0)),
            "actionable": bool(strategy_result.get("recommendedStrategy")),
            "strategyCode": str(strategy_result.get("recommendedStrategy", {}).get("code", "")),
        },
        "horizonForecast": [
            {
                "hourOffset": int(x.get("hour_offset", 0)),
                "timestamp": x.get("timestamp", ts),
                "temperatureC": float(x.get("temperature_celsius", 0)),
                "windSpeedMs": float(x.get("wind_speed_mps", 0)),
                "solarIrradianceWm2": float(x.get("solar_irradiance_w_m2", 0)),
                "predictedTotalLoadKw": float(x.get("load_kw", 0)),
                "predictedWindKw": float(x.get("wind_power_kw", x.get("wind_kw", 0))),
                "predictedSolarKw": float(x.get("solar_power_kw", x.get("solar_kw", 0))),
                "predictedDieselKw": float(x.get("diesel_power_kw", 0)),
                "predictedBatteryKw": float(x.get("battery_discharge_kw", 0)) - float(x.get("battery_charge_kw", 0)),
                "batterySocPercent": float(x.get("battery_soc_ratio", soc / 100.0)) * 100.0,
                "fuelRemainingLiters": float(x.get("fuel_remaining_liters", fuel)),
                "dynamicReserveTargetPercent": max(float(strategy_result.get("battery_strategy", {}).get("configured_soc_min_percent", 20.0)), min(30.0, float(strategy_result.get("battery_strategy", {}).get("configured_soc_min_percent", 20.0)) + (1.0 - min(1.0, float(x.get("confidence", 1.0)))) * 20.0)),
                "confidencePercent": float(x.get("confidence", 0)) * 100.0 if float(x.get("confidence", 0)) <= 1.0 else float(x.get("confidence", 0)),
                "uncertaintyBandKw": 0,
                # Thermal recovery is derived from the same diesel waste-heat
                # engineering model used by the current-state thermal snapshot.
                # Keep it attached to each forecast point so the Energy tab can
                # integrate the forecast consistently instead of reporting 0 kWh.
                "heatRecoveryOffsetKw": round(
                    (float(x.get("diesel_power_kw", 0.0)) / 0.38) * 0.55 * 0.65
                    if float(x.get("diesel_power_kw", 0.0)) > 0 else 0.0,
                    3,
                ),
            }
            for x in (run_projection(s.time.timestamp, 73, base_temperature_celsius=s.weather.temperature_celsius, base_wind_speed_mps=s.weather.wind_speed_mps, initial_state=s).points)
            if int(x.get("hour_offset", 0)) in {0, 6, 12, 24, 48, 72}
        ],
        "provenance": {"weatherSource":"ENGINEERING MODEL","powerTelemetrySource":"ENGINEERING MODEL","forecastModelSource":"ML/REFERENCE","thermalModelSource":"ENGINEERING MODEL"},
    }

@router.get("/intelligence/snapshot")
def frontend_snapshot(hourOffset:int=Query(0, ge=0, le=72)):
    return _snapshot(hourOffset)


@router.get("/intelligence/strategy")
def frontend_strategy(
    hours:int=Query(24, ge=1, le=72),
    cost_weight:float=Query(1.0, ge=0),
    emission_weight:float=Query(1.0, ge=0),
    reliability_weight:float=Query(5.0, ge=0),
    fuel_weight:float=Query(3.0, ge=0),
    renewable_weight:float=Query(1.0, ge=0),
    min_reserve_percent:float=Query(20.0, ge=0, le=100),
    soc_min_percent:float=Query(20.0, ge=0, le=100),
    soc_max_percent:float=Query(95.0, ge=0, le=100),
):
    """Single frontend-facing strategy contract.

    The UI talks only to the integration adapter so strategy requests use the
    same /api namespace as the authoritative snapshot. The decision itself is
    still computed by the backend EMS engine; this route contains no frontend
    optimization logic.
    """
    if soc_min_percent > soc_max_percent:
        raise HTTPException(status_code=422, detail="soc_min_percent cannot exceed soc_max_percent")
    return ems_strategy(
        hours=hours,
        cost_weight=cost_weight,
        emission_weight=emission_weight,
        reliability_weight=reliability_weight,
        fuel_weight=fuel_weight,
        renewable_weight=renewable_weight,
        min_reserve_percent=min_reserve_percent,
        soc_min_percent=soc_min_percent,
        soc_max_percent=soc_max_percent,
    )

@router.get("/intelligence/resilience")
def frontend_resilience(hours:int=Query(24, ge=6, le=72), min_reserve_percent:float=Query(20.0, ge=10.0, le=35.0)):
    """Authoritative backend resilience view. All displayed risk/reserve values are derived here."""
    from app.api.scenarios import resilience_matrix
    s = twin.state
    key = ("resilience", int(hours), round(float(min_reserve_percent), 2), round(float(s.weather.temperature_celsius), 3), round(float(s.weather.wind_speed_mps), 3), round(float(s.weather.solar_irradiance_w_m2), 1), round(float(s.loads.total_load_kw), 3), round(float(s.battery.soc_ratio), 4), round(float(s.fuel.fuel_remaining_liters), 2), round(float(s.generation.generator_health_percent), 2))

    def _calculate():
        raw = resilience_matrix(hours)
        # Resilience risk/reserve calculations need forecast conditions, not a
        # closed-loop Digital Twin projection. Avoid running the much heavier
        # projection a second time merely to build the reserve chart.
        forecast = _forecast(hours)["forecast"]
        strategy = ems_strategy(min(72, hours), min_reserve_percent=min_reserve_percent)
        return raw, forecast, strategy

    raw, forecast, strategy = get_or_compute(key, _calculate, ttl_seconds=30.0)
    reserve_target = float(strategy.get("dynamic_reserve_percent", 20.0))
    current_reserve = float(reserve_target)
    minimum_reserve = 10.0

    scenarios = {}
    for x in raw["scenarios"]:
        scenarios[x["name"].lower().replace(" ", "-")] = {
            "scenarioId": x["name"], "title": x["name"], "description":"Backend scenario simulation",
            "failureDurationHours":hours, "totalGenerationKw":float(x.get("average_generation_kw",0.0)), "generationDeltaPercent":0.0,
            "fuelConsumptionLhr":float(x.get("fuel_consumed_liters",0))/max(1,hours), "fuelDeltaPercent":0, "batterySocMinPercent":x["minimum_soc_percent"],
            "reserveLevelPercent":reserve_target, "unservedLoadKw":x["load_shed_energy_kwh"], "criticalLoadCoveragePercent":float(x.get("critical_load_coverage_percent", x["service_level_percent"])),
            "resilienceOutcome":"OPTIMAL_RECOVERY" if x["status"]=="PASS" else "MITIGATED", "aiAnalysis":"Derived from backend scenario simulation.", "recommendedActions":[],"unservedLoadUnit":"kWh","data_status":"ENGINEERING_MODEL"
        }

    values = raw["scenarios"]
    avg_service = sum(float(x["service_level_percent"]) for x in values) / max(1, len(values))
    by_name = {x["name"]: x for x in values}
    fuel_case = by_name.get("FUEL SHORTAGE", {})
    metrics = {
        "powerReliability": round(avg_service, 2),
        "fuelSecurity": round(min(100.0, max(0.0, float(fuel_case.get("fuel_remaining_liters", 0.0)) / 20000.0 * 100.0)), 2),
        "generatorRedundancy": round(float(by_name.get("DG1 FAILURE", {}).get("service_level_percent", avg_service)), 2),
        "batteryAvailability": round(float(by_name.get("BATTERY FAILURE", {}).get("service_level_percent", avg_service)), 2),
        "renewableStability": round(float(by_name.get("RENEWABLE COLLAPSE", {}).get("service_level_percent", avg_service)), 2),
        "criticalLoadProtection": round(avg_service, 2),
    }
    overall = round(sum(metrics.values()) / len(metrics), 2)
    status = "GOOD" if overall >= 90 else ("WATCH" if overall >= 75 else "CRITICAL")

    # Backend-derived risk assessment for the next horizon.
    peak_wind = max([float(x.get("wind_speed_mps", 0)) for x in forecast] + [float(twin.state.weather.wind_speed_mps)])
    peak_load = max([float(x.get("load_kw", 0)) for x in forecast] + [float(twin.state.loads.total_load_kw)])
    current_load = max(1.0, float(twin.state.loads.total_load_kw))
    min_soc = min([float(x.get("battery_soc_ratio", 1.0)) * 100.0 for x in forecast] + [float(twin.state.battery.soc_ratio*100)])
    fuel_days = float(twin.state.fuel.fuel_remaining_liters) / max(1e-9, float(twin.state.fuel.consumption_rate_lph)) / 24 if twin.state.fuel.consumption_rate_lph > 0 else None
    failed_generators = 1 if float(getattr(twin.state.generation, 'generator_health_percent', 100.0)) < 80 else 0
    risk = [
        {"label":"Extreme Weather","level":"HIGH" if peak_wind >= 20 else ("MEDIUM" if peak_wind >= 12 else "LOW"),"source":"backend forecast"},
        {"label":"Generation Shortfall","level":"HIGH" if any(float(x.get("load_kw",0)) > float(x.get("wind_power_kw",0))+float(x.get("solar_power_kw",0))+float(x.get("diesel_power_kw",0))+float(x.get("battery_discharge_kw",0))-float(x.get("battery_charge_kw",0)) + 1e-6 for x in forecast) else "LOW","source":"backend forecast"},
        {"label":"Fuel Supply Risk","level":"HIGH" if fuel_days is not None and fuel_days < 5 else ("MEDIUM" if fuel_days is not None and fuel_days < 10 else "LOW"),"source":"backend fuel model"},
        {"label":"Equipment Failure","level":"MEDIUM" if failed_generators else "LOW","source":"backend asset state"},
        {"label":"Load Surge (Forecast)","level":"HIGH" if peak_load/current_load >= 1.35 else ("MEDIUM" if peak_load/current_load >= 1.15 else "LOW"),"source":"backend forecast"},
    ]
    # Coverage comes directly from the authoritative Twin. Do not call the
    # snapshot builder here: it regenerates a forecast and can invoke the
    # decision engine again, turning one resilience request into several expensive
    # computations.
    load_components = [
        ("Critical Operations", "P0", float(twin.state.loads.critical_load_kw)),
        ("Research & Labs", "P1", float(twin.state.loads.important_load_kw)),
        ("Workshop & Utilities", "P2", float(twin.state.loads.flexible_load_kw)),
        ("Heating", "P0", float(twin.state.loads.heating_load_kw)),
    ]
    coverage = []
    for name, priority, requested in load_components:
        if requested <= 0:
            continue
        served = requested if float(twin.state.loads.shed_load_kw) <= 0.001 else min(requested, float(twin.state.loads.served_load_kw))
        coverage.append({
            "name": name, "isProtected": served + 1e-6 >= requested, "priority": priority,
            "requestedKw": round(requested, 3), "servedKw": round(served, 3),
            "coveragePercent": round(100.0 * served / max(1e-9, requested), 1),
        })
    active_threats=[]
    # Keep threat cards tied to the specific backend indicators instead of
    # turning any single HIGH component into a HIGH composite-risk headline.
    # The composite risk index and individual threat severity answer different
    # operational questions and must remain visually distinct.
    for item in risk:
        if item["level"] in {"HIGH", "MEDIUM"}:
            active_threats.append({
                "title": item["label"],
                "severity": item["level"],
                "timing": f"next {hours}h",
                "description": f"{item["source"].capitalize()} indicates {item["level"].lower()} severity for this indicator.",
            })
    if peak_wind > float(twin.state.weather.wind_speed_mps):
        next_step = next((x for x in forecast if float(x.get("wind_speed_mps",0)) > float(twin.state.weather.wind_speed_mps)), None)
        if not any(t["title"] == "Wind increase expected" for t in active_threats):
            active_threats.append({"title":"Wind increase expected","severity":"MEDIUM","timing":f"+{int(next_step.get('hour_offset',6))}h" if next_step else "forecast horizon","description":f"Forecast peak wind {peak_wind:.1f} m/s."})
    proactive=["Maintain the backend-calculated dynamic reserve target", "Protect P0 life-safety loads during contingencies", "Review fuel resupply readiness before the emergency threshold is reached"]

    reserve_forecast=[]
    # forecast_projection is already the authoritative horizon used above; do not
    # run the same closed-loop projection a second time for the reserve chart.
    configured_reserve = float(strategy.get("battery_strategy", {}).get("configured_soc_min_percent", minimum_reserve))
    for x in forecast:
        offset = int(x.get("hour_offset", 0))
        if offset == 0 or offset % 12 == 0 or offset == hours:
            confidence = float(x.get("confidence", 1.0))
            if confidence > 1.0:
                confidence /= 100.0
            recommended = max(configured_reserve, min(30.0, configured_reserve + (1.0 - confidence) * 20.0))
            reserve_forecast.append({
                "hourOffset": offset,
                "currentPlanPercent": round(configured_reserve, 1),
                "recommendedPercent": round(recommended, 1),
                "minimumPercent": minimum_reserve,
            })

    current_rate=float(twin.state.fuel.consumption_rate_lph)
    current_autonomy_days=(float(twin.state.fuel.fuel_remaining_liters)/current_rate/24) if current_rate > 0 else None
    return {"overallScore":overall,"status":status,"metrics":metrics,"nPlusOneStatus":{"generators":f"{1 if twin.state.generation.diesel_power_kw > 0 else 0} online + {2 if twin.state.generation.diesel_power_kw > 0 else 3} standby","battery":"1 available + 0 standby" if twin.state.battery.soc_ratio > 0 else "Unavailable","windTurbines":"3 available + 0 standby" if twin.state.generation.wind_power_kw > 0 else "3 available + 0 standby (no current output)","solarArray":"1 available + 0 standby" if twin.state.generation.solar_power_kw > 0 else "1 available + 0 standby (no current output)"},"fuelSurvivalDays":current_autonomy_days,"criticalLoadCoverage":coverage,"activeThreats":active_threats,"recommendedProactiveActions":proactive,"scenarios":scenarios,"horizon":hours,"source":"scenario_simulation","dataStatus":"ENGINEERING_MODEL","riskAssessment":risk,"reserveForecast":reserve_forecast,"reserveSemantics":{"minimumPercent":minimum_reserve,"targetPercent":reserve_target,"currentPercent":current_reserve,"description":"Minimum reserve is the configured safety floor; target is the backend EMS dynamic target."}}

@router.post("/intelligence/resilience/re-evaluate")
def frontend_resilience_reevaluate(hours:int=Query(72, ge=6, le=72), min_reserve_percent:float=Query(20.0, ge=10.0, le=35.0)):
    return frontend_resilience(hours, min_reserve_percent)

class AssistantRequest(BaseModel):
    prompt: str

@router.post("/intelligence/resilience/simulate")
def frontend_resilience_simulate(req: dict):
    key = str(req.get("scenarioKey", "DG1 FAILURE"))
    hours = int(req.get("hours", 24))
    start_offset_hours = int(req.get("startOffsetHours", 0))
    mapping = {
        "DG1_FAILURE":{"diesel_available":False},
        "BATTERY_FAILURE":{"battery_health_percent":0},
        "RENEWABLE_COLLAPSE":{"wind_reduction_percent":80,"solar_reduction_percent":80},
        "EXTREME_COLD":{"temperature_override_celsius":-40,"load_increase_percent":35},
        "FUEL_SHORTAGE":{"initial_fuel_liters":3600},
        "HIGH_RESEARCH_LOAD":{"load_increase_percent":40},
        "STORM_HIGH_WIND":{"wind_speed_override_mps":28},
        "LOW_WIND":{"wind_speed_override_mps":2.5},
        "LOW_SOLAR":{"solar_reduction_percent":85},
        "MULTIPLE_FAILURES":{"diesel_available":False,"temperature_override_celsius":-38,"wind_reduction_percent":60},
    }
    params = dict(mapping.get(key, {}))
    # Custom scenarios use the same validated ScenarioParameters model.
    for field in ("wind_reduction_percent","wind_speed_override_mps","solar_reduction_percent","temperature_override_celsius","load_increase_percent","initial_soc_percent","initial_fuel_liters","battery_health_percent","diesel_available","resupply_delay_days"):
        if field in req and req[field] is not None:
            params[field] = req[field]
    ai_reoptimization = bool(req.get("aiReoptimization", True))
    result = simulate_scenario(ScenarioParameters(name=key, **params), hours, start_offset_hours=start_offset_hours, ai_reoptimization=ai_reoptimization)
    m=result["metrics"]
    points=result.get("points", [])
    avg_generation=(sum(float(p.get("solar_power_kw",0))+float(p.get("wind_power_kw",0))+float(p.get("diesel_power_kw",0)) for p in points)/max(1,len(points)))
    current_generation=float(twin.state.generation.solar_power_kw+twin.state.generation.wind_power_kw+twin.state.generation.diesel_power_kw)
    generation_delta=((avg_generation-current_generation)/current_generation*100.0) if current_generation>0 else 0.0
    current_rate=float(getattr(twin.state.fuel,"consumption_rate_lph",0.0))
    scenario_rate=float(m.get("fuel_consumed_liters",0.0))/max(1,hours)
    fuel_delta=((scenario_rate-current_rate)/current_rate*100.0) if current_rate>0 else 0.0
    reserve=float(ems_strategy(min(72,hours)).get("dynamic_reserve_percent",20.0))
    action_map = {
        "DG1_FAILURE":["Start/hold DG2 as standby support","Protect P0/P1 loads and preserve battery reserve","Recheck generator redundancy after recovery"],
        "BATTERY_FAILURE":["Keep diesel reserve available for renewable fluctuations","Protect critical loads and avoid discretionary load growth","Inspect BESS fault state before return to service"],
        "RENEWABLE_COLLAPSE":["Increase dispatchable generation readiness","Preserve battery SOC for short-term transients","Defer flexible loads during renewable deficit"],
        "EXTREME_COLD":["Prioritize heating and life-safety loads","Increase thermal recovery utilization where available","Maintain elevated reserve for cold-weather uncertainty"],
        "FUEL_SHORTAGE":["Protect emergency fuel reserve","Shift flexible loads into renewable-rich periods","Prepare resupply contingency"],
        "HIGH_RESEARCH_LOAD":["Coordinate research surge with renewable availability","Keep standby generation ready","Review flexible loads before shedding critical demand"],
        "STORM_HIGH_WIND":["Prepare for turbine cut-out at extreme wind","Preserve battery headroom for transient events","Keep diesel standby available"],
        "LOW_WIND":["Prepare dispatchable generation for reduced wind","Preserve battery reserve","Shift flexible loads where operationally acceptable"],
        "LOW_SOLAR":["Use wind and battery to absorb the solar shortfall","Avoid unnecessary diesel starts","Re-evaluate renewable availability as cloud cover changes"],
        "MULTIPLE_FAILURES":["Enter contingency operating posture","Protect P0 life-safety loads first","Restrict non-critical load and preserve fuel reserve"],
    }
    return {"scenarioId":key,"title":key.replace("_"," "),"description":"Backend cloned-Twin scenario simulation.","failureDurationHours":hours,
            "totalGenerationKw":round(avg_generation,2),"generationDeltaPercent":round(generation_delta,2),"fuelConsumptionLhr":round(scenario_rate,3),"fuelDeltaPercent":round(fuel_delta,2),
            "batterySocMinPercent":round(float(m.get("minimum_soc_percent",0)),2),"reserveLevelPercent":round(reserve,2),"unservedLoadKw":round(float(m.get("load_shed_energy_kwh",0)),3),
            "loadShedEnergyKwh":round(float(m.get("load_shed_energy_kwh",0)),3),
            "criticalLoadCoveragePercent":round(float(m.get("critical_load_coverage_percent", m.get("service_level_percent",0))),2),"resilienceOutcome":("CRITICAL_RISK" if m.get("critical_load_failure_steps",0)>0 else ("MITIGATED" if m.get("load_shed_energy_kwh",0)>0 else "OPTIMAL_RECOVERY")),
            "aiAnalysis": f"Scenario {key.replace('_', ' ').lower()} evaluated using the cloned Digital Twin and closed-loop EMS.","recommendedActions":action_map.get(key,["Review scenario outputs and maintain critical-load protection."]),"unservedLoadUnit":"kWh","data_status":"ENGINEERING_MODEL",
            "points": points, "aiReoptimizationApplied": bool(result.get("ai_reoptimization_applied", ai_reoptimization))}


@router.post("/intelligence/resilience/compare")
def frontend_resilience_compare(req: dict):
    """Compare a baseline and what-if trajectory using one shared ML forecast bundle."""
    scenario_key = str(req.get("scenarioKey", "LOW_WIND")).upper()
    hours = int(req.get("hours", 24))
    start_offset_hours = int(req.get("startOffsetHours", 0))
    ai_reoptimization = bool(req.get("aiReoptimization", True))
    if not 1 <= hours <= 168:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 168")
    if not 0 <= start_offset_hours <= 72:
        raise HTTPException(status_code=400, detail="startOffsetHours must be between 0 and 72")

    mapping = {
        "DG1_FAILURE": {"diesel_available": False},
        "BATTERY_FAILURE": {"battery_health_percent": 0},
        "RENEWABLE_COLLAPSE": {"wind_reduction_percent": 80, "solar_reduction_percent": 80},
        "EXTREME_COLD": {"temperature_override_celsius": -40, "load_increase_percent": 35},
        "FUEL_SHORTAGE": {"initial_fuel_liters": 3600},
        "HIGH_RESEARCH_LOAD": {"load_increase_percent": 40},
        "STORM_HIGH_WIND": {"wind_speed_override_mps": 28},
        "LOW_WIND": {"wind_speed_override_mps": 2.5},
        "LOW_SOLAR": {"solar_reduction_percent": 85},
        "MULTIPLE_FAILURES": {"diesel_available": False, "temperature_override_celsius": -38, "wind_reduction_percent": 60},
    }
    scenario_params = dict(mapping.get(scenario_key, {}))
    allowed = (
        "wind_reduction_percent", "wind_speed_override_mps", "solar_reduction_percent",
        "temperature_override_celsius", "load_increase_percent", "initial_soc_percent",
        "initial_fuel_liters", "battery_health_percent", "diesel_available", "resupply_delay_days"
    )
    for field in allowed:
        if field in req and req[field] is not None:
            scenario_params[field] = req[field]

    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=start_offset_hours)
    from app.ml.forecasting.multi_day import generate_multi_day_forecast
    forecast_bundle = generate_multi_day_forecast(
        start,
        hours,
        base_temperature_celsius=-30.0,
        base_wind_speed_mps=8.0,
    )

    scenario = simulate_scenario(
        ScenarioParameters(name=scenario_key, **scenario_params),
        hours,
        start_offset_hours=start_offset_hours,
        forecast_bundle=forecast_bundle,
        ai_reoptimization=ai_reoptimization,
    )
    baseline_params = {
        k: scenario_params[k]
        for k in ("initial_soc_percent", "initial_fuel_liters", "battery_health_percent", "diesel_available", "resupply_delay_days")
        if k in scenario_params
    }
    baseline = simulate_scenario(
        ScenarioParameters(name="BASELINE", **baseline_params),
        hours,
        start_offset_hours=start_offset_hours,
        forecast_bundle=forecast_bundle,
        ai_reoptimization=ai_reoptimization,
    )

    def pack(result: dict) -> dict:
        m = result["metrics"]
        return {
            "averageGenerationKw": round(float(m["average_generation_kw"]), 2),
            "fuelConsumedLiters": round(float(m["fuel_consumed_liters"]), 2),
            "fuelConsumptionLhr": round(float(m["fuel_consumed_liters"]) / max(1, hours), 3),
            "renewableSharePercent": round(float(m["renewable_share_percent"]), 2),
            "minimumSocPercent": round(float(m["minimum_soc_percent"]), 2),
            "finalSocPercent": round(float(m["final_soc_percent"]), 2),
            "finalFuelLiters": round(float(m["final_fuel_liters"]), 2),
            "loadShedEnergyKwh": round(float(m["load_shed_energy_kwh"]), 3),
            "criticalLoadCoveragePercent": round(float(m["critical_load_coverage_percent"]), 2),
            "serviceLevelPercent": round(float(m["service_level_percent"]), 2),
            "blackoutEvent": bool(m["blackout_event"]),
            "autonomyDays": None if m["autonomy_days"] is None else round(float(m["autonomy_days"]), 2),
            "points": result.get("points", []),
            "aiReoptimizationApplied": bool(result.get("ai_reoptimization_applied", False)),
        }

    b = pack(baseline)
    w = pack(scenario)
    delta = {
        "fuelConsumedLiters": round(w["fuelConsumedLiters"] - b["fuelConsumedLiters"], 2),
        "fuelConsumptionLhr": round(w["fuelConsumptionLhr"] - b["fuelConsumptionLhr"], 3),
        "renewableSharePercent": round(w["renewableSharePercent"] - b["renewableSharePercent"], 2),
        "minimumSocPercent": round(w["minimumSocPercent"] - b["minimumSocPercent"], 2),
        "finalFuelLiters": round(w["finalFuelLiters"] - b["finalFuelLiters"], 2),
        "loadShedEnergyKwh": round(w["loadShedEnergyKwh"] - b["loadShedEnergyKwh"], 3),
        "criticalLoadCoveragePercent": round(w["criticalLoadCoveragePercent"] - b["criticalLoadCoveragePercent"], 2),
        "averageGenerationKw": round(w["averageGenerationKw"] - b["averageGenerationKw"], 2),
    }
    return {
        "scenarioId": scenario_key,
        "title": scenario_key.replace("_", " "),
        "description": "Baseline and what-if trajectories evaluated against the same ML forecast bundle and closed-loop EMS.",
        "horizonHours": hours,
        "startOffsetHours": start_offset_hours,
        "baseline": b,
        "whatIf": w,
        "delta": delta,
        "forecastSource": forecast_bundle.get("source", "integrated_ai_ml_reference_weather"),
        "forecastSyntheticWeather": bool(forecast_bundle.get("synthetic_weather", False)),
        "forecastConfidence": forecast_bundle.get("confidence"),
        "dataStatus": "ENGINEERING_MODEL",
        "aiReoptimizationApplied": bool(ai_reoptimization),
    }

@router.post("/intelligence/assistant")
def frontend_assistant(req: AssistantRequest):
    from app.digital_twin.projection import run_projection
    s=twin.state
    prompt=req.prompt.lower().strip()
    load=s.loads.requested_load_kw
    gen=s.generation.solar_power_kw+s.generation.wind_power_kw+s.generation.diesel_power_kw
    balance=gen+s.battery.battery_power_kw-load
    facts=["Current values are from the authoritative Digital Twin.","Electrical values are ENGINEERING MODEL unless field telemetry is supplied."]

    if ("battery" in prompt and ("energy" in prompt or "balance" in prompt or "status" in prompt)):
        direction = "discharging" if s.battery.battery_power_kw > 0 else "charging" if s.battery.battery_power_kw < 0 else "idle"
        answer = (f"Current station balance is {balance:+.1f} kW with generation at {gen:.1f} kW and load at {load:.1f} kW. "
                  f"The battery is {direction} at {abs(s.battery.battery_power_kw):.1f} kW with SOC {s.battery.soc_ratio*100:.1f}%. "
                  f"Fuel remaining is {s.fuel.fuel_remaining_liters:.0f} L.")
        facts += ["Current power balance: authoritative Digital Twin", "Battery state: authoritative Digital Twin"]
    elif "dg-01" in prompt and "fail" in prompt:
        from app.api.scenarios import resilience_matrix
        matrix=resilience_matrix(24)
        case=next((x for x in matrix["scenarios"] if x["name"]=="DG1 FAILURE"), None)
        if case:
            answer=(f"If DG-01 fails for 24 hours, the backend contingency model projects "
                    f"{case['service_level_percent']:.1f}% service level and {case['load_shed_energy_kwh']:.1f} kWh of load-shed energy, "
                    f"with minimum battery SOC at {case['minimum_soc_percent']:.1f}%. Critical-load protection is evaluated by the same scenario engine.")
            facts += ["Scenario: DG1 FAILURE", "24 h cloned-Twin contingency simulation"]
        else:
            answer="The DG-01 failure contingency result is currently unavailable from the backend scenario engine."
    elif "heating" in prompt or "heat recovery" in prompt:
        thermal=_snapshot(0)["thermal"]
        answer=(f"Current engineering-model heating demand is {float(thermal['totalHeatingDemandKw']):.1f} kW, with {float(thermal['recoveredHeatKw']):.1f} kWth recovered from diesel waste heat. "
                f"That offsets {float(thermal['thermalOffsetPercent']):.0f}% of the modeled thermal demand.")
        facts += ["Thermal status: ENGINEERING_MODEL", "Recovery is derived from the configured diesel waste-heat model"]
    elif "reserve" in prompt:
        reserve_result=ems_strategy(24)
        target=float(reserve_result.get("dynamic_reserve_percent", 20.0))
        confidence=float(reserve_result.get("recommendedStrategy", {}).get("confidencePercent", 0.0))
        answer=(f"The current EMS strategy sets a dynamic reserve target of {target:.1f}%. "
                f"The strategy confidence is {confidence:.0f}%, and the controller is protecting critical load while accounting for the forecast horizon. "
                f"Current battery SOC is {s.battery.soc_ratio*100:.1f}% and station balance is {balance:+.1f} kW.")
        facts += ["Reserve target: EMS strategy", "Critical load protection: enabled"]
    elif "battery" in prompt:
        direction="discharging" if s.battery.battery_power_kw>0 else "charging" if s.battery.battery_power_kw<0 else "idle"
        answer=f"The battery is currently {direction} at {abs(s.battery.battery_power_kw):.1f} kW with SOC {s.battery.soc_ratio*100:.1f}%. Configured operating limits are {STATION_CONFIG.battery.min_soc_ratio*100:.0f}%–{STATION_CONFIG.battery.max_soc_ratio*100:.0f}%."
    elif "fuel" in prompt and ("24" in prompt or "consume" in prompt):
        projection=run_projection(s.time.timestamp,24,base_temperature_celsius=s.weather.temperature_celsius,base_wind_speed_mps=s.weather.wind_speed_mps,initial_state=s)
        consumed=projection.metrics['fuel_consumed_liters']
        answer=f"The 24-hour reference projection consumes approximately {consumed:.1f} L of fuel and ends with {projection.metrics['final_fuel_liters']:.0f} L remaining. This is an engineering-model projection, not a field-calibrated fuel forecast."
        facts += ["Horizon: 24 hours", "Projection status: ENGINEERING_MODEL"]
    elif "diesel" in prompt and ("increasing" in prompt or "tomorrow" in prompt or "forecast" in prompt):
        forecast = _forecast(24)["forecast"]
        first = forecast[:6]
        later = forecast[6:] or forecast
        first_avg = sum(float(x.get("diesel_power_kw", 0.0)) for x in first) / max(1, len(first))
        later_avg = sum(float(x.get("diesel_power_kw", 0.0)) for x in later) / max(1, len(later))
        renewable_first = sum(float(x.get("renewable_kw", 0.0)) for x in first) / max(1, len(first))
        renewable_later = sum(float(x.get("renewable_kw", 0.0)) for x in later) / max(1, len(later))
        load_first = sum(float(x.get("load_kw", 0.0)) for x in first) / max(1, len(first))
        load_later = sum(float(x.get("load_kw", 0.0)) for x in later) / max(1, len(later))
        delta_diesel = later_avg - first_avg
        direction = "increase" if delta_diesel > 0.5 else "decrease" if delta_diesel < -0.5 else "remain broadly stable"
        answer=(f"The 24-hour ML forecast projects diesel at {first_avg:.1f} kW on average in the first 6 hours and {later_avg:.1f} kW over the remaining horizon, so the forecast indicates diesel will {direction} rather than assuming an increase. "
                f"Forecast load moves from {load_first:.1f} to {load_later:.1f} kW while renewable generation moves from {renewable_first:.1f} to {renewable_later:.1f} kW. "
                f"POLAR treats the resulting diesel change as a forecast-driven dispatch response, not a standalone diesel command.")
        facts += ["Forecast: ML-backed 24 h horizon", "Dispatch interpretation: closed-loop EMS", "Forecast status: backend forecast bundle"]
    elif "risk" in prompt and ("24" in prompt or "biggest" in prompt or "next" in prompt):
        projection = run_projection(s.time.timestamp, 24, base_temperature_celsius=s.weather.temperature_celsius, base_wind_speed_mps=s.weather.wind_speed_mps)
        assessment = assess_projection_risk(projection.metrics, projection.points)
        components = assessment.get("components", {})
        ranked = sorted(components.items(), key=lambda item: float(item[1] or 0), reverse=True)
        top_name, top_value = ranked[0] if ranked else ("overall", assessment.get("overall_risk_percent", 0))
        label = top_name.replace("_risk_percent", "").replace("_", " ").title()
        answer=(f"For the next 24 hours, the backend risk engine reports an overall risk of {float(assessment.get('overall_risk_percent', 0)):.1f}% ({assessment.get('risk_level', 'UNKNOWN')}). "
                f"The highest component in this assessment is {label} at {float(top_value):.1f}%. "
                f"This is an advisory projection based on the current Digital Twin and forecast, not a field-certainty claim.")
        facts += ["Risk engine: backend projection", "Horizon: 24 hours", "Status: advisory projection"]
    elif "critical" in prompt and "load" in prompt:
        critical = float(s.loads.critical_load_kw)
        served = float(s.loads.served_load_kw)
        coverage = 100.0 if critical <= 0 else min(100.0, served / critical * 100.0)
        answer=(f"Critical load is {critical:.1f} kW and the current Twin reports {coverage:.0f}% critical-load coverage. "
                f"Current total requested load is {load:.1f} kW with {float(s.loads.shed_load_kw):.1f} kW shed. "
                f"The backend load model keeps critical demand protected before flexible demand when supply is constrained.")
        facts += ["Critical-load classification: Digital Twin", "Shedding state: backend load model"]
    elif "renewable" in prompt and ("forecast" in prompt or "tomorrow" in prompt or "next" in prompt):
        forecast = _forecast(24)["forecast"]
        renewable = [float(x.get("renewable_kw", 0.0)) for x in forecast]
        load_values = [float(x.get("load_kw", 0.0)) for x in forecast]
        share = 100.0 * sum(renewable) / max(1e-9, sum(load_values))
        peak = max(renewable, default=0.0)
        answer=(f"The next 24-hour forecast projects {share:.1f}% renewable contribution against forecast load, with peak renewable output of {peak:.1f} kW. "
                f"POLAR uses that forecast in the EMS dispatch and reserve calculation.")
        facts += ["Forecast: ML-backed 24 h horizon", "Used by: EMS dispatch + reserve planning"]
    elif "why" in prompt and ("strategy" in prompt or "recommendation" in prompt or "dispatch" in prompt):
        strategy = ems_strategy(24)
        selected = strategy.get("selected", {})
        points = strategy.get("reasoningPoints", [])
        answer=(f"POLAR selected {selected.get('name', 'the backend strategy')} for the 24-hour horizon. "
                f"Projected service is {float(selected.get('service_level_percent', 0)):.1f}%, renewable share is {float(selected.get('renewable_share_percent', 0)):.1f}%, and projected fuel use is {float(selected.get('fuel_liters', 0)):.1f} L. "
                f"The decision remains advisory and is generated by the closed-loop EMS optimizer.")
        facts += [str(p.get("title")) + ": " + str(p.get("explanation")) for p in points[:3]]
    elif "diesel" in prompt and "start" in prompt:
        if s.generation.diesel_power_kw>0:
            answer=f"DG dispatch is currently {s.generation.diesel_power_kw:.1f} kW. The current Twin load is {load:.1f} kW and renewable generation is {s.generation.solar_power_kw+s.generation.wind_power_kw:.1f} kW, so the dispatch controller is using diesel as part of the current supply balance."
        else:
            answer="DG-01 is not currently producing power in the authoritative Twin state."
    else:
        answer=(f"Current station state: generation {gen:.1f} kW, load {load:.1f} kW, balance {balance:+.1f} kW, "
                f"battery SOC {s.battery.soc_ratio*100:.1f}%, fuel {s.fuel.fuel_remaining_liters:.0f} L.")
    return {"answer":answer,"groundedFacts":facts}
