from fastapi import APIRouter, Query
from app.services.validation_engine import mission_validation_report

router = APIRouter(prefix="/validation", tags=["Validation & Evidence"])


@router.get("/mission-report")
def mission_report(hours: int = Query(72, ge=24, le=72)):
    """Generate a reproducible engineering evidence report without mutating the live twin."""
    return mission_validation_report(hours)
