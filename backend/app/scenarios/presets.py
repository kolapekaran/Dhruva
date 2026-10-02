"""
presets.py

Predefined ScenarioInput objects for quick manual testing and demos.

These are ONLY shortcuts — the engine itself does not know or care that
these presets exist. It works with any ScenarioInput built any way
(manually, from these presets, from a JSON API request, or from an
AI/ML prediction). Combinations of these presets are also valid; you can
mix fields from different presets into a brand new ScenarioInput and the
engine will still evaluate it correctly.
"""

from .models import ScenarioInput

PRESETS: dict[str, ScenarioInput] = {
    "NORMAL": ScenarioInput(
        temperature=-10,
        wind_percent=100,
        solar_available=True,
        load_percent=100,
        battery_health=100,
        diesel_available=True,
        fuel_percent=100,
        resupply_delay_days=0,
    ),
    "EXTREME_COLD": ScenarioInput(
        temperature=-35,
    ),
    "LOW_WIND": ScenarioInput(
        wind_percent=40,
    ),
    "NO_SOLAR": ScenarioInput(
        solar_available=False,
    ),
    "HIGH_LOAD": ScenarioInput(
        load_percent=140,
    ),
    "BATTERY_DEGRADED": ScenarioInput(
        battery_health=30,
    ),
    "DIESEL_FAILURE": ScenarioInput(
        diesel_available=False,
    ),
    "FUEL_SHORTAGE": ScenarioInput(
        fuel_percent=15,
    ),
    "RESUPPLY_DELAY": ScenarioInput(
        resupply_delay_days=10,
    ),
}