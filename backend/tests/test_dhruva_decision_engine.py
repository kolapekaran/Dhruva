from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_decision_trace_contract():
    r = client.get('/decision/trace?hours=24')
    assert r.status_code == 200, r.text
    b = r.json()
    assert b['engine'].startswith('DHRUVA_DECISION_ENGINE')
    assert b['decision_id'].startswith('DEC-')
    assert b['baseline_comparison']['baseline']['engine'] == 'rule_based_baseline'
    assert 'safety_validation' in b
    assert isinstance(b['trace'], list) and len(b['trace']) >= 4
    assert b['optimality_claim'] is False


def test_72h_stress_test_is_isolated_and_structured():
    before = client.get('/twin/state').json()
    r = client.get('/decision/stress-test/72h')
    assert r.status_code == 200, r.text
    b = r.json()
    assert b['horizon_hours'] == 72
    assert len(b['points']) == 72
    assert len(b['events']) >= 6
    assert 'GENERATOR_FAILURE' in [x['event'] for x in b['events']]
    assert b['metrics']['fuel_consumed_liters'] >= 0
    after = client.get('/twin/state').json()
    assert after['battery']['soc_ratio'] == before['battery']['soc_ratio']
    assert after['fuel']['fuel_remaining_liters'] == before['fuel']['fuel_remaining_liters']


def test_phase2_uncertainty_asset_and_autonomy_contract():
    r = client.get('/decision/trace?hours=24')
    assert r.status_code == 200, r.text
    b = r.json()
    assert b['planning_case'] == 'P90_LOAD_P10_RENEWABLE'
    assert 'uncertainty' in b
    assert set(b['uncertainty']['bands']['load_kw']) == {'p10', 'p50', 'p90'}
    assert 'asset_health' in b
    assert 'fuel_autonomy' in b
    assert b['candidate_plan']['asset_awareness']['generator_health_percent'] >= 0


def test_phase2_assessment_endpoint():
    r = client.get('/decision/assessment?hours=24')
    assert r.status_code == 200, r.text
    b = r.json()
    assert b['engine'] == 'DHRUVA_INTELLIGENCE_ASSESSMENT_V2'
    assert b['planning_case'] == 'P90_LOAD_P10_RENEWABLE'
    assert b['dynamic_reserve_percent'] >= 20
    assert 'fuel_autonomy' in b
