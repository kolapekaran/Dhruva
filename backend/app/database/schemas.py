from dataclasses import asdict
from app.digital_twin.state import TwinState

def state_to_dict(state: TwinState):
    d = asdict(state)
    d["time"]["timestamp"] = state.time.timestamp.isoformat()
    d["status"]["operating_mode"] = state.status.operating_mode.value
    d["status"]["energy_status"] = state.status.energy_status.value
    return d
