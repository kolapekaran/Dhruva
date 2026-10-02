from app.digital_twin.station_twin import StationTwin
from app.ml.inference.predictor import predict_from_twin_state, forecast_horizon


def test_ml_models_load_and_predict_from_twin():
    twin = StationTwin()
    result = predict_from_twin_state(twin.state)
    assert result.load_kw >= 0
    assert result.solar_kw >= 0
    assert result.wind_kw >= 0
    assert 0 <= result.failure_probability <= 1


def test_ml_horizon():
    rows = forecast_horizon(-20, 8, 12, 4)
    assert len(rows) == 4
    assert all("load_kw" in row and "solar_kw" in row and "wind_kw" in row for row in rows)

from datetime import datetime, timezone
from app.config import STATION_CONFIG
from app.digital_twin.station_twin import StationTwinInputs
from app.ems.controller import EMSController
from app.ml.inference.predictor import predict


def test_ml_predictions_respect_station_physical_limits():
    result = predict(-20, 14, 12)
    assert 0 <= result.solar_kw <= STATION_CONFIG.solar.installed_capacity_kw
    assert 0 <= result.wind_kw <= STATION_CONFIG.wind.installed_capacity_kw


def test_closed_loop_battery_responds_to_deficit():
    twin = StationTwin()
    inputs = StationTwinInputs(
        timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        outdoor_temperature_celsius=0.0,
        wind_speed_mps=4.0,
        solar_irradiance_w_m2=0.0,
        heating_power_kw=0.0,
        critical_load_kw=15.0,
        important_load_kw=25.0,
        flexible_load_kw=10.0,
        battery_temperature_celsius=0.0,
    )
    command = EMSController().decide(inputs, twin.state)
    assert command.battery_discharge_kw > 0
    result = twin.step(StationTwinInputs(**{**inputs.__dict__,
        "battery_discharge_request_kw": command.battery_discharge_kw,
        "diesel_power_request_kw": command.diesel_power_kw,
        "diesel_running": command.diesel_running,
    }))
    assert result.state.battery.soc_ratio < 0.60
    assert result.state.loads.served_load_kw >= result.state.loads.critical_load_kw


def test_closed_loop_starts_diesel_when_battery_at_safe_reserve():
    twin = StationTwin()
    twin.state.battery.soc_ratio = STATION_CONFIG.simulation.safe_battery_reserve_ratio
    inputs = StationTwinInputs(
        timestamp=datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
        outdoor_temperature_celsius=0.0,
        wind_speed_mps=0.0,
        solar_irradiance_w_m2=0.0,
        heating_power_kw=0.0,
        critical_load_kw=15.0,
        important_load_kw=25.0,
        flexible_load_kw=10.0,
        battery_temperature_celsius=0.0,
    )
    command = EMSController().decide(inputs, twin.state)
    assert command.diesel_running is True
    assert command.diesel_power_kw > 0
    result = twin.step(StationTwinInputs(**{**inputs.__dict__,
        "diesel_power_request_kw": command.diesel_power_kw,
        "diesel_running": command.diesel_running,
    }))
    assert result.state.fuel.fuel_remaining_liters < 15000
    assert result.state.generation.diesel_power_kw > 0


def test_fastapi_ems_and_closed_loop_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/ems/dispatch').status_code == 200
    assert client.post('/ems/dispatch').status_code == 200
    assert client.post('/twin/step').status_code == 200
