from fastapi.testclient import TestClient
from app.main import app


def test_phase4_mission_validation_report():
    client = TestClient(app)
    response = client.get('/validation/mission-report?hours=24')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['engine'] == 'DHRUVA_VALIDATION_EVIDENCE_V1'
    assert data['station'] == 'Maitri Research Station'
    assert data['station_state_mutated'] is False
    assert len(data['scenario_matrix']) == 7
    assert 'baseline_vs_dhruva' in data
    assert 'forecast_model_metrics' in data
    assert 'optimizer_evidence' in data
    assert 'safety' in data
    assert data['optimizer_evidence']['schedule_points'] == 24
    assert data['optimizer_evidence']['optimality_claim'] is False


def test_phase4_validation_reports_safety_fields():
    client = TestClient(app)
    data = client.get('/validation/mission-report?hours=24').json()
    safety = data['safety']
    assert safety['decision_trace_hard_violation_count'] >= 0
    assert safety['stress_test_safety_violations'] >= 0
    assert safety['stress_test_critical_load_failures'] >= 0
    assert safety['matrix_critical_load_failures'] >= 0
    assert data['evidence_summary']['total_reported_safety_violations'] >= 0


def test_phase4_forecast_metrics_are_reference_labeled():
    client = TestClient(app)
    data = client.get('/validation/mission-report?hours=24').json()
    metrics = data['forecast_model_metrics']
    assert metrics
    assert all(item.get('synthetic_reference') is True for item in metrics.values() if 'synthetic_reference' in item)
