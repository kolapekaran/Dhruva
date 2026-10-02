from fastapi.testclient import TestClient
from app.main import app
from app.ml.evaluation.backtesting import parse_csv_text, parse_observation, run_backtest

client = TestClient(app)


def _rows(n=12):
    return [
        {
            "timestamp": f"2026-01-01T{h:02d}:00:00+00:00",
            "temperature_celsius": -20 + (h % 3),
            "wind_speed_mps": 8 + (h % 4),
            "solar_irradiance_w_m2": 100 if 8 <= h <= 18 else 0,
            "snowfall_rate": 0,
            "load_kw": 60 + (h % 5),
            "solar_kw": 8 if 8 <= h <= 18 else 0,
            "wind_kw": 20 + (h % 3),
            "provenance": "REFERENCE",
        }
        for h in range(n)
    ]


def test_schema_endpoint_exposes_real_data_contract():
    r = client.get('/intelligence/historical/schema')
    assert r.status_code == 200
    assert 'timestamp' in r.json()['required_columns']
    assert 'FIELD_TELEMETRY' in r.json()['provenance_values']


def test_historical_ingest_is_non_mutating_by_default():
    r = client.post('/intelligence/historical/ingest', json={"observations": _rows(6), "persist": False})
    assert r.status_code == 200, r.text
    assert r.json()['storage']['storage'] == 'request_only'
    assert r.json()['field_validated'] is False


def test_backtest_runs_chronological_holdout():
    r = client.post('/intelligence/historical/backtest', json={"observations": _rows(), "calibration_fraction": 0.6})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['engine'] == 'DHRUVA_HISTORICAL_BACKTEST_V1'
    assert body['evaluation']['chronological_holdout'] is True
    assert body['evaluation']['metrics']['load_kw']['status'] == 'EVALUATED'
    assert body['evaluation']['calibration']['load_kw']['method'] == 'split_conformal_absolute_residual'
    assert body['field_validated'] is False
    assert body['station_state_mutated'] is False


def test_csv_backtest_contract():
    csv = "timestamp,temperature_celsius,wind_speed_mps,load_kw,solar_kw,wind_kw,provenance\n" + "\n".join(
        f"2026-01-01T{h:02d}:00:00+00:00,-20,8,60,0,20,REFERENCE" for h in range(8)
    )
    r = client.post('/intelligence/historical/backtest-csv?calibration_fraction=0.5', data=csv, headers={'content-type':'text/plain'})
    assert r.status_code == 200, r.text
    assert r.json()['dataset']['sample_count'] == 8


def test_duplicate_timestamps_are_rejected():
    rows = _rows(4)
    rows[1]['timestamp'] = rows[0]['timestamp']
    r = client.post('/intelligence/historical/backtest', json={"observations": rows})
    assert r.status_code == 422


def test_unsorted_backtest_is_rejected_instead_of_silently_sorted():
    rows = _rows(8)
    rows[0], rows[1] = rows[1], rows[0]
    r = client.post('/intelligence/historical/backtest', json={'observations': rows})
    assert r.status_code == 422
    assert 'chronological' in r.json()['detail']


def test_historical_readiness_reports_artifact_integrity_without_field_claim():
    r = client.get('/intelligence/historical/readiness')
    assert r.status_code == 200
    body = r.json()
    assert body['engine'] == 'DHRUVA_HISTORICAL_READINESS_V1'
    assert body['field_validation_status'] == 'NOT_ESTABLISHED'
    assert body['station_state_mutated'] is False
    assert body['artifact_manifest']['artifact_count'] >= 1
