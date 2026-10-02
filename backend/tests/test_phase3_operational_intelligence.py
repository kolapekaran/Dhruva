from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_operational_posture_is_advisory():
    r = client.get('/intelligence/operational-posture?hours=24')
    assert r.status_code == 200
    data = r.json()
    assert data['posture'] in {'NORMAL', 'CONTINGENCY_READY', 'SURVIVAL_MODE'}
    assert data['station_state_mutated'] is False
    assert 'recommended_actions' in data


def test_resupply_decision_is_calculated():
    r = client.get('/intelligence/resupply-decision?hours=168&lead_time_hours=72')
    assert r.status_code == 200
    data = r.json()
    assert data['recommended_quantity_liters'] >= 0
    assert data['projected_fuel_at_lead_time_liters'] >= 0
    assert data['station_state_mutated'] is False


def test_maintenance_posture_has_health_and_risk():
    r = client.get('/intelligence/maintenance-posture')
    assert r.status_code == 200
    data = r.json()
    assert 'health' in data
    assert 'failure_risk' in data
    assert 'actions' in data


def test_operator_action_is_explicit_and_auditable():
    r = client.post('/intelligence/operator-action', json={
        'decision_id': 'DEC-TEST-001',
        'action': 'ACKNOWLEDGE',
        'operator': 'TEST_OPERATOR',
        'notes': 'Phase 3 test',
    })
    assert r.status_code == 200
    action = r.json()
    assert action['decision_id'] == 'DEC-TEST-001'
    assert action['action'] == 'ACKNOWLEDGE'

    log = client.get('/intelligence/operator-action-log?limit=5')
    assert log.status_code == 200
    assert any(x['action_id'] == action['action_id'] for x in log.json()['actions'])


def test_operator_action_rejects_unknown_action():
    r = client.post('/intelligence/operator-action', json={
        'decision_id': 'DEC-TEST-002',
        'action': 'EXECUTE_UNKNOWN',
    })
    assert r.status_code == 400
