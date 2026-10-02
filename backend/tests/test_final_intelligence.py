from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.api.twin import twin
from app.ml.inference.predictor import asset_failure_probabilities
from app.ml.forecasting.multi_day import generate_multi_day_forecast

client=TestClient(app)

def test_intelligence_routes_and_bounds():
    paths=['/intelligence/weather','/intelligence/assets','/intelligence/loads','/intelligence/fuel','/intelligence/analytics?hours=24','/intelligence/optimization?hours=24','/intelligence/seasonal-plan?days=2','/intelligence/offline-mode','/intelligence/maintenance','/intelligence/resilience']
    for p in paths:
        r=client.get(p); assert r.status_code==200,(p,r.text)
    a=client.get('/intelligence/assets').json()
    assert 0<=a['battery']['soh_percent']<=100
    assert 0<=a['generator']['health_percent']<=100
    assert 0<=a['failure_probability']['battery_failure']<=1
    assert 0<=a['failure_probability']['generator_failure']<=1


def test_heat_recovery_intelligence_contract():
    r = client.get('/intelligence/heat-recovery-intelligence?hours=24')
    assert r.status_code == 200, r.text
    b = r.json()
    assert b['data_status'] == 'ENGINEERING_MODEL'
    assert b['advisory_only'] is True
    assert b['station_state_mutated'] is False
    assert len(b['forecast']) >= 4
    assert b['summary']['current_heating_demand_kwth'] >= 0
    assert b['summary']['current_recovered_heat_kwth'] >= 0

def test_telemetry_ingestion_updates_weather_and_history():
    payload={'timestamp':'2026-01-02T12:00:00+00:00','temperature_celsius':-42,'wind_speed_mps':18,'solar_irradiance_w_m2':120,'snowfall_rate':3,'load_kw':80,'battery_soc_percent':55,'fuel_percent':70}
    r=client.post('/intelligence/telemetry',json=payload); assert r.status_code==200,r.text
    s=client.get('/intelligence/weather').json(); assert s['temperature_celsius']==-42; assert s['wind_speed_mps']==18
    h=client.get('/intelligence/telemetry/history?limit=2').json(); assert len(h)>=1

def test_load_action_contract():
    r=client.post('/intelligence/load-action?shift_flexible_kw=4'); assert r.status_code==200
    b=r.json(); assert b['critical_protected'] is True; assert b['shifted_kw']>=0

def test_coordination_balances_surplus_and_deficit():
    r=client.post('/intelligence/coordination',json=[{'station_id':'A','load_kw':20,'renewable_kw':50},{'station_id':'B','load_kw':40,'renewable_kw':10}])
    assert r.status_code==200; b=r.json(); assert b['transferable_surplus_kw']==30; assert b['unmet_after_local_balance_kw']==0

def test_asset_models_are_loadable_and_probabilities_bounded():
    p=asset_failure_probabilities(-40,15,0,80,40,60,85,1000)
    assert set(p)=={'battery_failure','generator_failure'}
    assert all(0<=v<=1 for v in p.values())

def test_polar_night_reference_forecast_is_zero_solar():
    f=generate_multi_day_forecast(datetime(2026,6,1,tzinfo=timezone.utc),24)
    assert all(x['solar_irradiance_w_m2']==0 for x in f['forecast'])
    assert all(x['solar_kw']==0 for x in f['forecast'])
    assert all(x['polar_night'] for x in f['forecast'])

def test_optimization_schedule_is_feasible_and_renewable_first():
    b=client.get('/intelligence/optimization?hours=24').json(); s=b['summary']
    assert b['optimality_claim'] is False
    assert s['fuel_liters']>=0 and 0<=s['service_level_percent']<=100
    for row in b['schedule']:
        assert row['battery_discharge_kw']>=0 and row['battery_charge_kw']>=0
        assert row['diesel_kw']>=0 and row['fuel_remaining_liters']>=0

def test_websocket_live_contract():
    with client.websocket_connect('/ws/live') as ws:
        first=ws.receive_json(); assert 'time' in first and 'battery' in first
        ws.send_text('ping'); second=ws.receive_json(); assert 'generation' in second


def test_what_if_comparison_uses_shared_ml_forecast():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    response = client.post('/api/intelligence/resilience/compare', json={
        'scenarioKey': 'LOW_WIND',
        'hours': 6,
        'startOffsetHours': 0,
        'aiReoptimization': True,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload['forecastSource'] == 'integrated_ai_ml_reference_weather'
    assert payload['dataStatus'] == 'ENGINEERING_MODEL'
    assert payload['aiReoptimizationApplied'] is True
    assert 'baseline' in payload and 'whatIf' in payload and 'delta' in payload
    assert payload['whatIf']['points']


def test_risk_endpoint_returns_backend_risk_series():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    response = client.get('/risk?hours=24')
    assert response.status_code == 200
    body = response.json()
    series = body.get('risk_series')
    assert isinstance(series, list) and len(series) > 0
    assert series[0]['hour_offset'] == 0
    assert {'overall','weather','fuel','battery','service'}.issubset(series[0])

