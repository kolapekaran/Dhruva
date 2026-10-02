from fastapi.testclient import TestClient
from app.main import app
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.digital_twin.projection import run_projection
from datetime import datetime, timezone


def test_multi_day_forecast_supported_horizons():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for hours in (24, 72, 168):
        result = generate_multi_day_forecast(start, hours)
        assert len(result["forecast"]) == hours
        assert 0.0 < result["confidence"]["average_confidence"] <= 1.0
        assert all(0 <= r["solar_kw"] <= 50 for r in result["forecast"])
        assert all(0 <= r["wind_kw"] <= 100 for r in result["forecast"])


def test_projection_produces_resilience_metrics():
    result = run_projection(datetime(2026, 1, 1, tzinfo=timezone.utc), 24)
    assert len(result.points) == 24
    assert result.metrics["final_fuel_liters"] >= 0
    assert 0 <= result.metrics["minimum_soc_ratio"] <= 1
    assert 0 <= result.metrics["blackout_risk_percent"] <= 100
    assert result.metrics["renewable_energy_kwh"] >= 0


def test_ui_ready_part1_endpoints():
    client = TestClient(app)
    for path in (
        "/forecasts/multi-day?hours=24",
        "/projection?hours=24",
        "/energy/analysis?hours=24",
        "/fuel/projection?hours=24",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)


def test_projection_metrics_cover_full_horizon_including_terminal_step():
    result = run_projection(datetime(2026, 1, 1, tzinfo=timezone.utc), 24)
    # The public series intentionally has 24 displayed points (0..23), while
    # energy/runtime metrics include the terminal +24 simulation step.
    assert len(result.points) == 24
    assert result.metrics["load_energy_kwh"] > 24 * 50
    assert 24 * 50 <= result.metrics["load_energy_kwh"] <= 24 * 60
    assert 0 <= result.metrics["diesel_runtime_hours"] <= 24


def test_one_hour_projection_has_nonzero_horizon_metrics():
    result = run_projection(datetime(2026, 1, 1, tzinfo=timezone.utc), 1)
    assert len(result.points) == 1
    assert result.metrics["load_energy_kwh"] > 0
    assert result.metrics["served_energy_kwh"] > 0


def test_initial_energy_state_reports_renewable_generation():
    from app.digital_twin.station_twin import StationTwin
    twin = StationTwin()
    assert twin.state.system.renewable_generation_kw == twin.state.generation.wind_power_kw + twin.state.generation.solar_power_kw
