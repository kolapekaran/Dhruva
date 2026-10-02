from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from app.digital_twin.station_twin import StationTwin, StationTwinInputs, StationTwinResult
from app.ems.controller import EMSController

@dataclass(frozen=True)
class SimulationPoint:
    result: StationTwinResult

class SimulationEngine:
    def __init__(self, twin: StationTwin | None = None):
        self.twin = twin or StationTwin()

    def run(self, start_time: datetime, steps: int, input_provider) -> list[SimulationPoint]:
        if steps <= 0:
            raise ValueError("steps must be positive")
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        history = []
        t = start_time
        for step in range(steps):
            inputs = input_provider(step, t, self.twin.state)
            result = self.twin.step(inputs)
            history.append(SimulationPoint(result))
            t += timedelta(seconds=inputs.timestep_seconds or self.twin.config.simulation.timestep_seconds)
        return history

def reference_input_provider(step: int, timestamp: datetime, state) -> StationTwinInputs:
    hour = timestamp.hour + timestamp.minute / 60.0
    solar = max(0.0, math.sin(math.pi * (hour - 6.0) / 12.0)) * 700.0 if 6 <= hour <= 18 else 0.0
    wind = 8.0 + 2.0 * math.sin(2 * math.pi * hour / 24.0)
    temp = -22.0 + 4.0 * math.sin(2 * math.pi * (hour - 6.0) / 24.0)
    return StationTwinInputs(
        timestamp=timestamp,
        outdoor_temperature_celsius=temp,
        wind_speed_mps=wind,
        solar_irradiance_w_m2=solar,
        snowfall_rate=0.0,
        solar_derate_factor=1.0,
        wind_icing_factor=1.0,
        battery_temperature_celsius=max(-10.0, temp + 8.0),
    )


def closed_loop_input_provider(step: int, timestamp: datetime, state) -> StationTwinInputs:
    base = reference_input_provider(step, timestamp, state)
    command = EMSController().decide(base, state)
    return StationTwinInputs(
        **{**base.__dict__,
           "battery_charge_request_kw": command.battery_charge_kw,
           "battery_discharge_request_kw": command.battery_discharge_kw,
           "diesel_power_request_kw": command.diesel_power_kw,
           "diesel_running": command.diesel_running}
    )
