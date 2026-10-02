from fastapi.testclient import TestClient
from app.main import app
from app.ml.evaluation.calibration import split_conformal_evaluation, compare_forecasters

client = TestClient(app)


def test_split_conformal_uses_separate_evaluation_split():
    result = split_conformal_evaluation(
        [10, 12, 14, 16, 18, 20], [11, 11, 15, 15, 17, 22],
        [9, 13, 15, 17, 19, 21], [10, 12, 16, 16, 18, 20], alpha=0.10
    )
    assert result['method'] == 'split_conformal_absolute_residual'
    assert result['calibration_samples'] == 6
    assert result['evaluation_samples'] == 6
    assert 0 <= result['evaluation']['coverage_percent'] <= 100
    assert result['field_validated'] is False


def test_model_comparison_selects_lowest_held_out_mae():
    result = compare_forecasters([10, 20, 30, 40], {
        'MODEL_A': [11, 19, 31, 41],
        'MODEL_B': [15, 25, 35, 45],
    })
    assert result['recommended_model'] == 'MODEL_A'
    assert result['promotion_requires_operator_review'] is True


def test_calibration_api_contract():
    payload = {
        'calibration_actual': [10, 12, 14, 16],
        'calibration_predicted': [11, 11, 15, 15],
        'evaluation_actual': [9, 13, 15, 17],
        'evaluation_predicted': [10, 12, 16, 16],
        'alpha': 0.1,
    }
    r = client.post('/intelligence/calibration/split-conformal', json=payload)
    assert r.status_code == 200, r.text
    assert r.json()['target_coverage_percent'] == 90.0


def test_data_quality_endpoint_is_non_mutating():
    r = client.get('/intelligence/data-quality?limit=10')
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['source'] == 'external_telemetry_buffer'
    assert body['field_validated'] is False
