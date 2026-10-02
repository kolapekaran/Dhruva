import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import alerts, energy, fuel, scenarios, station, twin, forecasts, ems, projection, risk, dashboard, reports, optimization, settings, analytics, live, health, intelligence, integration_adapter, mission_survival, mission_autonomy, decision_engine, validation, ultimate_ai

app = FastAPI(
    title="DHRUVA",
    version="2.0.0",
    description="Computational Digital Twin foundation for a polar research-station energy-management system.",
)

app.include_router(twin.router)
app.include_router(energy.router)
app.include_router(fuel.router)
app.include_router(alerts.router)
app.include_router(scenarios.router)
app.include_router(station.router)
app.include_router(forecasts.router)
app.include_router(ems.router)
app.include_router(projection.router)
app.include_router(risk.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(optimization.router)
app.include_router(settings.router)
app.include_router(analytics.router)
app.include_router(live.router)
app.include_router(health.router)
app.include_router(intelligence.router)
app.include_router(mission_survival.router)
app.include_router(mission_autonomy.router)
app.include_router(integration_adapter.router)
app.include_router(decision_engine.router)
app.include_router(validation.router)
app.include_router(ultimate_ai.router)

# Frontend development origins. Production deployments should override these
# with the deployed frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("POLAR_EMS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,https://polar-ems-delta.vercel.app").split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status":"ok","service":"dhruva"}
