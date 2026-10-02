from app.api.twin import twin
from app.ml.inference.predictor import predict_from_twin_state
from app.ml.forecasting.forecast_engine import generate_reference_forecast


def current_forecast() -> dict:
    state = twin.state
    result = predict_from_twin_state(state)
    return {
        "timestamp": state.time.timestamp.isoformat(),
        "source": "integrated_ai_ml",
        "input": {
            "temperature_celsius": state.weather.temperature_celsius,
            "wind_speed_mps": state.weather.wind_speed_mps,
            "hour": state.time.timestamp.hour + state.time.timestamp.minute / 60.0,
        },
        "prediction": result.to_dict(),
    }


def horizon_forecast(hours: int = 24) -> dict:
    state = twin.state
    start_hour = state.time.timestamp.hour + state.time.timestamp.minute / 60.0
    rows = generate_reference_forecast(
        start_time=state.time.timestamp,
        hours=hours,
        base_temperature_celsius=state.weather.temperature_celsius,
        base_wind_speed_mps=state.weather.wind_speed_mps,
    )
    return {
        "source": "integrated_ai_ml",
        "horizon_hours": hours,
        "forecast": [row.to_dict() for row in rows],
    }
