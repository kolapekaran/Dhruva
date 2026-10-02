from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

class StationOperatingMode(str, Enum):
    NORMAL = "normal"
    ECO = "eco"
    LOAD_SHEDDING = "load_shedding"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    BLACKOUT = "blackout"

class EnergyStatus(str, Enum):
    SURPLUS = "surplus"
    BALANCED = "balanced"
    DEFICIT = "deficit"
    CRITICAL = "critical"

@dataclass
class TimeState:
    timestamp: datetime
    simulation_step: int = 0

@dataclass
class WeatherState:
    temperature_celsius: float = -20.0
    wind_speed_mps: float = 8.0
    solar_irradiance_w_m2: float = 0.0
    snowfall_rate: float = 0.0
    icing_factor: float = 1.0

@dataclass
class GenerationState:
    solar_power_kw: float = 0.0
    wind_power_kw: float = 0.0
    diesel_power_kw: float = 0.0
    generator_health_percent: float = 100.0
    generator_start_count: int = 0

@dataclass
class BatteryState:
    soc_ratio: float = 0.60
    battery_power_kw: float = 0.0
    battery_temperature_celsius: float = -10.0
    health_percent: float = 100.0
    state_of_health_percent: float = 100.0
    cycle_count: float = 0.0

@dataclass
class FuelState:
    fuel_remaining_liters: float = 15000.0
    cumulative_consumed_liters: float = 0.0
    consumption_rate_lph: float = 0.0

@dataclass
class LoadsState:
    critical_load_kw: float = 15.0
    important_load_kw: float = 25.0
    flexible_load_kw: float = 10.0
    heating_load_kw: float = 0.0
    requested_load_kw: float = 50.0
    served_load_kw: float = 50.0
    shed_load_kw: float = 0.0
    total_load_kw: float = 50.0

@dataclass
class SystemState:
    total_generation_kw: float = 0.0
    renewable_generation_kw: float = 0.0
    battery_charging_kw: float = 0.0
    battery_discharging_kw: float = 0.0
    power_balance_kw: float = 0.0
    surplus_kw: float = 0.0
    deficit_kw: float = 0.0
    diesel_running: bool = False
    diesel_runtime_seconds: int = 0

@dataclass
class StatusState:
    operating_mode: StationOperatingMode = StationOperatingMode.NORMAL
    energy_status: EnergyStatus = EnergyStatus.BALANCED

@dataclass
class ThermalState:
    indoor_temperature_celsius: float = 20.0

@dataclass
class TwinState:
    time: TimeState
    weather: WeatherState
    generation: GenerationState
    battery: BatteryState
    fuel: FuelState
    loads: LoadsState
    system: SystemState
    status: StatusState
    thermal: ThermalState

    @classmethod
    def initial(cls, battery_soc: float, fuel_liters: float, indoor_temperature: float = 20.0):
        return cls(
            TimeState(datetime.now(timezone.utc), 0),
            WeatherState(),
            GenerationState(),
            BatteryState(soc_ratio=battery_soc),
            FuelState(fuel_remaining_liters=fuel_liters),
            LoadsState(),
            SystemState(),
            StatusState(),
            ThermalState(indoor_temperature),
        )
