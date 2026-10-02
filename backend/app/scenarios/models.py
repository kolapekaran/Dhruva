"""
models.py

Data models used by the Scenario Engine.

This file defines:
- ScenarioType: all the possible scenario labels the engine can detect
- ScenarioInput: the raw sensor/prediction data fed into the engine
- ScenarioResult: the output produced by the engine after evaluation

No logic lives here. This file only describes the shape of the data.
"""

from dataclasses import dataclass, field
from enum import Enum


class ScenarioType(str, Enum):
    """
    All scenario labels the engine is able to detect.

    Inheriting from `str` as well as `Enum` means these values behave like
    normal strings (easy to print, easy to put into JSON for an API later)
    while still being a proper Enum.
    """

    NORMAL = "NORMAL"
    EXTREME_COLD = "EXTREME_COLD"
    LOW_WIND = "LOW_WIND"
    NO_SOLAR = "NO_SOLAR"
    HIGH_LOAD = "HIGH_LOAD"
    BATTERY_DEGRADED = "BATTERY_DEGRADED"
    DIESEL_FAILURE = "DIESEL_FAILURE"
    FUEL_SHORTAGE = "FUEL_SHORTAGE"
    RESUPPLY_DELAY = "RESUPPLY_DELAY"
    COMBINED_EXTREME = "COMBINED_EXTREME"


@dataclass
class ScenarioInput:
    """
    Represents the current (or predicted) state of the station.

    This is the single object the engine needs in order to evaluate
    conditions. It can be built directly from sensor readings, from an
    AI/ML prediction, or from a JSON body sent to a future FastAPI endpoint.
    """

    # Outside air temperature in Celsius. Negative values are expected.
    temperature: float = 0.0

    # Wind generation as a percentage of normal/expected output (0-100).
    wind_percent: float = 100.0

    # Whether solar power is currently available at all.
    solar_available: bool = True

    # Current electrical load as a percentage of normal capacity.
    # Values above 100 mean the station is drawing more than its
    # baseline "normal" load.
    load_percent: float = 100.0

    # Battery health/state as a percentage (0-100). Lower means more
    # degraded / less reliable storage.
    battery_health: float = 100.0

    # Whether the diesel generator backup is currently available.
    diesel_available: bool = True

    # Remaining fuel as a percentage of full capacity (0-100).
    fuel_percent: float = 100.0

    # Number of days the next resupply shipment is delayed by.
    # 0 means resupply is on schedule.
    resupply_delay_days: int = 0

    def __post_init__(self) -> None:
        """Validate values as soon as the object is created."""
        validate_scenario_input(self)


@dataclass
class ScenarioResult:
    """
    The output of evaluating a ScenarioInput.

    This is what the rest of the system (API, dashboard, alerts, etc.)
    will consume after the engine runs.
    """

    # List of scenario labels detected, e.g. ["EXTREME_COLD", "LOW_WIND"].
    # Stored as plain strings (via ScenarioType's str value) so this is
    # easy to serialize to JSON later.
    scenarios: list[str] = field(default_factory=list)

    # Overall severity level: "LOW", "MEDIUM", "HIGH", or "CRITICAL".
    severity: str = "LOW"

    # Human-readable recommendations, one per detected condition
    # (plus an extra one if COMBINED_EXTREME is triggered).
    recommendations: list[str] = field(default_factory=list)

    # Numeric risk score from 0 to 100.
    estimated_risk: float = 0.0


def validate_scenario_input(data: ScenarioInput) -> None:
    """
    Raise a ValueError if any field of `data` is out of its valid range.

    Kept as a standalone function (rather than only inside __post_init__)
    so it can also be reused elsewhere, e.g. if an API layer wants to
    validate a dict before constructing a ScenarioInput.
    """
    if not (0.0 <= data.wind_percent <= 100.0):
        raise ValueError(
            f"wind_percent must be between 0 and 100, got {data.wind_percent}"
        )

    if data.load_percent < 0.0:
        raise ValueError(
            f"load_percent must be >= 0, got {data.load_percent}"
        )

    if not (0.0 <= data.battery_health <= 100.0):
        raise ValueError(
            f"battery_health must be between 0 and 100, got {data.battery_health}"
        )

    if not (0.0 <= data.fuel_percent <= 100.0):
        raise ValueError(
            f"fuel_percent must be between 0 and 100, got {data.fuel_percent}"
        )

    if data.resupply_delay_days < 0:
        raise ValueError(
            "resupply_delay_days must be >= 0, "
            f"got {data.resupply_delay_days}"
        )