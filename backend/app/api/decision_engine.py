from fastapi import APIRouter, Query
from app.api.twin import twin
from app.ems.decision_engine import build_decision_trace, run_72h_stress_test
from app.ems.intelligence_engine import fuel_autonomy, asset_health_context

router = APIRouter(prefix="/decision", tags=["DHRUVA Decision Engine"])

@router.get("/trace")
def decision_trace(hours: int = Query(24, ge=6, le=72)):
    return build_decision_trace(twin.state, hours)

@router.get("/stress-test/72h")
def stress_test_72h():
    return run_72h_stress_test(twin.state)

@router.get("/assessment")
def intelligence_assessment(hours: int = Query(24, ge=6, le=72)):
    # The decision trace owns the forecast/plan; this endpoint exposes the
    # Phase-2 intelligence in a compact contract for Analytics and operators.
    trace = build_decision_trace(twin.state, hours)
    return {
        "engine": "DHRUVA_INTELLIGENCE_ASSESSMENT_V2",
        "horizon_hours": hours,
        "data_status": trace.get("data_status", "ENGINEERING_MODEL"),
        "dynamic_reserve_percent": trace.get("dynamic_reserve_percent", 0.0),
        "uncertainty": trace.get("uncertainty", {}),
        "asset_health": asset_health_context(twin.state),
        "fuel_autonomy": trace.get("fuel_autonomy", fuel_autonomy(twin.state, [])),
        "planning_case": trace.get("planning_case", "P90_LOAD_P10_RENEWABLE"),
        "safety": trace.get("safety_validation", {}),
    }
