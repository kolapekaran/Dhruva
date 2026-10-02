from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import STATION_CONFIG
from app.digital_twin.station_twin import StationTwin, StationTwinInputs

client = TestClient(app)


def test_frontend_cors_and_ui_contracts():
    r = client.get('/dashboard?hours=24', headers={'Origin': 'http://localhost:3000'})
    assert r.status_code == 200
    assert r.headers.get('access-control-allow-origin') == 'http://localhost:3000'
    for path in ('/settings', '/analytics/history', '/health/detailed'):
        assert client.get(path).status_code == 200


def test_history_analytics_empty_or_valid_shape():
    data = client.get('/analytics/history?limit=10').json()
    assert {'count', 'series', 'summary'} <= data.keys()
    assert data['count'] == len(data['series'])


def test_diesel_cannot_generate_without_fuel():
    twin = StationTwin()
    twin.state.fuel.fuel_remaining_liters = 0.0
    result = twin.step(StationTwinInputs(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        outdoor_temperature_celsius=-20,
        wind_speed_mps=0,
        solar_irradiance_w_m2=0,
        diesel_power_request_kw=100,
        diesel_running=True,
    ))
    assert result.diesel_power_kw == 0.0
    assert result.state.fuel.fuel_remaining_liters == 0.0


def test_physical_configuration_is_exposed_consistently():
    data = client.get('/settings').json()
    assert data['battery']['capacity_kwh'] == STATION_CONFIG.battery.capacity_kwh
    assert data['solar']['installed_capacity_kw'] == STATION_CONFIG.solar.installed_capacity_kw
    assert data['wind']['installed_capacity_kw'] == STATION_CONFIG.wind.installed_capacity_kw


def test_openapi_and_validation_contracts_are_available():
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/docs').status_code == 200
    assert client.get('/forecasts/horizon?hours=0').status_code == 422
    assert client.get('/forecasts/multi-day?hours=25').status_code == 422
    assert client.get('/reports?hours=169').status_code == 200
    assert client.get('/reports?hours=8761').status_code == 422


def test_frontend_snapshot_future_is_backend_reconciled():
    now = client.get('/api/intelligence/snapshot?hourOffset=0').json()
    future = client.get('/api/intelligence/snapshot?hourOffset=72').json()
    for data in (now, future):
        pb = data['powerBalance']
        expected_gen = pb['dieselGenKw'] + pb['windGenKw'] + pb['solarGenKw']
        assert pb['totalGenerationKw'] == pytest.approx(expected_gen, abs=1e-6)
        assert pb['netBalanceKw'] == pytest.approx(expected_gen + pb['batteryPowerKw'] - pb['totalLoadKw'], abs=1e-6)
    assert future['fuel']['currentVolumeLiters'] <= now['fuel']['currentVolumeLiters']
    assert future['systemTime'] != now['systemTime']
    assert future['reserve']['currentReservePercent'] >= future['reserve']['targetReservePercent'] - 1e-6


def test_frontend_snapshot_uses_canonical_asset_values():
    data = client.get('/api/intelligence/snapshot?hourOffset=0').json()
    dg = next(x for x in data['generators'] if x['id'] == 'DG-01')
    assert data['powerBalance']['dieselGenKw'] == pytest.approx(dg['currentOutputKw'], abs=1e-6)
    wind = next(x for x in data['renewables'] if x['type'] == 'Wind Turbine')
    assert data['powerBalance']['windGenKw'] == pytest.approx(wind['currentOutputKw'], abs=1e-6)


def test_resilience_is_backend_derived_and_has_quantitative_coverage():
    data = client.get('/api/intelligence/resilience?hours=72').json()
    assert data['dataStatus'] == 'ENGINEERING_MODEL'
    assert data['reserveSemantics']['targetPercent'] >= data['reserveSemantics']['minimumPercent']
    assert data['criticalLoadCoverage']
    assert all('requestedKw' in x and 'servedKw' in x and 'coveragePercent' in x for x in data['criticalLoadCoverage'])


def test_frontend_has_no_synthetic_chart_fallbacks():
    root = Path(__file__).resolve().parents[2] / 'frontend' / 'src'
    resilience = (root / 'tabs' / '06-resilience' / 'ResilienceTab.tsx').read_text()
    analytics = (root / 'tabs' / '07-analytics' / 'AnalyticsTab.tsx').read_text()
    assert 'Math.sin' not in resilience and 'Math.cos' not in resilience
    assert "value: dieselMwh ||" not in analytics
    assert "value: solarMwh ||" not in analytics
    assert "value: windMwh ||" not in analytics
    assert "value: 85" not in analytics


def test_energy_snapshot_balance_and_battery_direction_contract():
    data = client.get('/api/intelligence/snapshot?hourOffset=0').json()
    pb = data['powerBalance']
    battery = data['battery']
    expected_generation = pb['dieselGenKw'] + pb['windGenKw'] + pb['solarGenKw']
    assert pb['totalGenerationKw'] == pytest.approx(expected_generation, abs=1e-6)
    assert pb['netBalanceKw'] == pytest.approx(expected_generation + pb['batteryPowerKw'] - pb['totalLoadKw'], abs=1e-6)
    if battery['currentPowerKw'] > 0:
        assert battery['status'] == 'DISCHARGING'
    elif battery['currentPowerKw'] < 0:
        assert battery['status'] == 'CHARGING'
    else:
        assert battery['status'] == 'IDLE'


def test_energy_and_assets_ui_are_source_labelled_and_do_not_claim_static_live_data():
    root = Path(__file__).resolve().parents[2] / 'frontend' / 'src'
    energy = (root / 'tabs' / '03-energy' / 'EnergyTab.tsx').read_text()
    assets = (root / 'tabs' / '04-assets-loads' / 'AssetsLoadsTab.tsx').read_text()
    assert 'SOURCE · {forecastSource}' in energy
    assert 'snapshot.battery.status' in energy
    assert 'sourceLabel' in assets
    assert 'Select an asset to inspect the authoritative station state' in assets
