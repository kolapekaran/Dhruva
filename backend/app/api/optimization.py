from fastapi import APIRouter, Query
from app.services.optimization_service import optimization_advisory
router=APIRouter(prefix='/optimization',tags=['Optimization'])
@router.get('')
def optimization(hours:int=Query(24,ge=1,le=168)): return optimization_advisory(hours)
