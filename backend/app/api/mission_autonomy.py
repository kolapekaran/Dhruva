from fastapi import APIRouter, Query
from app.ems.mission_autonomy import build_mission_autopilot

router = APIRouter(prefix='/intelligence', tags=['Mission Autonomy'])

@router.get('/mission-autopilot')
def mission_autopilot(
    hours: int = Query(168, ge=72, le=168),
    ensemble_members: int = Query(120, ge=50, le=1000),
):
    """Operator-supervised mission planning envelope; never mutates live state."""
    return build_mission_autopilot(hours, ensemble_members)
