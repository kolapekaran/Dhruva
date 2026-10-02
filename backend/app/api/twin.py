from fastapi import APIRouter
from app.database.schemas import state_to_dict
from app.digital_twin.simulation import SimulationEngine, closed_loop_input_provider
from app.digital_twin.station_twin import StationTwin

router = APIRouter(prefix="/twin", tags=["Digital Twin"])
twin = StationTwin()
history = []

@router.get("/state")
def get_state():
    return state_to_dict(twin.state)

@router.post("/step")
def step():
    global history
    result = SimulationEngine(twin).run(twin.state.time.timestamp, 1, closed_loop_input_provider)[0].result
    history.append(result.state)
    return state_to_dict(result.state)

@router.get("/history")
def get_history(limit: int = 1440):
    return [state_to_dict(s) for s in history[-max(1, min(limit, 10000)):]]
