from fastapi import APIRouter
from app.api.twin import twin
from app.ml.ultimate_core import build_ultimate_ai_core

router = APIRouter(prefix='/intelligence', tags=['Ultimate AI'])

@router.get('/ultimate-ai')
def ultimate_ai():
    """Return the integrated model stack without mutating the authoritative twin."""
    return build_ultimate_ai_core(twin.state)
