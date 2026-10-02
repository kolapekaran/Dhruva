from fastapi import APIRouter
from app.config import STATION_CONFIG

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("")
def settings():
    """Read-only station configuration for the frontend settings screen."""
    c = STATION_CONFIG
    return {
        "editable": False,
        "station": {
            "id": c.station.name,
            "name": c.station.name,
            "environment": "Antarctic reference environment",
            "data_classification": "synthetic_reference",
        },
        "solar": {
            "installed_capacity_kw": c.solar.installed_capacity_kw,
            "nominal_efficiency_ratio": c.solar.nominal_efficiency_ratio,
            "temperature_coefficient_percent_per_celsius": c.solar.temperature_coefficient_percent_per_celsius,
        },
        "wind": {
            "installed_capacity_kw": c.wind.installed_capacity_kw,
            "cut_in_wind_speed_mps": c.wind.cut_in_wind_speed_mps,
            "rated_wind_speed_mps": c.wind.rated_wind_speed_mps,
            "cut_out_wind_speed_mps": c.wind.cut_out_wind_speed_mps,
        },
        "battery": {
            "capacity_kwh": c.battery.capacity_kwh,
            "max_charge_power_kw": c.battery.max_charge_power_kw,
            "max_discharge_power_kw": c.battery.max_discharge_power_kw,
            "min_soc_percent": c.battery.min_soc_ratio * 100,
            "max_soc_percent": c.battery.max_soc_ratio * 100,
            "initial_soc_percent": c.battery.initial_soc_ratio * 100,
            "minimum_operating_temperature_celsius": c.battery.minimum_operating_temperature_celsius,
        },
        "diesel": {
            "rated_power_kw": c.diesel.rated_power_kw,
            "minimum_power_kw": c.diesel.minimum_power_kw,
            "fuel_intercept_lph": c.diesel.fuel_intercept_lph,
            "fuel_slope_l_per_kwh": c.diesel.fuel_slope_l_per_kwh,
        },
        "fuel": {
            "tank_capacity_liters": c.fuel.tank_capacity_liters,
            "initial_fuel_liters": c.fuel.initial_fuel_liters,
            "emergency_reserve_liters": c.fuel.emergency_reserve_liters,
        },
        "loads": {
            "critical_kw": c.loads.critical_load_kw,
            "important_kw": c.loads.important_load_kw,
            "flexible_kw": c.loads.flexible_load_kw,
            "max_flexible_kw": c.loads.max_flexible_load_kw,
        },
        "simulation": {
            "timestep_seconds": c.simulation.timestep_seconds,
            "forecast_horizon_hours": c.simulation.forecast_horizon_hours,
            "safe_battery_reserve_percent": c.simulation.safe_battery_reserve_ratio * 100,
        },
    }
