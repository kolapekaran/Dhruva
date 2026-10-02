from fastapi import APIRouter
from app.api.twin import twin

router = APIRouter(prefix="/energy", tags=["Energy"])

@router.get("")
def energy():
    s = twin.state
    # The initial Twin state has no measured generation yet. Report the
    # instantaneous accounting deficit instead of incorrectly calling it balanced.
    generation = s.system.total_generation_kw
    load = s.loads.requested_load_kw
    power_balance = generation - load - s.system.battery_charging_kw
    surplus = max(power_balance, 0.0)
    deficit = max(-power_balance, 0.0)
    return {
        "timestamp": s.time.timestamp.isoformat(),
        "solar_power_kw": s.generation.solar_power_kw,
        "wind_power_kw": s.generation.wind_power_kw,
        "diesel_power_kw": s.generation.diesel_power_kw,
        "renewable_generation_kw": s.system.renewable_generation_kw,
        "total_generation_kw": s.system.total_generation_kw,
        "total_load_kw": s.loads.total_load_kw,
        "requested_load_kw": s.loads.requested_load_kw,
        "served_load_kw": s.loads.served_load_kw,
        "shed_load_kw": s.loads.shed_load_kw,
        "battery_soc_ratio": s.battery.soc_ratio,
        "battery_power_kw": s.battery.battery_power_kw,
        "power_balance_kw": power_balance,
        "surplus_kw": surplus,
        "deficit_kw": deficit,
    }

@router.get("/analysis")
def energy_analysis(hours: int = 24):
    from fastapi import HTTPException
    from app.services.projection_service import forecast_projection
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=422, detail="hours must be between 1 and 168")
    projection = forecast_projection(hours)
    return {
        "timestamp": projection["start_time"],
        "horizon_hours": hours,
        "metrics": projection["metrics"],
        "series": projection["points"],
    }
