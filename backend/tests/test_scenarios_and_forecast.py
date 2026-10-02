from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.scenarios import ScenarioEngine, ScenarioInput, ScenarioType
from app.ml.evaluation.forecast_metrics import evaluate_forecast
from app.ml.forecasting.forecast_engine import generate_reference_forecast


def test_scenario_engine_detects_combined_extreme():
    result = ScenarioEngine().evaluate(
        ScenarioInput(
            temperature=-40,
            wind_percent=40,
            solar_available=False,
            fuel_percent=15,
        )
    )
    assert ScenarioType.EXTREME_COLD.value in result.scenarios
    assert ScenarioType.LOW_WIND.value in result.scenarios
    assert ScenarioType.NO_SOLAR.value in result.scenarios
    assert ScenarioType.FUEL_SHORTAGE.value in result.scenarios
    assert ScenarioType.COMBINED_EXTREME.value in result.scenarios
    assert result.estimated_risk <= 100


def test_reference_forecast_is_24_hours_and_physically_bounded():
    rows = generate_reference_forecast(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        hours=24,
    )
    assert len(rows) == 24
    for row in rows:
        assert 0 <= row.solar_kw <= 50
        assert 0 <= row.wind_kw <= 100
        assert row.load_kw >= 0


def test_forecast_metrics():
    metrics = evaluate_forecast([10, 20, 30], [11, 18, 30])
    assert round(metrics["mae"], 6) == round(1.0, 6)
    assert metrics["rmse"] > 0
    assert metrics["mape_percent"] > 0


def test_scenario_evaluation_api():
    client = TestClient(app)
    response = client.get(
        "/scenarios/evaluate",
        params={
            "temperature": -40,
            "wind_percent": 40,
            "solar_available": False,
            "fuel_percent": 15,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "COMBINED_EXTREME" in body["scenarios"]
