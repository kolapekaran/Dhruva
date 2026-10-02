from fastapi import APIRouter, Query
from app.api.twin import twin
from app.config import STATION_CONFIG
from app.digital_twin.projection import run_projection
from app.ml.risk.risk_engine import assess_projection_risk
from app.services.alert_service import generate_alerts
from app.services.ai_insights import generate_ai_insights
from app.services.recommendation import generate_recommendations

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("")
def dashboard(hours: int = Query(24, ge=1, le=168)):
    s = twin.state
    projection = run_projection(s.time.timestamp, hours,
        base_temperature_celsius=s.weather.temperature_celsius,
        base_wind_speed_mps=s.weather.wind_speed_mps,
        initial_state=s)
    risk = assess_projection_risk(projection.metrics, projection.points)
    alerts = generate_alerts(s, STATION_CONFIG)
    recommendations = generate_recommendations(s, STATION_CONFIG)
    insights = generate_ai_insights(s, risk, projection.metrics)
    m = projection.metrics
    return {
        "timestamp": s.time.timestamp.isoformat(),
        "station": STATION_CONFIG.station.name,
        "status": {
            "operating_mode": s.status.operating_mode.value,
            "energy_status": s.status.energy_status.value,
        },
        "live": {
            "load_kw": s.loads.requested_load_kw,
            "served_load_kw": s.loads.served_load_kw,
            "renewable_power_kw": s.system.renewable_generation_kw,
            "solar_power_kw": s.generation.solar_power_kw,
            "wind_power_kw": s.generation.wind_power_kw,
            "diesel_power_kw": s.generation.diesel_power_kw,
            "battery_soc_percent": s.battery.soc_ratio * 100.0,
            "fuel_remaining_liters": s.fuel.fuel_remaining_liters,
            "indoor_temperature_celsius": s.thermal.indoor_temperature_celsius,
            "outdoor_temperature_celsius": s.weather.temperature_celsius,
        },
        "forecast": {
            "horizon_hours": hours,
            "renewable_share_percent": m["renewable_share"] * 100.0,
            "diesel_share_percent": m["diesel_share"] * 100.0,
            "fuel_consumed_liters": m["fuel_consumed_liters"],
            "minimum_soc_percent": m["minimum_soc_ratio"] * 100.0,
            "autonomy_days": m["estimated_autonomy_days"],
        },
        "risk": risk,
        "alerts": alerts,
        "recommendations": recommendations,
        "ai_insights": insights,
    }
