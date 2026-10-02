"""Multi-hour ML forecasting adapter.

This module turns a sequence of future weather inputs into validated hourly
load/solar/wind forecasts. It deliberately does not make EMS decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import math

from app.ml.inference.predictor import predict_many


@dataclass(frozen=True)
class WeatherForecastPoint:
    timestamp: datetime
    temperature_celsius: float
    wind_speed_mps: float
    solar_irradiance_w_m2: float = 0.0
    snowfall_rate: float = 0.0
    wind_icing_factor: float = 1.0
    solar_derate_factor: float = 1.0

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.wind_speed_mps < 0:
            raise ValueError("wind_speed_mps must be non-negative")
        if self.solar_irradiance_w_m2 < 0:
            raise ValueError("solar_irradiance_w_m2 must be non-negative")


@dataclass(frozen=True)
class ForecastPoint:
    timestamp: str
    hour_offset: int
    hour: float
    temperature_celsius: float
    wind_speed_mps: float
    load_kw: float
    solar_kw: float
    wind_kw: float
    renewable_kw: float
    anomaly: int
    failure: int
    failure_probability: float

    def to_dict(self) -> dict:
        return asdict(self)


def generate_forecast(weather_points: list[WeatherForecastPoint]) -> list[ForecastPoint]:
    """Run the existing ML predictor for each future weather point."""
    if not weather_points:
        raise ValueError("weather_points must not be empty")

    results: list[ForecastPoint] = []
    model_inputs = []
    for weather in weather_points:
        ts = weather.timestamp
        hour = ts.hour + ts.minute / 60.0 + ts.second / 3600.0
        model_inputs.append((weather.temperature_celsius, hour, weather.wind_speed_mps))

    predictions = predict_many(model_inputs)
    for offset, (weather, result) in enumerate(zip(weather_points, predictions)):
        ts = weather.timestamp
        hour = ts.hour + ts.minute / 60.0 + ts.second / 3600.0
        solar_kw = 0.0 if weather.solar_irradiance_w_m2 <= 0.0 else result.solar_kw * weather.solar_derate_factor
        wind_kw = result.wind_kw * weather.wind_icing_factor
        results.append(ForecastPoint(
            timestamp=ts.isoformat(),
            hour_offset=offset,
            hour=hour,
            temperature_celsius=weather.temperature_celsius,
            wind_speed_mps=weather.wind_speed_mps,
            load_kw=result.load_kw,
            solar_kw=max(0.0, solar_kw),
            wind_kw=max(0.0, wind_kw),
            renewable_kw=max(0.0, solar_kw + wind_kw),
            anomaly=result.anomaly,
            failure=result.failure,
            failure_probability=result.failure_probability,
        ))
    return results


def generate_reference_forecast(
    start_time: datetime,
    hours: int = 24,
    base_temperature_celsius: float = -30.0,
    base_wind_speed_mps: float = 8.0,
) -> list[ForecastPoint]:
    """Generate a deterministic reference weather trajectory for demos/tests.

    This is a placeholder input source, not an assertion of real Antarctic
    weather. Real weather forecasts can later provide the same point format.
    """
    if hours < 1 or hours > 168:
        raise ValueError("hours must be between 1 and 168")
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if base_wind_speed_mps < 0:
        raise ValueError("base_wind_speed_mps must be non-negative")

    points: list[WeatherForecastPoint] = []
    for offset in range(hours):
        ts = start_time + timedelta(hours=offset)
        phase = 2.0 * math.pi * (ts.hour - 6) / 24.0
        temp = base_temperature_celsius + 4.0 * math.sin(phase)
        wind = max(0.0, base_wind_speed_mps + 2.0 * math.sin(2.0 * math.pi * ts.hour / 24.0))
        daylight = max(0.0, math.sin(math.pi * (ts.hour - 4.0) / 16.0)) if 4 <= ts.hour <= 20 else 0.0
        irradiance = 650.0 * daylight
        points.append(WeatherForecastPoint(ts, temp, wind, irradiance))
    return generate_forecast(points)
