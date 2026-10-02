from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_part3_dashboard_report_optimization():
    for path in ("/dashboard?hours=24", "/reports/summary?hours=24", "/optimization?hours=24"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert response.json()


def test_part3_dashboard_has_ui_sections():
    data = client.get("/dashboard?hours=24").json()
    assert {"live", "forecast", "risk", "alerts", "recommendations", "ai_insights"} <= data.keys()
    assert 0 <= data["live"]["battery_soc_percent"] <= 100
    assert data["forecast"]["horizon_hours"] == 24


def test_part3_report_has_series():
    data = client.get("/reports?hours=24").json()
    assert len(data["series"]) == 24
    assert "forecast_summary" in data
    assert "resilience" in data


def test_part3_optimization_is_honest_advisory():
    data = client.get("/optimization?hours=24").json()
    assert data["status"] == "advisory"
    assert data["optimality_claim"] is False
    assert data["impact"]["fuel_saved_liters"] >= 0


def test_part3_energy_accounting_exposes_renewable_generation():
    data = client.get('/energy').json()
    assert abs(data['renewable_generation_kw'] - (data['solar_power_kw'] + data['wind_power_kw'])) < 1e-6
    assert abs(data['total_generation_kw'] - (data['solar_power_kw'] + data['wind_power_kw'] + data['diesel_power_kw'])) < 1e-6


def test_part3_reserve_policy_is_authoritative_and_configurable():
    data = client.get('/api/intelligence/resilience?hours=72&min_reserve_percent=28').json()
    assert data['reserveSemantics']['targetPercent'] >= 28
    strategy = client.get('/ems/strategy?min_reserve_percent=28').json()
    assert strategy['dynamic_reserve_percent'] >= 28


def test_part3_simulator_ai_reoptimization_toggle_is_honest():
    enabled = client.post('/api/intelligence/resilience/simulate', json={
        'scenarioKey': 'STORM_HIGH_WIND', 'hours': 24, 'startOffsetHours': 0, 'aiReoptimization': True,
    }).json()
    disabled = client.post('/api/intelligence/resilience/simulate', json={
        'scenarioKey': 'STORM_HIGH_WIND', 'hours': 24, 'startOffsetHours': 0, 'aiReoptimization': False,
    }).json()
    assert enabled['aiReoptimizationApplied'] is True
    assert disabled['aiReoptimizationApplied'] is False
