"""Multi-day forecast orchestration built on the existing ML predictor."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from app.ml.forecasting.forecast_engine import ForecastPoint, WeatherForecastPoint, generate_forecast
from app.ml.uncertainty.confidence import prediction_interval, confidence_summary

ALLOWED_HORIZONS_HOURS = (24, 72, 168)


def _reference_weather(start_time: datetime, hours: int, base_temperature_celsius: float, base_wind_speed_mps: float) -> list[WeatherForecastPoint]:
    if hours < 1 or hours > 8760: raise ValueError("hours must be between 1 and 8760")
    if base_wind_speed_mps < 0: raise ValueError("base_wind_speed_mps must be non-negative")
    if start_time.tzinfo is None: start_time=start_time.replace(tzinfo=timezone.utc)
    points=[]
    for offset in range(hours):
        ts=start_time+timedelta(hours=offset); hour=ts.hour+ts.minute/60.0
        # Reference Antarctic seasonal daylight envelope. It intentionally models
        # polar night/day rather than assuming a 24h conventional solar cycle.
        month=ts.month
        daylight_hours={1:24,2:22,3:18,4:8,5:0,6:0,7:0,8:0,9:8,10:16,11:22,12:24}[month]
        if daylight_hours>=24:
            daylight=1.0
        elif daylight_hours<=0:
            daylight=0.0
        else:
            center=12.0; half=daylight_hours/2
            distance=abs(((hour-center+12)%24)-12)
            daylight=max(0.0,1.0-distance/max(half,1e-9))
        daily=1.5*math.sin(2*math.pi*(hour-6)/24) if daylight_hours<24 else 0.5*math.sin(2*math.pi*hour/24)
        slow=1.5*math.sin(2*math.pi*offset/72)
        temp=base_temperature_celsius+daily+slow
        wind=max(0.0,base_wind_speed_mps+2*math.sin(2*math.pi*hour/24)+math.sin(2*math.pi*offset/48))
        irradiance=650.0*daylight
        snowfall=max(0.0, 2.0*math.sin(2*math.pi*(offset+7)/96)) if temp < -5 else 0.0
        icing=max(0.0,min(1.0,1.0-0.012*max(0,-temp-5)-0.03*snowfall))
        solar_derate=max(0.0,min(1.0,1.0-0.025*snowfall))
        points.append(WeatherForecastPoint(ts,temp,wind,irradiance,snowfall,icing,solar_derate))
    return points


def generate_multi_day_forecast(
    start_time: datetime,
    hours: int,
    base_temperature_celsius: float = -30.0,
    base_wind_speed_mps: float = 8.0,
) -> dict:
    weather = _reference_weather(start_time, hours, base_temperature_celsius, base_wind_speed_mps)
    rows: list[dict] = []
    for row in generate_forecast(weather):
        load_value, load_low, load_high, load_conf = prediction_interval(row.load_kw, "load", row.hour_offset)
        solar_value, solar_low, solar_high, solar_conf = prediction_interval(row.solar_kw, "solar", row.hour_offset)
        wind_value, wind_low, wind_high, wind_conf = prediction_interval(row.wind_kw, "wind", row.hour_offset)
        row_dict = row.to_dict()
        row_dict.update({
            "solar_irradiance_w_m2": weather[row.hour_offset].solar_irradiance_w_m2,
            "snowfall_rate": weather[row.hour_offset].snowfall_rate,
            "wind_icing_factor": weather[row.hour_offset].wind_icing_factor,
            "solar_derate_factor": weather[row.hour_offset].solar_derate_factor,
            "polar_night": weather[row.hour_offset].solar_irradiance_w_m2 <= 0.0,
            "load_lower_kw": load_low,
            "load_upper_kw": load_high,
            "solar_lower_kw": solar_low,
            "solar_upper_kw": solar_high,
            "wind_lower_kw": wind_low,
            "wind_upper_kw": wind_high,
            "load_confidence": load_conf,
            "solar_confidence": solar_conf,
            "wind_confidence": wind_conf,
            "confidence": min(load_conf, solar_conf, wind_conf),
        })
        rows.append(row_dict)

    return {
        "source": "integrated_ai_ml_reference_weather",
        "synthetic_weather": True,
        "horizon_hours": hours,
        "forecast": rows,
        "confidence": confidence_summary(rows),
    }
