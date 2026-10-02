from app.api.twin import twin
from app.digital_twin.projection import run_projection


def forecast_projection(hours: int = 24) -> dict:
    state = twin.state
    result = run_projection(
        state.time.timestamp,
        hours,
        base_temperature_celsius=state.weather.temperature_celsius,
        base_wind_speed_mps=state.weather.wind_speed_mps,
        initial_state=state,
    )
    return {
        "source": "forecast_driven_digital_twin",
        "synthetic_weather": True,
        "start_time": result.start_time,
        "horizon_hours": result.horizon_hours,
        "points": result.points,
        "metrics": result.metrics,
    }
