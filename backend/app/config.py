from dataclasses import dataclass

@dataclass(frozen=True)
class StationInfo:
    name: str = "Maitri Research Station"
    simulation_timestep_seconds: int = 60

@dataclass(frozen=True)
class SolarPVConfig:
    installed_capacity_kw: float = 50.0
    nominal_efficiency_ratio: float = 0.20
    temperature_coefficient_percent_per_celsius: float = -0.35
    snow_ice_derate_min: float = 0.0
    snow_ice_derate_max: float = 1.0

@dataclass(frozen=True)
class WindTurbineConfig:
    installed_capacity_kw: float = 100.0
    cut_in_wind_speed_mps: float = 3.0
    rated_wind_speed_mps: float = 12.0
    cut_out_wind_speed_mps: float = 25.0
    icing_derate_min: float = 0.0
    icing_derate_max: float = 1.0

@dataclass(frozen=True)
class BatteryConfig:
    capacity_kwh: float = 500.0
    max_charge_power_kw: float = 100.0
    max_discharge_power_kw: float = 100.0
    round_trip_efficiency_ratio: float = 0.90
    min_soc_ratio: float = 0.20
    max_soc_ratio: float = 0.95
    initial_soc_ratio: float = 0.60
    minimum_operating_temperature_celsius: float = -35.0
    maximum_operating_temperature_celsius: float = 45.0

@dataclass(frozen=True)
class DieselGeneratorConfig:
    rated_power_kw: float = 150.0
    minimum_power_kw: float = 30.0
    fuel_intercept_lph: float = 5.0
    fuel_slope_l_per_kwh: float = 0.25
    startup_time_seconds: int = 30
    minimum_runtime_seconds: int = 600

@dataclass(frozen=True)
class FuelTankConfig:
    tank_capacity_liters: float = 20000.0
    initial_fuel_liters: float = 15000.0
    emergency_reserve_liters: float = 2000.0

@dataclass(frozen=True)
class LoadsConfig:
    critical_load_kw: float = 15.0
    important_load_kw: float = 25.0
    flexible_load_kw: float = 10.0
    max_flexible_load_kw: float = 20.0

@dataclass(frozen=True)
class HeatingConfig:
    target_indoor_temperature_celsius: float = 20.0
    heat_loss_coefficient_kw_per_celsius: float = 0.8
    thermal_mass_kwh_per_celsius: float = 50.0
    heating_efficiency_ratio: float = 0.85

@dataclass(frozen=True)
class SimulationConfig:
    timestep_seconds: int = 60
    forecast_horizon_hours: int = 24
    safe_battery_reserve_ratio: float = 0.25

@dataclass(frozen=True)
class StationConfig:
    station: StationInfo = StationInfo()
    solar: SolarPVConfig = SolarPVConfig()
    wind: WindTurbineConfig = WindTurbineConfig()
    battery: BatteryConfig = BatteryConfig()
    diesel: DieselGeneratorConfig = DieselGeneratorConfig()
    fuel: FuelTankConfig = FuelTankConfig()
    loads: LoadsConfig = LoadsConfig()
    heating: HeatingConfig = HeatingConfig()
    simulation: SimulationConfig = SimulationConfig()

STATION_CONFIG = StationConfig()
