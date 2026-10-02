from datetime import datetime, timezone
from app.config import STATION_CONFIG
from app.digital_twin.energy_balance import EnergyBalanceInputs, calculate_energy_balance
from app.digital_twin.station_twin import StationTwin, StationTwinInputs
from app.models.battery import BatteryModelInputs, simulate_battery_step
from app.models.diesel import DieselModelInputs, simulate_diesel_step
from app.models.fuel import FuelModelInputs, calculate_fuel
from app.models.solar import SolarModelInputs, calculate_solar
from app.models.wind import WindModelInputs, calculate_wind

def test_energy_balance():
    r = calculate_energy_balance(EnergyBalanceInputs(20,30,0,0,0,40))
    assert r.surplus_kw == 10

def test_solar_limit():
    r = calculate_solar(SolarModelInputs(2000,25,1), STATION_CONFIG.solar)
    assert r.solar_power_kw <= 50

def test_wind_curve():
    assert calculate_wind(WindModelInputs(2,1), STATION_CONFIG.wind).wind_power_kw == 0
    assert calculate_wind(WindModelInputs(26,1), STATION_CONFIG.wind).wind_power_kw == 0

def test_battery_charge_and_discharge():
    c = simulate_battery_step(BatteryModelInputs(.60,50,0,3600,-10), STATION_CONFIG.battery)
    d = simulate_battery_step(BatteryModelInputs(.60,0,50,3600,-10), STATION_CONFIG.battery)
    assert c.final_soc_ratio > .60
    assert d.final_soc_ratio < .60

def test_diesel():
    r = simulate_diesel_step(DieselModelInputs(100,3600,True), STATION_CONFIG.diesel)
    assert r.actual_power_kw == 100
    assert r.fuel_consumed_liters > 0

def test_fuel():
    r = calculate_fuel(FuelModelInputs(10,100), STATION_CONFIG.fuel)
    assert r.final_fuel_liters == 0

def test_twin_evolves():
    twin = StationTwin()
    t = datetime(2026,1,1,tzinfo=timezone.utc)
    r = twin.step(StationTwinInputs(t,-25,10,500,battery_discharge_request_kw=10))
    assert 0.20 <= r.state.battery.soc_ratio <= .95
    assert r.state.time.simulation_step == 1
    assert r.state.thermal.indoor_temperature_celsius != 20.0 or r.state.loads.heating_load_kw >= 0
