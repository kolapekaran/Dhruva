from fastapi import APIRouter, Query
from app.api.twin import twin
from app.config import STATION_CONFIG
from app.services.alert_service import generate_alerts
from app.digital_twin.projection import run_projection
from app.ml.risk.risk_engine import assess_projection_risk

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("")
def alerts(hours: int = Query(24, ge=1, le=168)):
    current = generate_alerts(twin.state, STATION_CONFIG)
    projection = run_projection(twin.state.time.timestamp, hours,
                                base_temperature_celsius=twin.state.weather.temperature_celsius,
                                base_wind_speed_mps=twin.state.weather.wind_speed_mps,
                                initial_state=twin.state)
    risk = assess_projection_risk(projection.metrics, projection.points)
    projected = []
    if risk["components"]["battery_soc_risk_percent"] >= 20:
        projected.append({"severity": "warning", "type": "forecast_battery", "message": "Forecast indicates battery reserve pressure within the selected horizon."})
    if risk["components"]["fuel_reserve_risk_percent"] >= 20:
        projected.append({"severity": "warning", "type": "forecast_fuel", "message": "Forecast indicates fuel reserve pressure within the selected horizon."})
    if risk["components"]["critical_load_risk_percent"] > 0:
        projected.append({"severity": "critical", "type": "forecast_critical_load", "message": "Forecast indicates possible critical-load service loss."})
    if risk["components"]["extreme_weather_risk_percent"] >= 25:
        projected.append({"severity": "warning", "type": "forecast_weather", "message": "Forecast contains significant extreme-weather exposure."})
    return {
        "timestamp": twin.state.time.timestamp.isoformat(),
        "current": current,
        "projected": projected,
        "risk": risk,
        "total_active": len(current) + len(projected),
        "horizon_hours": hours,
    }
