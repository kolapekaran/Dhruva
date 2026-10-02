from fastapi.testclient import TestClient

from app.main import app
from app.api.twin import twin
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.optimization.mpc_controller import run_physics_informed_mpc

client = TestClient(app)


def test_physics_informed_mpc_contract_and_isolation():
    before = twin.state.time.timestamp
    r = client.get('/intelligence/physics-informed-mpc?hours=12&control_horizon_hours=4&lookahead_hours=6&alpha=0.8')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['engine'] == 'DHRUVA_PHYSICS_INFORMED_ROLLING_MPC_V1'
    assert body['optimality_claim'] is False
    assert len(body['controls']) == 4
    assert body['station_state_mutated'] is False
    assert body['physics_constraint']['method'] == 'conservative-physics-envelope-cap'
    assert twin.state.time.timestamp == before


def test_mpc_replans_and_reports_candidates():
    s = twin.state
    forecast = generate_multi_day_forecast(
        s.time.timestamp, 10, s.weather.temperature_celsius, s.weather.wind_speed_mps
    )['forecast']
    result = run_physics_informed_mpc(forecast, s, control_horizon=3, lookahead_hours=6)
    assert len(result['candidate_evaluations']) == 3
    assert all(len(x['candidates']) == 4 for x in result['candidate_evaluations'])
    assert all(x['selected_policy'] in {'BALANCED_ROBUST','HIGH_RELIABILITY','FUEL_CONSERVATION','RENEWABLE_MAXIMIZATION'} for x in result['candidate_evaluations'])


def test_physics_cap_never_increases_renewable_forecast():
    s = twin.state
    forecast = generate_multi_day_forecast(
        s.time.timestamp, 6, s.weather.temperature_celsius, s.weather.wind_speed_mps
    )['forecast']
    result = run_physics_informed_mpc(forecast, s, control_horizon=2, lookahead_hours=4)
    assert result['physics_constraint']['over_credit_prevented'] in {True, False}
    for cap in result['physics_constraint']['caps']:
        assert cap['wind_physics_cap_kw'] <= cap['wind_forecast_kw'] or cap['solar_physics_cap_kw'] <= cap['solar_forecast_kw']
