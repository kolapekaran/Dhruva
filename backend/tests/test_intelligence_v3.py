from fastapi.testclient import TestClient
from app.main import app
from app.api.twin import twin
from app.ems.intelligence_v3 import model_drift_check, battery_rul, polar_regime

client = TestClient(app)


def test_v3_mission_intelligence_contract():
    before = twin.state.time.timestamp
    r = client.get('/intelligence/mission-intelligence?hours=24')
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['engine'] == 'DHRUVA_INTELLIGENCE_ENGINE_V3'
    assert data['regime']['regime']
    assert data['uncertainty']['reference_intervals']['calibration_status'] == 'NOT_CALIBRATED'
    assert len(data['scenario_catalog']) == 9
    assert data['dependency_graph']['failure_propagation']['DG']
    assert data['station_state_mutated'] is False
    assert twin.state.time.timestamp == before


def test_v3_drift_screen():
    stable = model_drift_check([10, 11, 12], [10, 11, 12])
    drift = model_drift_check([20, 20, 20], [10, 10, 10])
    assert stable['status'] == 'STABLE'
    assert drift['status'] == 'DRIFT'


def test_v3_drift_api():
    r = client.post('/intelligence/model-drift', json={'actual': [20, 20, 20], 'predicted': [10, 10, 10]})
    assert r.status_code == 200
    assert r.json()['status'] == 'DRIFT'


def test_v3_counterfactual_isolated():
    r = client.get('/intelligence/counterfactual?scenario=GENERATOR_FAILURE&hours=24')
    assert r.status_code == 200
    data = r.json()
    assert data['station_state_mutated'] is False
    assert data['scenario'] == 'GENERATOR_FAILURE'
    assert data['estimated_additional_fuel_liters'] >= 0


def test_v3_asset_rul_is_explicitly_screening():
    result = battery_rul(twin.state)
    assert result['field_validated'] is False
    assert result['estimated_remaining_equivalent_cycles'] >= 0
