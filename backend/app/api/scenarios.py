from fastapi import APIRouter, Query, HTTPException
from app.scenarios.engine import ScenarioEngine
from app.scenarios.models import ScenarioInput
from app.scenarios.what_if import run_scenario, wind_reduction, solar_reduction, extreme_temperature
from app.scenarios.simulator import ScenarioParameters, simulate_scenario
from app.ml.risk.risk_engine import assess_projection_risk
from app.services.ai_insights import generate_ai_insights
from app.api.twin import twin
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from datetime import datetime, timezone

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])

@router.get("/wind-reduction")
def wind(percent: float = Query(50, ge=0, le=100), days: float = Query(5, gt=0, le=7)):
    baseline = run_scenario("baseline", days)
    scenario = run_scenario(f"wind_-{percent}%", days, wind_reduction(percent))
    return {"baseline": baseline.__dict__, "scenario": scenario.__dict__}

@router.get("/solar-reduction")
def solar(percent: float = Query(50, ge=0, le=100), days: float = Query(5, gt=0, le=7)):
    baseline = run_scenario("baseline", days)
    scenario = run_scenario(f"solar_-{percent}%", days, solar_reduction(percent))
    return {"baseline": baseline.__dict__, "scenario": scenario.__dict__}

@router.get("/extreme-temperature")
def temperature(temp_celsius: float = Query(-40, ge=-80, le=10), days: float = Query(5, gt=0, le=7)):
    baseline = run_scenario("baseline", days)
    scenario = run_scenario(f"temperature_{temp_celsius}C", days, extreme_temperature(temp_celsius))
    return {"baseline": baseline.__dict__, "scenario": scenario.__dict__}

@router.get("/evaluate")
def evaluate(
    temperature: float = Query(0.0), wind_percent: float = Query(100.0, ge=0, le=100), solar_available: bool = True,
    load_percent: float = Query(100.0, ge=0), battery_health: float = Query(100.0, ge=0, le=100),
    diesel_available: bool = True, fuel_percent: float = Query(100.0, ge=0, le=100), resupply_delay_days: int = Query(0, ge=0),
):
    result = ScenarioEngine().evaluate(ScenarioInput(temperature=temperature, wind_percent=wind_percent,
        solar_available=solar_available, load_percent=load_percent, battery_health=battery_health,
        diesel_available=diesel_available, fuel_percent=fuel_percent, resupply_delay_days=resupply_delay_days))
    return result.__dict__

@router.get("/simulate")
def simulate(
    hours: int = Query(120, ge=1, le=168), wind_reduction_percent: float = Query(0, ge=0, le=100),
    solar_reduction_percent: float = Query(0, ge=0, le=100), temperature_override_celsius: float | None = Query(None, ge=-80, le=10),
    load_increase_percent: float = Query(0, ge=0, le=300), initial_soc_percent: float | None = Query(None, ge=0, le=100),
    initial_fuel_liters: float | None = Query(None, ge=0, le=20000), battery_health_percent: float = Query(100, ge=0, le=100),
    diesel_available: bool = True, resupply_delay_days: int = Query(0, ge=0),
):
    params = ScenarioParameters(name="custom", wind_reduction_percent=wind_reduction_percent,
        solar_reduction_percent=solar_reduction_percent, temperature_override_celsius=temperature_override_celsius,
        load_increase_percent=load_increase_percent, initial_soc_percent=initial_soc_percent,
        initial_fuel_liters=initial_fuel_liters, battery_health_percent=battery_health_percent,
        diesel_available=diesel_available, resupply_delay_days=resupply_delay_days)
    result = simulate_scenario(params, hours)
    assessment = assess_projection_risk(result["metrics"], result["points"])
    result["risk"] = assessment
    result["insights"] = generate_ai_insights(twin.state, assessment, {
        "renewable_share": result["metrics"]["renewable_share_percent"] / 100.0,
        "load_shed_energy_kwh": result["metrics"]["load_shed_energy_kwh"],
    })
    return result


@router.get("/resilience-matrix")
def resilience_matrix(hours: int = Query(72, ge=24, le=168)):
    scenarios = [
        ("DG1 FAILURE", {"diesel_available": False}),
        ("BATTERY FAILURE", {"battery_health_percent": 0}),
        ("RENEWABLE COLLAPSE", {"wind_reduction_percent": 80, "solar_reduction_percent": 80}),
        ("EXTREME COLD", {"temperature_override_celsius": -35, "load_increase_percent": 25}),
        ("FUEL SHORTAGE", {"initial_fuel_liters": 3600}),
        ("HIGH RESEARCH LOAD", {"load_increase_percent": 35}),
    ]
    out=[]
    # All resilience cases use the same reference weather/ML forecast. Generate it
    # once and share it across the baseline + six scenario simulations. This avoids
    # repeating the forecast-engine work for every case.
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    forecast_bundle = generate_multi_day_forecast(start, hours, base_temperature_celsius=-30.0, base_wind_speed_mps=8.0)
    baseline=simulate_scenario(ScenarioParameters(name="baseline"), hours, forecast_bundle=forecast_bundle)
    for name, kwargs in scenarios:
        case=simulate_scenario(ScenarioParameters(name=name, **kwargs), hours, forecast_bundle=forecast_bundle)
        m=case["metrics"]
        out.append({"name":name,"status":"PASS" if m["service_level_percent"] >= 99 and m["critical_load_failure_steps"] == 0 else "DEGRADED","service_level_percent":m["service_level_percent"],"load_shed_energy_kwh":m["load_shed_energy_kwh"],"minimum_soc_percent":m["minimum_soc_percent"],"fuel_remaining_liters":m["final_fuel_liters"],"fuel_delta_liters":m["fuel_consumed_liters"]-baseline["metrics"]["fuel_consumed_liters"],"average_generation_kw":m["average_generation_kw"]})
    return {"horizon_hours":hours,"source":"scenario_simulation","data_status":"ENGINEERING_MODEL","scenarios":out}


@router.get("/contingency-plan")
def contingency_plan(hours: int = Query(72, ge=24, le=168)):
    """Evaluate a backend-defined set of compound contingencies against one shared forecast."""
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    forecast_bundle = generate_multi_day_forecast(
        start, hours, base_temperature_celsius=-30.0, base_wind_speed_mps=8.0
    )
    baseline = simulate_scenario(
        ScenarioParameters(name="baseline"), hours, forecast_bundle=forecast_bundle
    )
    cases = [
        ("POWER ISLAND", "DG-01 unavailable + 60% renewable reduction",
         {"diesel_available": False, "wind_reduction_percent": 60, "solar_reduction_percent": 60}),
        ("BATTERY OUTAGE", "Battery unavailable + elevated load",
         {"battery_health_percent": 0, "load_increase_percent": 15}),
        ("WINTER HEAT STRESS", "Extreme cold + heating-driven load increase",
         {"temperature_override_celsius": -40, "load_increase_percent": 30}),
        ("FUEL LOGISTICS INTERRUPTION", "Reduced starting fuel + resupply delay",
         {"initial_fuel_liters": 3600, "resupply_delay_days": 5}),
        ("RENEWABLE DROUGHT", "Low wind + low solar",
         {"wind_reduction_percent": 80, "solar_reduction_percent": 80}),
        ("MULTI-SYSTEM STRESS", "Diesel unavailable + battery unavailable + high load",
         {"diesel_available": False, "battery_health_percent": 0, "load_increase_percent": 20}),
    ]
    out = []
    bm = baseline["metrics"]
    for name, description, kwargs in cases:
        result = simulate_scenario(
            ScenarioParameters(name=name, **kwargs),
            hours,
            forecast_bundle=forecast_bundle,
        )
        m = result["metrics"]
        out.append({
            "name": name,
            "description": description,
            "status": "PASS" if m["service_level_percent"] >= 99 and m["critical_load_failure_steps"] == 0 else "DEGRADED",
            "service_level_percent": m["service_level_percent"],
            "critical_load_failure_steps": m["critical_load_failure_steps"],
            "load_shed_energy_kwh": m["load_shed_energy_kwh"],
            "minimum_soc_percent": m["minimum_soc_percent"],
            "fuel_remaining_liters": m["final_fuel_liters"],
            "fuel_consumed_liters": m["fuel_consumed_liters"],
            "fuel_delta_liters": m["fuel_consumed_liters"] - bm["fuel_consumed_liters"],
            "autonomy_days": m.get("autonomy_days"),
            "recovery_time_hours": m.get("failure_duration_hours", 0),
        })
    return {
        "station": "Maitri Research Station",
        "horizon_hours": hours,
        "source": "scenario_simulation",
        "data_status": "ENGINEERING_MODEL",
        "forecast_source": "shared_reference_forecast",
        "baseline": {
            "service_level_percent": bm["service_level_percent"],
            "minimum_soc_percent": bm["minimum_soc_percent"],
            "fuel_remaining_liters": bm["final_fuel_liters"],
            "fuel_consumed_liters": bm["fuel_consumed_liters"],
        },
        "contingencies": out,
    }

@router.get("/compare")
def compare(
    hours: int = Query(120, ge=1, le=168), wind_reduction_percent: float = Query(0, ge=0, le=100),
    solar_reduction_percent: float = Query(0, ge=0, le=100), temperature_override_celsius: float | None = Query(None, ge=-80, le=10),
    load_increase_percent: float = Query(0, ge=0, le=300), initial_soc_percent: float | None = Query(None, ge=0, le=100),
    initial_fuel_liters: float | None = Query(None, ge=0, le=20000), battery_health_percent: float = Query(100, ge=0, le=100),
    diesel_available: bool = True, resupply_delay_days: int = Query(0, ge=0),
):
    base = simulate_scenario(ScenarioParameters(name="baseline"), hours)
    scenario = simulate_scenario(ScenarioParameters(name="scenario", wind_reduction_percent=wind_reduction_percent,
        solar_reduction_percent=solar_reduction_percent, temperature_override_celsius=temperature_override_celsius,
        load_increase_percent=load_increase_percent, initial_soc_percent=initial_soc_percent,
        initial_fuel_liters=initial_fuel_liters, battery_health_percent=battery_health_percent,
        diesel_available=diesel_available, resupply_delay_days=resupply_delay_days), hours)
    bm, sm = base["metrics"], scenario["metrics"]
    change = {
        "fuel_consumed_liters": sm["fuel_consumed_liters"] - bm["fuel_consumed_liters"],
        "minimum_soc_percent": sm["minimum_soc_percent"] - bm["minimum_soc_percent"],
        "final_fuel_liters": sm["final_fuel_liters"] - bm["final_fuel_liters"],
        "load_shed_energy_kwh": sm["load_shed_energy_kwh"] - bm["load_shed_energy_kwh"],
        "service_level_percent": sm["service_level_percent"] - bm["service_level_percent"],
        "autonomy_days": (sm["autonomy_days"] - bm["autonomy_days"]) if sm["autonomy_days"] is not None and bm["autonomy_days"] is not None else None,
    }
    return {"baseline": base, "scenario": scenario, "change": change}
