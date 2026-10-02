from fastapi import APIRouter, Query
from app.api.twin import twin
from app.digital_twin.projection import run_projection
from app.ml.risk.risk_engine import assess_projection_risk
from app.ml.anomaly_detector import score_telemetry
from app.services.ai_insights import generate_ai_insights

router = APIRouter(prefix="/risk", tags=["Risk & AI"])

@router.get("")
def risk(hours: int = Query(24, ge=1, le=168)):
    projection = run_projection(twin.state.time.timestamp, hours,
                                 base_temperature_celsius=twin.state.weather.temperature_celsius,
                                 base_wind_speed_mps=twin.state.weather.wind_speed_mps,
                                 initial_state=twin.state)
    assessment = assess_projection_risk(projection.metrics, projection.points)
    return {"horizon_hours": hours, **assessment, "projection_metrics": projection.metrics}

@router.get("/anomaly")
def anomaly():
    s = twin.state
    return score_telemetry(s.loads.total_load_kw, s.system.renewable_generation_kw,
                           s.generation.diesel_power_kw, s.battery.soc_ratio,
                           s.fuel.fuel_remaining_liters)

@router.get("/insights")
def insights(hours: int = Query(24, ge=1, le=168)):
    projection = run_projection(twin.state.time.timestamp, hours,
                                 base_temperature_celsius=twin.state.weather.temperature_celsius,
                                 base_wind_speed_mps=twin.state.weather.wind_speed_mps,
                                 initial_state=twin.state)
    assessment = assess_projection_risk(projection.metrics, projection.points)
    return {"horizon_hours": hours, "risk": assessment, "insights": generate_ai_insights(twin.state, assessment, projection.metrics)}
