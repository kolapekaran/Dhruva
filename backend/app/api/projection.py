from fastapi import APIRouter, Query
from app.services.projection_service import forecast_projection
from app.services.performance_cache import get_or_compute
from app.api.twin import twin

router = APIRouter(prefix="/projection", tags=["Forecast Projection"])


@router.get("")
def projection(hours: int = Query(24, ge=1, le=8760)):
    s = twin.state
    key = ("projection", int(hours), s.time.timestamp.isoformat(), round(float(s.weather.temperature_celsius), 3), round(float(s.weather.wind_speed_mps), 3), round(float(s.battery.soc_ratio), 4), round(float(s.fuel.fuel_remaining_liters), 2))
    return get_or_compute(key, lambda: forecast_projection(hours), ttl_seconds=30.0)
