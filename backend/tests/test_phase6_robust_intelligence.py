from fastapi.testclient import TestClient
from app.main import app
from app.api.twin import twin
from app.optimization.robust_optimizer import robust_scenario_evaluation
from app.ml.forecasting.multi_day import generate_multi_day_forecast

client = TestClient(app)


def test_robust_optimization_contract_and_isolation():
    before = twin.state.time.timestamp
    r = client.get('/intelligence/robust-optimization?hours=24&alpha=0.8')
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['engine'] == 'DHRUVA_ROBUST_SCENARIO_ENGINE_V1'
    assert data['optimality_claim'] is False
    assert data['risk_measure'].startswith('CVaR')
    assert data['scenario_count'] == 9
    assert data['cvar']['tail_count'] >= 1
    assert data['station_state_mutated'] is False
    assert twin.state.time.timestamp == before


def test_generator_failure_is_evaluated_without_diesel():
    forecast = generate_multi_day_forecast(twin.state.time.timestamp, 12, twin.state.weather.temperature_celsius, twin.state.weather.wind_speed_mps)['forecast']
    result = robust_scenario_evaluation(forecast, twin.state)
    failure = next(x for x in result['scenario_results'] if x['scenario'] == 'GENERATOR_FAILURE')
    assert failure['generator_available'] is False
    assert failure['fuel_liters'] == 0


def test_cvar_is_at_least_tail_threshold():
    r = client.get('/intelligence/robust-optimization?hours=12&alpha=0.75')
    assert r.status_code == 200
    body = r.json()
    assert body['cvar']['cvar'] >= body['cvar']['threshold']


def test_physics_consistency_is_reported():
    r = client.get('/intelligence/robust-optimization?hours=12')
    assert r.status_code == 200
    physics = r.json()['physics_consistency']
    assert physics['checked_points'] == 12
    assert physics['field_validated'] is False
    assert physics['status'] in {'PASS', 'REVIEW'}
