"""Feature construction shared by the trained forecasting models."""
from __future__ import annotations
import numpy as np


def create_features(temp_celsius: float, hour: float, wind_speed_mps: float) -> np.ndarray:
    """Return the 5-feature vector used by the supplied teammate models."""
    if not 0 <= hour < 24:
        raise ValueError("hour must be in [0, 24)")
    if wind_speed_mps < 0:
        raise ValueError("wind_speed_mps must be non-negative")
    is_night = 1 if (hour < 6 or hour > 20) else 0
    wind_chill = temp_celsius - (wind_speed_mps * 0.7)
    return np.array([[temp_celsius, hour, wind_speed_mps, is_night, wind_chill]], dtype=float)
