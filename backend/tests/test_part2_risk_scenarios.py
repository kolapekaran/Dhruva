from fastapi.testclient import TestClient
from app.main import app
from app.scenarios.simulator import ScenarioParameters, simulate_scenario
from app.ml.risk.risk_engine import assess_projection_risk


def test_custom_scenario_simulation():
    result = simulate_scenario(ScenarioParameters(wind_reduction_percent=50, load_increase_percent=20), 24)
    assert len(result["points"]) == 24
    assert result["metrics"]["fuel_consumed_liters"] >= 0
    assert 0 <= result["metrics"]["minimum_soc_percent"] <= 100


def test_risk_score_is_bounded():
    result = assess_projection_risk({"minimum_soc_ratio": 0.1, "final_fuel_liters": 1000,
                                     "service_level_percent": 70, "critical_load_failure_steps": 1,
                                     "load_shed_energy_kwh": 100, "forecast_confidence": {"average_confidence": 0.5}}, [])
    assert 0 <= result["overall_risk_percent"] <= 100
    assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_part2_endpoints():
    client = TestClient(app)
    for path in ("/risk?hours=24", "/risk/anomaly", "/risk/insights?hours=24",
                 "/scenarios/simulate?hours=24&wind_reduction_percent=50",
                 "/scenarios/compare?hours=24&solar_reduction_percent=30"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
