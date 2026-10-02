from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_mission_survival_exposes_thermal_and_hierarchical_intelligence():
    r = client.post('/intelligence/mission-survival', json={'horizon_hours': 24, 'ensemble_members': 50})
    assert r.status_code == 200, r.text
    body = r.json()
    assert 'thermal_unserved_energy_kwh' in body
    assert 'recovered_waste_heat_kwh' in body
    assert body['hierarchical_control']['rolling_mpc']
    assert body['station_state_mutated'] is False

def test_strategy_benchmark_is_reproducible_and_non_mutating():
    r = client.get('/intelligence/strategy-benchmark?hours=24')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['engine'] == 'DHRUVA_COMPARATIVE_BENCHMARK_V1'
    assert 'baseline' in body and 'dhruva' in body and 'delta' in body
    assert body['field_validated'] is False
    assert body['station_state_mutated'] is False

def test_mission_assurance_matrix_is_non_mutating_and_explicitly_non_field_validated():
    r = client.get('/intelligence/mission-assurance?horizon_hours=72&ensemble_members=100')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['engine'] == 'DHRUVA_MISSION_ASSURANCE_V1'
    assert body['scenario_count'] == 7
    assert len(body['scenario_matrix']) == 7
    assert body['field_validated'] is False
    assert body['station_state_mutated'] is False
    assert body['worst_case']['scenario'] == 'COMBINED_ASSET_STRESS'
