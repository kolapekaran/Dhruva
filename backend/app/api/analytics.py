from fastapi import APIRouter, Query
from app.api.twin import twin, history

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/history")
def history_analytics(limit: int = Query(1440, ge=1, le=10000)):
    rows = history[-limit:]
    if not rows:
        return {"count": 0, "series": [], "summary": {}}
    def avg(values):
        return sum(values) / len(values) if values else 0.0
    renewable = [s.system.renewable_generation_kw for s in rows]
    diesel = [s.generation.diesel_power_kw for s in rows]
    load = [s.loads.requested_load_kw for s in rows]
    served = [s.loads.served_load_kw for s in rows]
    fuel = [s.fuel.fuel_remaining_liters for s in rows]
    soc = [s.battery.soc_ratio for s in rows]
    return {
        "count": len(rows),
        "series": [{
            "timestamp": s.time.timestamp.isoformat(),
            "load_kw": s.loads.requested_load_kw,
            "served_load_kw": s.loads.served_load_kw,
            "shed_load_kw": s.loads.shed_load_kw,
            "solar_power_kw": s.generation.solar_power_kw,
            "wind_power_kw": s.generation.wind_power_kw,
            "renewable_power_kw": s.system.renewable_generation_kw,
            "diesel_power_kw": s.generation.diesel_power_kw,
            "battery_soc_percent": s.battery.soc_ratio * 100,
            "fuel_remaining_liters": s.fuel.fuel_remaining_liters,
            "indoor_temperature_celsius": s.thermal.indoor_temperature_celsius,
            "outdoor_temperature_celsius": s.weather.temperature_celsius,
        } for s in rows],
        "summary": {
            "average_load_kw": avg(load),
            "average_served_load_kw": avg(served),
            "average_renewable_power_kw": avg(renewable),
            "average_diesel_power_kw": avg(diesel),
            "minimum_soc_percent": min(soc) * 100,
            "maximum_soc_percent": max(soc) * 100,
            "fuel_start_liters": fuel[0],
            "fuel_end_liters": fuel[-1],
            "fuel_consumed_liters": max(0.0, fuel[0] - fuel[-1]),
            "load_shed_steps": sum(s.loads.shed_load_kw > 1e-6 for s in rows),
        },
    }
