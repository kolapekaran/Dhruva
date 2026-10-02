from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_mission_autopilot_composes_full_decision_chain_without_mutation():
    r = client.get('/intelligence/mission-autopilot?horizon_hours=72&ensemble_members=50')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['engine'] == 'DHRUVA_MISSION_AUTOPILOT_V1'
    assert body['current_posture'] in {'NORMAL', 'CONSERVATION', 'CONTINGENCY', 'SURVIVAL'}
    assert len(body['timeline']) >= 6
    assert len(body['strategy_options']) == 4
    assert len(body['counterfactual_lab']) >= 3
    assert body['decision_trace']['steps'] == [
        'DATA', 'FORECAST', 'RISK', 'OPTIONS', 'CONSTRAINTS', 'SELECTED_POSTURE',
        'EXPECTED_IMPACT', 'SAFETY_CHECK', 'OPERATOR_APPROVAL'
    ]
    assert body['operator_gate']['approval_required_for_strategy_change'] is True
    assert body['operator_gate']['automatic_equipment_control'] is False
    assert body['provenance']['station_state_mutated'] is False
    assert body['provenance']['field_validated'] is False


def test_mission_autopilot_is_deterministic_for_same_state_and_seeded_inputs():
    a = client.get('/intelligence/mission-autopilot?horizon_hours=72&ensemble_members=50').json()
    b = client.get('/intelligence/mission-autopilot?horizon_hours=72&ensemble_members=50').json()
    assert a['current_posture'] == b['current_posture']
    assert a['worst_case'] == b['worst_case']
    assert [(x['window'], x['action']) for x in a['timeline']] == [(x['window'], x['action']) for x in b['timeline']]
    assert [x['scenario'] for x in a['counterfactual_lab']] == [x['scenario'] for x in b['counterfactual_lab']]
