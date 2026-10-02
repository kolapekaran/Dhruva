"""End-to-end engineering validation for the DHRUVA backend."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import STATION_CONFIG
from app.database.schemas import state_to_dict
from app.digital_twin.energy_balance import calculate_energy_balance
from app.digital_twin.station_twin import StationTwin, StationTwinInputs
from app.ems.controller import EMSController
from app.ml.inference.predictor import predict, forecast_horizon
from app.scenarios.what_if import run_scenario, wind_reduction, solar_reduction, extreme_temperature


def _inputs(**overrides):
    base = dict(
        timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        outdoor_temperature_celsius=-20.0,
        wind_speed_mps=8.0,
        solar_irradiance_w_m2=0.0,
        heating_power_kw=0.0,
        critical_load_kw=15.0,
        important_load_kw=25.0,
        flexible_load_kw=10.0,
        battery_temperature_celsius=-20.0,
    )
    base.update(overrides)
    return StationTwinInputs(**base)


def test_complete_physics_energy_accounting():
    from app.digital_twin.energy_balance import EnergyBalanceInputs
    result = calculate_energy_balance(EnergyBalanceInputs(10.0, 15.0, 20.0, 5.0, 0.0, 60.0))
    assert result.total_generation_kw == 50.0
    assert result.power_balance_kw == -10.0
    assert result.deficit_kw == 10.0
    assert result.surplus_kw == 0.0


def test_complete_closed_loop_covers_deficit_with_battery_first():
    twin = StationTwin()
    inp = _inputs(wind_speed_mps=4.0)
    cmd = EMSController().decide(inp, twin.state)
    assert cmd.battery_discharge_kw > 0
    result = twin.step(StationTwinInputs(**{**inp.__dict__,
        "battery_discharge_request_kw": cmd.battery_discharge_kw,
        "diesel_power_request_kw": cmd.diesel_power_kw,
        "diesel_running": cmd.diesel_running,
    }))
    s = result.state
    assert s.battery.soc_ratio < 0.60
    assert s.loads.served_load_kw >= s.loads.critical_load_kw
    assert s.system.deficit_kw >= 0


def test_complete_closed_loop_diesel_fallback_and_fuel_accounting():
    twin = StationTwin()
    twin.state.battery.soc_ratio = STATION_CONFIG.simulation.safe_battery_reserve_ratio
    inp = _inputs(wind_speed_mps=0.0, outdoor_temperature_celsius=0.0)
    cmd = EMSController().decide(inp, twin.state)
    assert cmd.diesel_running
    assert cmd.diesel_power_kw > 0
    result = twin.step(StationTwinInputs(**{**inp.__dict__,
        "diesel_power_request_kw": cmd.diesel_power_kw,
        "diesel_running": True,
    }))
    s = result.state
    assert s.generation.diesel_power_kw > 0
    assert s.fuel.fuel_remaining_liters < STATION_CONFIG.fuel.initial_fuel_liters
    assert s.loads.served_load_kw >= s.loads.critical_load_kw


def test_complete_critical_load_protection():
    twin = StationTwin()
    inp = _inputs(wind_speed_mps=0.0, critical_load_kw=15.0, important_load_kw=100.0, flexible_load_kw=100.0)
    result = twin.step(inp)
    s = result.state
    assert s.loads.served_load_kw >= s.loads.critical_load_kw
    assert s.loads.shed_load_kw >= 0


def test_complete_ml_contract_and_physical_bounds():
    r = predict(-40.0, 2, 0.0)
    assert 0 <= r.load_kw
    assert 0 <= r.solar_kw <= STATION_CONFIG.solar.installed_capacity_kw
    assert 0 <= r.wind_kw <= STATION_CONFIG.wind.installed_capacity_kw
    assert 0 <= r.failure_probability <= 1
    rows = forecast_horizon(-40.0, 0.0, 2, 24)
    assert len(rows) == 24
    for row in rows:
        assert 0 <= row["solar_kw"] <= STATION_CONFIG.solar.installed_capacity_kw
        assert 0 <= row["wind_kw"] <= STATION_CONFIG.wind.installed_capacity_kw
        assert row["load_kw"] >= 0


def test_complete_api_surface_and_schema():
    from app.main import app
    client = TestClient(app)
    routes = [
        ("GET", "/health"), ("GET", "/twin/state"), ("GET", "/twin/history"),
        ("GET", "/energy"), ("GET", "/fuel"), ("GET", "/alerts"),
        ("GET", "/station"), ("GET", "/forecasts"), ("GET", "/forecasts/horizon?hours=4"),
        ("GET", "/ems/dispatch"), ("POST", "/ems/dispatch"), ("POST", "/twin/step"),
    ]
    for method, path in routes:
        response = client.request(method, path)
        assert response.status_code == 200, (method, path, response.text)
        assert response.headers["content-type"].startswith("application/json")

    state = client.get("/twin/state").json()
    assert state["battery"]["soc_ratio"] >= STATION_CONFIG.battery.min_soc_ratio
    assert state["battery"]["soc_ratio"] <= STATION_CONFIG.battery.max_soc_ratio
    assert state["fuel"]["fuel_remaining_liters"] >= 0


def test_complete_scenarios_produce_physical_responses():
    baseline = run_scenario("baseline", 1)
    wind = run_scenario("wind", 1, wind_reduction(50))
    solar = run_scenario("solar", 1, solar_reduction(50))
    cold = run_scenario("cold", 1, extreme_temperature(-40))
    for m in (baseline, wind, solar, cold):
        assert m.steps == 1440
        assert m.deficit_energy_kwh >= 0
        assert 0 <= m.final_soc_ratio <= 1
        assert m.final_fuel_liters >= 0
        assert m.minimum_fuel_liters >= 0
    assert wind.diesel_energy_kwh >= baseline.diesel_energy_kwh
    assert solar.diesel_energy_kwh >= baseline.diesel_energy_kwh


def test_projection_does_not_leave_unmanaged_generation_surplus_at_minimum_diesel():
    from app.api.integration_adapter import _snapshot
    snap = _snapshot(12)
    pb = snap["powerBalance"]
    # Future snapshots must reconcile generation + battery flow with load.
    assert abs(pb["netBalanceKw"]) < 1e-6
    assert pb["totalGenerationKw"] + pb["batteryPowerKw"] >= pb["totalLoadKw"] - 1e-6
    assert pb["totalGenerationKw"] + pb["batteryPowerKw"] <= pb["totalLoadKw"] + 1e-6

