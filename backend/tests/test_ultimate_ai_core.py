from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ultimate_ai_core_contract_and_governance():
    response = client.get('/intelligence/ultimate-ai')
    assert response.status_code == 200
    body = response.json()
    assert body['state_preserving'] is True
    assert body['field_validated'] is False
    for key in ['world_model','physics_informed','forecast_ensemble','battery_digital_twin','asset_rul','safe_rl_challenger','causal_engine','model_selector','gnn_dependency']:
        assert key in body['models']
    assert body['governance']['human_approval_required'] is True
    assert body['governance']['safety_shield_authoritative'] is True
    assert body['governance']['automatic_equipment_control'] is False
    assert body['governance']['model_promotion_automatic'] is False

def test_ultimate_ai_core_does_not_mutate_twin():
    from app.api.twin import twin
    before = (twin.state.time.simulation_step, twin.state.fuel.fuel_remaining_liters, twin.state.battery.soc_ratio)
    assert client.get('/intelligence/ultimate-ai').status_code == 200
    after = (twin.state.time.simulation_step, twin.state.fuel.fuel_remaining_liters, twin.state.battery.soc_ratio)
    assert after == before
