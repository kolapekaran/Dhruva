from dataclasses import dataclass

@dataclass(frozen=True)
class WeatherInputs:
    temperature_celsius: float
    wind_speed_mps: float
    solar_irradiance_w_m2: float
    snowfall_rate: float = 0.0
    icing_factor: float = 1.0

def validate_weather(w: WeatherInputs) -> WeatherInputs:
    if w.wind_speed_mps < 0 or w.solar_irradiance_w_m2 < 0:
        raise ValueError("Wind and irradiance must be non-negative")
    if not 0 <= w.icing_factor <= 1:
        raise ValueError("Icing factor must be in [0,1]")
    return w
