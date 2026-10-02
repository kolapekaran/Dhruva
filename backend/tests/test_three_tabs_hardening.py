from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend" / "src"


def read(name: str) -> str:
    return (FRONT / "tabs" / name).read_text(encoding="utf-8")


def test_simulator_exposes_backend_decision_impact():
    text = read("05-simulator/SimulatorTab.tsx")
    assert "Decision Impact" in text
    assert "BACKEND COMPARISON" in text
    assert "criticalLoadCoveragePercent" in text
    assert "loadShedEnergyKwh" in text


def test_resilience_has_no_fake_uptime_or_battery_hours():
    text = read("06-resilience/ResilienceTab.tsx")
    assert "Communication Uptime" not in text
    assert "Battery Backup" not in text
    assert "Online Generators" in text
    assert "RESERVE HORIZON" in text


def test_simulation_state_propagates_to_analytics_and_resilience():
    context = (FRONT / "integration" / "StationContext.tsx").read_text(encoding="utf-8")
    analytics = read("07-analytics/AnalyticsTab.tsx")
    resilience = read("06-resilience/ResilienceTab.tsx")
    assert "simulationTrajectory" in context
    assert "setSimulationTrajectory" in context
    assert "systemMode === 'SIMULATION'" in analytics
    assert "systemMode === 'SIMULATION'" in resilience


def test_analytics_year_range_matches_backend_projection_limit():
    text = read("07-analytics/AnalyticsTab.tsx")
    assert 'value="1Y">Reference Year' in text
    assert "8760" in text
    assert "8,760h reference projection" in text


def test_analytics_chart_reacts_to_view_mode():
    text = read("07-analytics/AnalyticsTab.tsx")
    assert "[series, range, view]" in text
