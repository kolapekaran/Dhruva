from fastapi import APIRouter
from app.api.twin import twin
from app.config import STATION_CONFIG
from app.services.fuel_service import fuel_summary

router = APIRouter(prefix="/fuel", tags=["Fuel"])

@router.get("")
def fuel():
    return fuel_summary(twin.state, STATION_CONFIG.fuel.tank_capacity_liters, STATION_CONFIG.fuel.emergency_reserve_liters)

@router.get("/projection")
def fuel_projection(hours: int = 168):
    from fastapi import HTTPException
    from app.services.projection_service import forecast_projection
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=422, detail="hours must be between 1 and 168")
    result = forecast_projection(hours)
    return {
        "horizon_hours": hours,
        "current_fuel_liters": result["metrics"]["initial_fuel_liters"],
        "projected_fuel_liters": result["metrics"]["final_fuel_liters"],
        "fuel_consumed_liters": result["metrics"]["fuel_consumed_liters"],
        "autonomy_days": result["metrics"]["estimated_autonomy_days"],
        "reserve_reached": result["metrics"]["fuel_reserve_reached"],
        "series": [
            {"timestamp": p["timestamp"], "fuel_remaining_liters": p["fuel_remaining_liters"], "diesel_power_kw": p["diesel_power_kw"]}
            for p in result["points"]
        ],
    }
