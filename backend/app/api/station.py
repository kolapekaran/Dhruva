from fastapi import APIRouter
from app.models.station import StationMetadata

router = APIRouter(prefix="/station", tags=["Station"])

@router.get("")
def station():
    return StationMetadata().__dict__
