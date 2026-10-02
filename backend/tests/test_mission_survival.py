from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_mission_survival_baseline_contract():
    response = client.post('/intelligence/mission-survival', json={})
    assert response.status_code == 200
    body = response.json()
    assert body['station'] == 'Maitri Research Station'
    assert body['horizon_hours'] == 72
    assert body['ensemble_members'] == 250
    assert set(body['survival_horizon_hours']) == {'p10', 'p50', 'p90'}
    assert body['data_status'] == 'REFERENCE_STRESS_ENSEMBLE'
    assert 'not a calibrated probability' in body['provenance']


def test_mission_survival_stress_path():
    response = client.post('/intelligence/mission-survival', json={
        'horizon_hours': 72,
        'ensemble_members': 100,
        'wind_factor': 0.4,
        'solar_factor': 0.2,
        'load_factor': 1.3,
        'generator_available': False,
        'resupply_delay_hours': 48,
        'resupply_quantity_liters': 5000,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'SURVIVAL_MODE'
    assert body['assumptions']['resupply_delay_hours'] == 48
    assert body['assumptions']['resupply_quantity_liters'] == 5000.0
    assert 0 <= body['survival_percent'] <= 100


def test_mission_survival_rejects_invalid_range():
    response = client.post('/intelligence/mission-survival', json={'ensemble_members': 10})
    assert response.status_code == 422


def test_mission_survival_resupply_timing_and_no_resupply_mode():
    immediate = client.post('/intelligence/mission-survival', json={
        'horizon_hours': 72, 'ensemble_members': 100, 'resupply_delay_hours': 0,
        'resupply_quantity_liters': 5000, 'wind_factor': 0.6, 'solar_factor': 0.5,
        'load_factor': 1.0, 'generator_available': True,
    }).json()
    delayed = client.post('/intelligence/mission-survival', json={
        'horizon_hours': 72, 'ensemble_members': 100, 'resupply_delay_hours': 72,
        'resupply_quantity_liters': 5000, 'wind_factor': 0.6, 'solar_factor': 0.5,
        'load_factor': 1.0, 'generator_available': True,
    }).json()
    none = client.post('/intelligence/mission-survival', json={
        'horizon_hours': 72, 'ensemble_members': 100, 'resupply_delay_hours': 0,
        'resupply_quantity_liters': 0, 'wind_factor': 0.6, 'solar_factor': 0.5,
        'load_factor': 1.0, 'generator_available': True,
    }).json()
    assert immediate['assumptions']['resupply_quantity_liters'] == 5000.0
    assert delayed['assumptions']['resupply_delay_hours'] == 72
    assert none['assumptions']['resupply_quantity_liters'] == 0.0
    assert immediate['minimum_fuel_liters'] >= delayed['minimum_fuel_liters']
    assert delayed['minimum_fuel_liters'] >= none['minimum_fuel_liters']
