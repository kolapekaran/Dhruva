"""Closed-loop energy management controller.

The controller decides battery/diesel requests from the current physical
inputs and Twin state. The Digital Twin remains the authority that applies
those requests and updates SOC, fuel, load shedding and thermal state.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.config import STATION_CONFIG, StationConfig
from app.models.solar import SolarModelInputs, calculate_solar
from app.models.wind import WindModelInputs, calculate_wind

@dataclass(frozen=True)
class DispatchCommand:
    battery_charge_kw: float = 0.0
    battery_discharge_kw: float = 0.0
    diesel_power_kw: float = 0.0
    diesel_running: bool = False
    reason: str = "normal_operation"

def validate_command(command: DispatchCommand, config: StationConfig = STATION_CONFIG) -> DispatchCommand:
    if command.battery_charge_kw > 0 and command.battery_discharge_kw > 0:
        raise ValueError("Battery cannot charge and discharge simultaneously")
    if command.battery_charge_kw < 0 or command.battery_discharge_kw < 0 or command.diesel_power_kw < 0:
        raise ValueError("Dispatch powers must be non-negative")
    if command.battery_charge_kw > config.battery.max_charge_power_kw + 1e-9:
        raise ValueError("Battery charge request exceeds configured limit")
    if command.battery_discharge_kw > config.battery.max_discharge_power_kw + 1e-9:
        raise ValueError("Battery discharge request exceeds configured limit")
    if command.diesel_power_kw > config.diesel.rated_power_kw + 1e-9:
        raise ValueError("Diesel request exceeds configured rated power")
    if command.diesel_power_kw > 0 and not command.diesel_running:
        raise ValueError("Diesel must be marked running when power is requested")
    return command

class EMSController:
    """Deterministic safety-first controller used until optimization is added."""

    def __init__(self, config: StationConfig = STATION_CONFIG):
        self.config = config

    def decide(self, inputs, state, forecast=None) -> DispatchCommand:
        dt_hours = (inputs.timestep_seconds or self.config.simulation.timestep_seconds) / 3600.0
        if dt_hours <= 0:
            raise ValueError("Timestep must be positive")

        solar = calculate_solar(
            SolarModelInputs(inputs.solar_irradiance_w_m2, inputs.outdoor_temperature_celsius, inputs.solar_derate_factor),
            self.config.solar,
        ).solar_power_kw
        wind = calculate_wind(
            WindModelInputs(inputs.wind_speed_mps, inputs.wind_icing_factor),
            self.config.wind,
        ).wind_power_kw

        heating = inputs.heating_power_kw
        if heating is None:
            indoor = state.thermal.indoor_temperature_celsius
            heating = max(0.0, 0.20 * self.config.heating.heat_loss_coefficient_kw_per_celsius *
                          max(indoor - inputs.outdoor_temperature_celsius, 0.0))
        critical = inputs.critical_load_kw if inputs.critical_load_kw is not None else self.config.loads.critical_load_kw
        important = inputs.important_load_kw if inputs.important_load_kw is not None else self.config.loads.important_load_kw
        flexible = inputs.flexible_load_kw if inputs.flexible_load_kw is not None else self.config.loads.flexible_load_kw
        requested_load = max(0.0, critical) + max(0.0, important) + min(max(0.0, flexible), self.config.loads.max_flexible_load_kw) + max(0.0, heating)
        renewable = solar + wind
        net = renewable - requested_load

        if net >= 0:
            charge = min(net, self.config.battery.max_charge_power_kw)
            return validate_command(DispatchCommand(
                battery_charge_kw=charge, reason="renewable_surplus_charge" if charge > 0 else "balanced"
            ), self.config)

        deficit = -net
        # Keep a safety reserve above the physical minimum.
        safe_soc = max(self.config.simulation.safe_battery_reserve_ratio, self.config.battery.min_soc_ratio)
        available_battery_energy = max(0.0, (state.battery.soc_ratio - safe_soc) * self.config.battery.capacity_kwh)
        eta = self.config.battery.round_trip_efficiency_ratio ** 0.5
        battery_limit = available_battery_energy * eta / dt_hours
        battery_power = min(deficit, self.config.battery.max_discharge_power_kw, max(0.0, battery_limit))
        if battery_power < 1e-6:
            battery_power = 0.0
        remaining = max(0.0, deficit - battery_power)

        diesel = 0.0
        running = False
        if remaining > 1e-9 and state.fuel.fuel_remaining_liters > self.config.fuel.emergency_reserve_liters + 1e-9:
            # Never intentionally consume the protected emergency reserve.
            fuel_available = state.fuel.fuel_remaining_liters - self.config.fuel.emergency_reserve_liters
            max_diesel_by_fuel = max(0.0, ((fuel_available / dt_hours) - self.config.diesel.fuel_intercept_lph) / self.config.diesel.fuel_slope_l_per_kwh)
            diesel = min(remaining, self.config.diesel.rated_power_kw, max_diesel_by_fuel)
            if diesel > 0:
                running = True
                if diesel < self.config.diesel.minimum_power_kw:
                    diesel = min(self.config.diesel.minimum_power_kw, self.config.diesel.rated_power_kw, max_diesel_by_fuel)

        # A diesel generator has a minimum stable output. If that minimum would
        # create a surplus after covering a small deficit, absorb the surplus in
        # the battery when headroom exists instead of exporting/losing energy.
        # This keeps the projected station energy balance physically coherent.
        post_dispatch_surplus = max(0.0, renewable + diesel - requested_load - battery_power)
        if post_dispatch_surplus > 1e-9 and battery_power <= 1e-9 and diesel > 0:
            charge_headroom = max(0.0, (self.config.battery.max_soc_ratio - state.battery.soc_ratio) * self.config.battery.capacity_kwh / max(1e-9, dt_hours))
            charge = min(post_dispatch_surplus, self.config.battery.max_charge_power_kw, charge_headroom)
        else:
            charge = 0.0

        if battery_power > 0 and diesel > 0:
            reason = "battery_plus_diesel_support"
        elif battery_power > 0:
            reason = "battery_discharge"
        elif diesel > 0:
            reason = "diesel_support"
        else:
            reason = "load_shedding_required"

        return validate_command(DispatchCommand(
            battery_charge_kw=charge,
            battery_discharge_kw=battery_power,
            diesel_power_kw=diesel,
            diesel_running=running,
            reason=("minimum_diesel_surplus_to_battery" if charge > 0 else reason),
        ), self.config)
