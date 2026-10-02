from fastapi import APIRouter, Query
from app.services.forecast_service import current_forecast, horizon_forecast

router = APIRouter(prefix="/forecasts", tags=["AI Forecasts"])


@router.get("")
def forecasts():
    return current_forecast()


@router.get("/horizon")
def forecasts_horizon(hours: int = Query(24, ge=1, le=168)):
    return horizon_forecast(hours)

@router.get("/multi-day")
def forecasts_multi_day(hours: int = Query(24, description="24, 72, or 168 hours", ge=24, le=168)):
    from app.ml.forecasting.multi_day import generate_multi_day_forecast, ALLOWED_HORIZONS_HOURS
    from app.api.twin import twin

    if hours not in ALLOWED_HORIZONS_HOURS:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="hours must be one of 24, 72, or 168")
    state = twin.state
    return generate_multi_day_forecast(
        start_time=state.time.timestamp,
        hours=hours,
        base_temperature_celsius=state.weather.temperature_celsius,
        base_wind_speed_mps=state.weather.wind_speed_mps,
    )
