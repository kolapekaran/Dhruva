from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from app.config import STATION_CONFIG, StationConfig
from app.digital_twin.energy_balance import EnergyBalanceInputs, calculate_energy_balance
from app.digital_twin.state import *
from app.models.solar import SolarModelInputs, calculate_solar
from app.models.wind import WindModelInputs, calculate_wind
from app.models.battery import BatteryModelInputs, simulate_battery_step
from app.models.diesel import DieselModelInputs, simulate_diesel_step
from app.models.heating import HeatingModelInputs, calculate_heating
from app.models.fuel import FuelModelInputs, calculate_fuel
from app.models.load import LoadModelInputs, calculate_load

@dataclass(frozen=True)
class StationTwinInputs:
    timestamp: datetime
    outdoor_temperature_celsius: float
    wind_speed_mps: float
    solar_irradiance_w_m2: float
    snowfall_rate: float = 0.0
    solar_derate_factor: float = 1.0
    wind_icing_factor: float = 1.0
    heating_power_kw: float | None = None
    critical_load_kw: float | None = None
    important_load_kw: float | None = None
    flexible_load_kw: float | None = None
    battery_charge_request_kw: float = 0.0
    battery_discharge_request_kw: float = 0.0
    diesel_power_request_kw: float = 0.0
    diesel_running: bool = False
    battery_temperature_celsius: float | None = None
    timestep_seconds: int | None = None

@dataclass(frozen=True)
class StationTwinResult:
    state: TwinState
    solar_power_kw: float
    wind_power_kw: float
    diesel_power_kw: float
    total_load_kw: float
    battery_charge_kw: float
    battery_discharge_kw: float
    fuel_consumed_liters: float
    next_indoor_temperature_celsius: float

class StationTwin:
    def __init__(self, config: StationConfig = STATION_CONFIG):
        self.config = config
        self.state = TwinState.initial(
            config.battery.initial_soc_ratio,
            config.fuel.initial_fuel_liters,
            config.heating.target_indoor_temperature_celsius,
        )

        # Start the authoritative Twin from a physically coherent reference operating point.
        # This prevents the UI from showing served load with zero supply before the first control action.
        baseline_wind = calculate_wind(
            WindModelInputs(self.state.weather.wind_speed_mps, self.state.weather.icing_factor),
            self.config.wind,
        ).wind_power_kw
        baseline_diesel = max(self.config.diesel.minimum_power_kw, self.state.loads.total_load_kw - baseline_wind)
        baseline_diesel = min(self.config.diesel.rated_power_kw, baseline_diesel)
        self.state.generation.wind_power_kw = baseline_wind
        self.state.generation.diesel_power_kw = baseline_diesel
        self.state.system.total_generation_kw = baseline_wind + baseline_diesel
        self.state.system.renewable_generation_kw = baseline_wind
        self.state.generation.generator_start_count = 1
        self.state.system.diesel_running = baseline_diesel > 0
        self.state.fuel.consumption_rate_lph = self.config.diesel.fuel_intercept_lph + self.config.diesel.fuel_slope_l_per_kwh * baseline_diesel
        self.state.system.power_balance_kw = self.state.system.total_generation_kw - self.state.loads.total_load_kw
        self.state.status.energy_status = EnergyStatus.BALANCED if abs(self.state.system.power_balance_kw) < 1e-6 else EnergyStatus.DEFICIT

    def step(self, inputs: StationTwinInputs) -> StationTwinResult:
        dt = inputs.timestep_seconds or self.config.simulation.timestep_seconds
        if dt <= 0:
            raise ValueError("Timestep must be positive")
        timestamp = inputs.timestamp if inputs.timestamp.tzinfo else inputs.timestamp.replace(tzinfo=timezone.utc)

        solar = calculate_solar(
            SolarModelInputs(inputs.solar_irradiance_w_m2, inputs.outdoor_temperature_celsius, inputs.solar_derate_factor),
            self.config.solar,
        )
        wind = calculate_wind(
            WindModelInputs(inputs.wind_speed_mps, inputs.wind_icing_factor),
            self.config.wind,
        )

        indoor = self.state.thermal.indoor_temperature_celsius
        heating_request = inputs.heating_power_kw
        if heating_request is None:
            heating_request = max(0.0, 0.20 * self.config.heating.heat_loss_coefficient_kw_per_celsius *
                                  max(indoor - inputs.outdoor_temperature_celsius, 0.0))
        heating = calculate_heating(
            HeatingModelInputs(inputs.outdoor_temperature_celsius, indoor, heating_request, dt),
            self.config.heating,
        )

        critical = inputs.critical_load_kw if inputs.critical_load_kw is not None else self.config.loads.critical_load_kw
        important = inputs.important_load_kw if inputs.important_load_kw is not None else self.config.loads.important_load_kw
        flexible = inputs.flexible_load_kw if inputs.flexible_load_kw is not None else self.config.loads.flexible_load_kw
        requested_load = calculate_load(
            LoadModelInputs(critical, important, flexible, heating.actual_heating_power_kw),
            self.config.loads,
        )

        battery_temp = (
            inputs.battery_temperature_celsius
            if inputs.battery_temperature_celsius is not None
            else inputs.outdoor_temperature_celsius
        )
        battery = simulate_battery_step(
            BatteryModelInputs(
                self.state.battery.soc_ratio,
                inputs.battery_charge_request_kw,
                inputs.battery_discharge_request_kw,
                dt,
                battery_temp,
            ),
            self.config.battery,
        )

        # Couple generator output to available fuel before applying the diesel result.
        # This prevents the Twin from reporting electrical generation after the fuel tank
        # has physically run out.
        fuel_before = self.state.fuel.fuel_remaining_liters
        diesel_request = inputs.diesel_power_request_kw
        diesel_running = inputs.diesel_running
        if diesel_running and diesel_request > 0 and fuel_before <= 0.0:
            diesel_request = 0.0
            diesel_running = False
        elif diesel_running and diesel_request > 0:
            hours = dt / 3600.0
            fixed_fuel = self.config.diesel.fuel_intercept_lph * hours
            variable_fuel_per_kw = self.config.diesel.fuel_slope_l_per_kwh * hours
            if fixed_fuel >= fuel_before:
                diesel_request = 0.0
                diesel_running = False
            elif variable_fuel_per_kw > 0:
                max_power_from_fuel = (fuel_before - fixed_fuel) / variable_fuel_per_kw
                diesel_request = min(diesel_request, max_power_from_fuel)
                if diesel_request < self.config.diesel.minimum_power_kw:
                    diesel_request = 0.0
                    diesel_running = False

        diesel = simulate_diesel_step(
            DieselModelInputs(diesel_request, dt, diesel_running),
            self.config.diesel,
        )

        fuel = calculate_fuel(FuelModelInputs(fuel_before, diesel.fuel_consumed_liters), self.config.fuel)
        balance = calculate_energy_balance(
            EnergyBalanceInputs(
                solar.solar_power_kw, wind.wind_power_kw, diesel.actual_power_kw,
                battery.actual_discharge_power_kw, battery.actual_charge_power_kw,
                requested_load.total_load_kw,
            )
        )

        # Load service is calculated after supply is known. Critical/important/flexible priority is explicit.
        supply_for_loads = (
            solar.solar_power_kw + wind.wind_power_kw + diesel.actual_power_kw +
            battery.actual_discharge_power_kw - battery.actual_charge_power_kw
        )
        served_load = calculate_load(
            LoadModelInputs(critical, important, flexible, heating.actual_heating_power_kw),
            self.config.loads,
            max(0.0, supply_for_loads),
        )

        status = EnergyStatus.BALANCED
        if served_load.shed_load_kw > 1e-6:
            status = EnergyStatus.CRITICAL if served_load.critical_load_kw < critical - 1e-6 else EnergyStatus.DEFICIT
        elif balance.surplus_kw > 1e-6:
            status = EnergyStatus.SURPLUS
        elif balance.deficit_kw > 1e-6:
            status = EnergyStatus.DEFICIT

        mode = StationOperatingMode.NORMAL
        if status == EnergyStatus.CRITICAL:
            mode = StationOperatingMode.EMERGENCY
        elif served_load.shed_load_kw > 1e-6:
            mode = StationOperatingMode.LOAD_SHEDDING
        elif fuel.final_fuel_liters <= self.config.fuel.emergency_reserve_liters:
            mode = StationOperatingMode.ECO

        diesel_running = diesel.generator_running and diesel.actual_power_kw > 0
        runtime = self.state.system.diesel_runtime_seconds + (dt if diesel_running else 0)
        cumulative_fuel = self.state.fuel.cumulative_consumed_liters + fuel.actual_consumed_liters
        # Slowly degrade battery SOH with cycling and temperature stress. This is an
        # engineering reference model, not a field-calibrated battery-aging model.
        throughput_kwh = (battery.actual_charge_power_kw + battery.actual_discharge_power_kw) * dt / 3600.0
        cycle_increment = throughput_kwh / max(1e-9, 2.0 * self.config.battery.capacity_kwh)
        cold_penalty = max(0.0, (-15.0 - battery_temp) / 20.0) * 0.0008 * (dt / 3600.0)
        prior_soh = self.state.battery.state_of_health_percent
        soh = max(50.0, prior_soh - cycle_increment * 0.02 - cold_penalty)
        # Generator health is driven mainly by accumulated runtime and harsh cold.
        prior_gh = self.state.generation.generator_health_percent
        runtime_hours = runtime / 3600.0
        cold_stress = max(0.0, (-20.0 - inputs.outdoor_temperature_celsius) / 40.0)
        gh = max(50.0, prior_gh - (0.0008 if diesel_running else 0.0) * (dt / 3600.0) - cold_stress * 0.0003 * (dt / 3600.0))
        rate = fuel.actual_consumed_liters / (dt / 3600.0) if dt else 0.0

        new_state = TwinState(
            time=TimeState(timestamp, self.state.time.simulation_step + 1),
            weather=WeatherState(
                inputs.outdoor_temperature_celsius,
                inputs.wind_speed_mps,
                inputs.solar_irradiance_w_m2,
                inputs.snowfall_rate,
                wind.icing_factor,
            ),
            generation=GenerationState(
                solar.solar_power_kw, wind.wind_power_kw, diesel.actual_power_kw,
                gh, self.state.generation.generator_start_count + (1 if diesel_running and not self.state.system.diesel_running else 0),
            ),
            battery=BatteryState(
                battery.final_soc_ratio,
                battery.actual_discharge_power_kw - battery.actual_charge_power_kw,
                battery_temp, soh, soh, self.state.battery.cycle_count + cycle_increment,
            ),
            fuel=FuelState(fuel.final_fuel_liters, cumulative_fuel, rate),
            loads=LoadsState(
                served_load.critical_load_kw,
                served_load.important_load_kw,
                served_load.flexible_load_kw,
                served_load.heating_load_kw,
                requested_load.requested_load_kw,
                served_load.served_load_kw,
                served_load.shed_load_kw,
                requested_load.requested_load_kw,
            ),
            system=SystemState(
                balance.total_generation_kw,
                solar.solar_power_kw + wind.wind_power_kw,
                battery.actual_charge_power_kw,
                battery.actual_discharge_power_kw,
                balance.power_balance_kw,
                balance.surplus_kw,
                balance.deficit_kw,
                diesel_running,
                runtime,
            ),
            status=StatusState(mode, status),
            thermal=ThermalState(heating.next_indoor_temperature_celsius),
        )
        self.state = new_state

        return StationTwinResult(
            new_state, solar.solar_power_kw, wind.wind_power_kw, diesel.actual_power_kw,
            requested_load.total_load_kw, battery.actual_charge_power_kw,
            battery.actual_discharge_power_kw, fuel.actual_consumed_liters,
            heating.next_indoor_temperature_celsius,
        )
