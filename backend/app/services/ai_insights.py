"""Explainable AI-style insights assembled from forecast, risk and Twin state."""
from __future__ import annotations


def generate_ai_insights(state, risk: dict, projection_metrics: dict) -> list[dict]:
    insights: list[dict] = []
    components = risk.get("components", {})

    if components.get("battery_soc_risk_percent", 0) >= 20:
        insights.append({"priority": "high", "type": "battery", "title": "Battery reserve is under pressure", "message": "Shift discretionary demand away from the battery and preserve the configured reserve.", "reason": "Projected minimum SOC is approaching or crossing the safe reserve."})
    if components.get("fuel_reserve_risk_percent", 0) >= 20:
        insights.append({"priority": "high", "type": "fuel", "title": "Fuel reserve is at risk", "message": "Conserve diesel and review resupply timing before the protected reserve is reached.", "reason": "Projected fuel level is approaching the emergency reserve."})
    if projection_metrics.get("renewable_share", 0) < 0.40:
        insights.append({"priority": "medium", "type": "renewable", "title": "Diesel dependency is elevated", "message": "Prefer renewable generation whenever available and use stored energy strategically.", "reason": "Projected renewable share is below 40%."})
    if projection_metrics.get("load_shed_energy_kwh", 0) > 0:
        insights.append({"priority": "critical", "type": "load", "title": "Load shedding is projected", "message": "Reduce flexible loads and protect critical services.", "reason": "The Digital Twin projects unmet requested demand."})
    if components.get("extreme_weather_risk_percent", 0) >= 25:
        insights.append({"priority": "medium", "type": "weather", "title": "Extreme weather may change the energy balance", "message": "Prepare for higher heating demand and renewable variability.", "reason": "The forecast contains a meaningful share of extreme cold/high-wind conditions."})
    if not insights:
        insights.append({"priority": "low", "type": "status", "title": "Station operating within projected margins", "message": "Maintain current safety-first EMS operation and continue monitoring forecast changes.", "reason": "No major projected resilience constraint was detected."})
    return insights
