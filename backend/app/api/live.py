from __future__ import annotations
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dataclasses import replace
from datetime import timedelta
from app.api.twin import twin
from app.database.schemas import state_to_dict
from app.websocket.manager import ConnectionManager
from app.digital_twin.simulation import SimulationEngine, closed_loop_input_provider

router = APIRouter(tags=["Live Telemetry"])
manager = ConnectionManager()
_tick_lock = asyncio.Lock()
_last_tick = 0.0
TICK_SECONDS = 5

async def _advance_realtime_twin() -> None:
    """Advance the authoritative twin once per wall-clock tick, regardless of client count."""
    global _last_tick
    now = time.monotonic()
    async with _tick_lock:
        if now - _last_tick < TICK_SECONDS:
            return
        # The model timestep is explicitly 5 seconds so the UI changes continuously
        # without artificially jumping minutes ahead on every websocket message.
        next_timestamp = twin.state.time.timestamp + timedelta(seconds=TICK_SECONDS)
        def realtime_provider(step, timestamp, state):
            return replace(closed_loop_input_provider(step, next_timestamp, state), timestep_seconds=TICK_SECONDS)

        SimulationEngine(twin).run(next_timestamp, 1, realtime_provider)
        _last_tick = now

@router.websocket("/ws/live")
async def live_telemetry(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=TICK_SECONDS)
                if message.lower() in {"ping", "refresh", "state"}:
                    await _advance_realtime_twin()
                    await websocket.send_json(state_to_dict(twin.state))
            except asyncio.TimeoutError:
                await _advance_realtime_twin()
                await websocket.send_json(state_to_dict(twin.state))
    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket)
    finally:
        manager.disconnect(websocket)
