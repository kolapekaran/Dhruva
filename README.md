# DHRUVA — Polar Mission Intelligence & Energy Management System

DHRUVA is a mission-control and decision-intelligence platform for remote polar research stations, demonstrated against Maitri Research Station, Antarctica.

It combines a computational digital twin, energy/fuel/thermal intelligence, forecasting, uncertainty analysis, scenario simulation, robust optimization, rolling MPC, mission survival analysis, asset health, operator-supervised autonomy, explainability, auditability and historical validation into one decision loop:

**Sense → Predict → Stress → Optimize → Verify → Recommend → Approve → Audit → Learn**

> **Important:** This repository is an engineering/research prototype. The included ML artifacts and reference datasets are synthetic/engineering-reference data unless explicitly marked otherwise. They are **not** evidence of field calibration or measured Maitri telemetry.

---

## 1. What DHRUVA solves

Remote polar stations must maintain critical services while weather, renewable availability, fuel logistics, equipment health, thermal demand and communications can change quickly. DHRUVA is designed to answer:

- What is the station doing now?
- What is likely to happen over the next hours/days?
- What happens under adverse scenarios?
- How much fuel/energy reserve is available?
- Which assets should be preserved or committed?
- Which operating strategy is safer and more resource-efficient?
- What should the operator do now?
- Why was that recommendation produced?
- What happens if an assumption changes?
- Can the decision be reproduced and audited later?

DHRUVA is **advisory and human-supervised**. It does not directly command physical equipment.

---

## 2. Core system states

The integrated application uses three operating states:

### ONLINE
Live/backend telemetry and current station intelligence are available.

### OFFLINE
The application uses the last valid/cached state and remains read-only for operational safety.

### SIMULATION
A fully isolated simulated state can be explored without overwriting authoritative live station state.

---

## 3. Frontend mission-control application

The frontend is a React + TypeScript + Vite application styled with Tailwind CSS and Lucide icons.

### Seven operational tabs

1. **Command Center**
   - Primary mission-control interface
   - Station KPIs
   - Current operating posture
   - Live/connected status
   - 3D station digital twin
   - Energy-flow visualization
   - Mission Autopilot
   - Mission Assurance / survival intelligence
   - Ultimate AI Core
   - Operator decision context

2. **Optimization & Advisory**
   - Dispatch recommendations
   - Forecast/risk context
   - Optimization horizon
   - Strategy selection
   - Safety validation
   - Decision reasoning

3. **Energy**
   - Generation and demand
   - Battery state
   - Renewable contribution
   - Diesel generation
   - Energy balance and trends

4. **Assets & Loads**
   - Generators
   - Renewable assets
   - Battery assets
   - Station loads
   - Asset health and maintenance context
   - Critical / important / flexible load prioritization

5. **Simulator**
   - What-if scenarios
   - Environmental and asset disturbances
   - Isolated simulation state
   - Predicted consequences

6. **Resilience**
   - Failure scenarios
   - Survival posture
   - Critical-load protection
   - Recovery/contingency analysis
   - Mission assurance

7. **Analytics**
   - Historical trends
   - Forecast evidence
   - Validation metrics
   - Decision/operational analytics
   - Exportable reports

---

## 4. 3D Antarctic Digital Twin

The Command Center includes a standalone Maitri-inspired 3D operational model at:

`frontend/public/station-3d/polar-station-3d.html`

The scene represents:

- Main elevated research building
- Research/laboratory block
- Summer camp
- Workshop/utilities
- Pump house
- Fuel farm and tanks
- Diesel generator plant
- Electrical substation
- Communication/weather mast and radome
- Wind turbines
- Solar array
- Containerized battery storage
- Roads and snow terrain
- Service vehicles
- Utility poles/conductors

It supports operational visual states and animations including wind rotation, solar behavior, generator/radiator activity, battery cooling, energy-flow particles, status lights, vehicles, atmospheric snow and camera orbit/zoom/manual rotation.

The 3D twin is a **visual/operational representation**. The authoritative station state remains in the application/backend state model.

---

## 5. Forecasting and ML layer

DHRUVA contains reference ML artifacts for:

- Station load forecasting
- Solar generation forecasting
- Wind generation forecasting
- General asset-failure screening
- Generator-failure screening
- Battery-failure screening
- Multivariate anomaly detection

The implementation includes:

- Feature preprocessing
- Model inference
- Confidence estimation
- Forecast ensembles
- Multi-day forecasting
- Forecast metrics
- Historical backtesting
- Split-conformal calibration/evaluation
- Data-quality gates
- Model comparison / champion-challenger evaluation
- Model-drift analysis

### Reference model families

The included reference artifacts use scikit-learn/joblib models such as Random Forest regressors/classifiers and Isolation Forest anomaly detection.

The metrics JSON files intentionally identify the reference datasets as synthetic/engineering-reference data. They must not be presented as measured Antarctic performance.

---

## 6. Ultimate AI Core

The Ultimate AI layer is an integrated decision-support stack rather than a single black-box model.

### World-model / state-transition surrogate

Represents how station state can evolve under candidate actions and disturbances.

### Physics-informed energy reasoning

Uses engineering relationships and constraints for:

- Wind generation
- Solar generation
- Battery behavior
- Generator behavior
- Thermal demand
- Fuel consumption

### Forecast ensemble

Combines multiple prediction signals and uncertainty bands to support P10/P50/P90 engineering planning cases.

### Battery digital-twin intelligence

Provides mission context for:

- SOC
- SOH
- usable energy
- cycle/degradation pressure
- temperature/cold-stress context
- reserve constraints

### Asset health / RUL intelligence

Generator and asset health signals are connected to mission decisions so asset condition can influence strategy and runtime allocation.

### Safe-RL challenger architecture

The architecture provides a learning-based policy/challenger layer while keeping deterministic constraints and the Safety Shield authoritative. The repository does not claim field-trained RL performance.

### Adaptive model selection

The intelligence layer can use operating regime, uncertainty and data-quality context to select or weight appropriate decision pathways.

### Dependency/graph reasoning

Station assets and dependencies can be represented as a graph for impact propagation and future graph-learning integration.

### Causal mission reasoning

Connects chains such as:

`Weather → Renewable availability → Load/Thermal demand → Battery/Generator behavior → Fuel autonomy → Mission risk`

### Explainability

Recommendations expose contributing conditions, constraints, expected consequences and safety status rather than returning only a numerical prediction.

---

## 7. Robust optimization and control

DHRUVA contains several complementary optimization layers.

### Standard dispatch optimization

Determines generator/storage/renewable operating decisions under station constraints.

### Robust scenario optimization

Evaluates adverse futures including:

- Low wind
- Solar loss
- High load
- Blizzard
- Extreme cold
- Renewable collapse
- Generator failure
- Combined asset stress
- Renewable surplus

### CVaR-style tail-risk analysis

The robust layer evaluates expected loss and adverse-tail exposure rather than optimizing only an average forecast.

### Physics-informed rolling MPC

The rolling/receding-horizon controller evaluates near-term decisions repeatedly as the station state changes.

Supported strategy concepts include:

- Balanced robust operation
- High reliability
- Fuel conservation
- Renewable maximization

### Deterministic Safety Shield

Safety constraints remain authoritative over learning or optimization proposals.

---

## 8. Mission Survival & Mission Assurance

DHRUVA evaluates multi-day station survival rather than only instantaneous energy balance.

The mission layer considers:

- Fuel autonomy
- Battery reserve
- Generator availability
- Renewable uncertainty
- Critical-load service
- Thermal constraints
- Asset failures
- Adverse weather
- Combined disturbances
- Worst-case scenarios
- Operational posture

The mission assurance engine supports seeded multi-path scenario analysis and P10/P50-style survival horizons as engineering planning outputs.

---

## 9. Mission Autopilot — operator-supervised

DHRUVA can recommend a mission posture such as:

- NORMAL
- CONSERVATION
- CONTINGENCY
- SURVIVAL

The system can identify when a future condition is expected to require a strategy change and produce an advisory plan.

A consequential physical action still requires an authorized operator/control path.

### Decision Trace

Every major recommendation follows the conceptual chain:

`DATA → FORECAST → RISK → OPTIONS → CONSTRAINTS → SELECTED STRATEGY → EXPECTED IMPACT → SAFETY CHECK → OPERATOR APPROVAL`

This makes the decision explainable and auditable.

---

## 10. Thermal, fuel and resource intelligence

DHRUVA goes beyond electrical power.

### Thermal intelligence

- Heating demand context
- Temperature-driven load changes
- Generator heat-recovery context
- Thermal deficit detection
- Thermal-aware mission decisions

### Fuel intelligence

- Tank state
- Consumption rate
- Fuel autonomy
- Dynamic reserve
- Resupply-aware planning
- Fuel impact of candidate strategies

### Resource readiness

The architecture supports mission-level resource tracking for station survivability, with explicit provenance for non-electrical resource data.

---

## 11. Counterfactual / What-If Lab

Candidate futures can be evaluated without modifying authoritative live state.

Example disturbances:

- Wind reduction
- Solar loss
- High load
- Generator failure
- Battery degradation/stress
- Blizzard
- Extreme cold
- Renewable collapse
- Combined asset stress
- Resupply-delay style planning cases

The result can compare:

- Fuel use
- Critical-load coverage
- Battery reserve
- Thermal gap
- Generator runtime
- Risk/tail exposure
- Survival horizon
- Recommended operating posture

---

## 12. Mission Replay

Historical/recorded station states can be replayed conceptually through the backend mission/replay interfaces for analysis of:

- Telemetry state
- Forecasts
- Alerts
- Decisions
- Scenario conditions
- Operator actions

This supports training, incident review, debugging and validation workflows.

---

## 13. Historical data and validation

DHRUVA includes a historical observation/backtesting framework with provenance-aware observations.

Supported provenance categories include:

- FIELD_TELEMETRY
- REFERENCE
- SYNTHETIC
- SIMULATION

Validation checks include:

- Timestamp ordering
- Duplicate timestamps
- Target completeness
- Provenance counts
- Chronological calibration/evaluation split
- Forecast metrics
- Split-conformal evaluation
- Artifact integrity / SHA-256 manifest
- Data-quality readiness

CSV ingestion and local JSONL-style prototype storage are included.

The system intentionally reports when field validation has **not** been established.

---

## 14. Benchmarking

The backend contains benchmark/assessment pathways for comparing candidate strategies and baselines.

Useful evaluation metrics include:

- Fuel consumption
- Unserved energy
- Critical-load coverage
- Generator runtime
- Battery cycling/degradation pressure
- Renewable utilization
- Thermal recovery/use
- Tail risk
- Recovery/survival horizon
- Decision safety violations

Any quantitative superiority claim must be made only when the compared systems use the same inputs, constraints, scenarios and evaluation protocol.

---

## 15. Offline and edge-ready architecture

DHRUVA supports the three-state operating concept so loss of connectivity does not require the UI to fabricate live data.

Offline behavior is designed around:

- Last valid state
- Cached intelligence
- Read-only operation
- Local simulation
- Deferred synchronization architecture

Communication status is treated separately from physical station state.

---

## 16. Security, governance and auditability

The architecture includes:

- Operator approval gates
- Decision traceability
- Audit-log concepts
- Data provenance
- Model governance
- Champion/challenger comparison without automatic promotion
- Data-quality gates
- Explicit synthetic/reference-data labeling
- Safety validation before recommendation acceptance

The system should be deployed behind production authentication, network controls, secrets management and an approved industrial-control boundary before any real equipment integration.

---

## 17. Backend architecture

Backend stack:

- Python
- FastAPI
- Uvicorn
- NumPy
- scikit-learn
- Joblib
- ReportLab
- Pytest

Main backend domains:

```text
backend/app/
├── api/              REST/WebSocket API surface
├── digital_twin/     Station state, simulation and energy balance
├── ems/              Energy-management and intelligence orchestration
├── ml/               Forecasting, anomaly, risk, training, evaluation
├── models/           Physical/engineering station models
├── optimization/     Dispatch, robust optimization and MPC
├── scenarios/        Scenario generation, simulation and what-if analysis
├── services/         Forecast, fuel, optimization, alerts, reports, etc.
└── websocket/        Live update management
```

Major API groups include:

- `/health`
- `/twin/*`
- `/energy/*`
- `/fuel/*`
- `/alerts/*`
- `/scenarios/*`
- `/station/*`
- `/forecasts/*`
- `/ems/*`
- `/projection/*`
- `/risk/*`
- `/dashboard/*`
- `/reports/*`
- `/optimization/*`
- `/analytics/*`
- `/live/*`
- `/intelligence/*`
- `/mission-survival/*`
- `/mission-autonomy/*`
- `/decision/*`
- `/validation/*`
- `/ultimate-ai/*`
- `/ws/live`

Exact route definitions are the source of truth in `backend/app/api/`.

---

## 18. Frontend architecture

Frontend stack:

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Lucide React
- Recharts
- Motion

Key frontend areas:

```text
frontend/src/
├── components/             Shared mission-control components
├── components/advanced/    Digital-twin and intelligence components
├── integration/             Backend/station state integration
├── tabs/                   Seven operational tabs
├── assets/                 Maitri visual assets
└── App.tsx                 Application shell
```

The `StationContext` and integration layer provide the central frontend/backend station-state bridge.

---

## 19. Running locally

### Prerequisites

- Python 3.11+ recommended
- Node.js 20+ recommended
- npm

### Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend health check:

`http://localhost:8000/health`

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server is configured for port `3000`.

Open:

`http://localhost:3000`

The frontend integration layer can communicate with the FastAPI backend through the configured API base URL/environment configuration.

---

## 20. Testing

Run backend tests:

```bash
cd backend
pytest -q
```

The repository includes tests covering:

- Core station behavior
- Decision engine
- ML integration
- Digital-twin projection
- Risk and scenario logic
- Mission survival
- Mission autonomy
- Robust intelligence
- Physics-informed MPC
- Calibration/governance
- Historical backtesting
- Reports
- Frontend/backend integration hardening
- Ultimate AI Core

The exact pass count should always be taken from the current local test run rather than a historical release claim.

---

## 21. Environment configuration

Use `frontend/.env.example` as the frontend environment template.

Backend CORS can be configured with:

`POLAR_EMS_ALLOWED_ORIGINS`

Do not commit real API keys, credentials, production database secrets or private telemetry.

---

## 22. Data and model provenance

The repository includes reference ML artifacts because the application is designed to demonstrate an end-to-end decision pipeline.

Several included training datasets are physically grounded synthetic data. Their metric files explicitly mark them as synthetic and warn that they must not be presented as measured Antarctic telemetry.

For a field deployment, replace/retrain the reference models using approved station telemetry and establish:

1. Data-quality requirements
2. Chronological train/calibration/evaluation splits
3. Field validation protocol
4. Calibration monitoring
5. Drift detection
6. Model versioning
7. Independent safety validation
8. Rollback procedures

---

## 23. Safety and deployment boundary

DHRUVA is not a certified industrial control system.

For real deployment, recommendations must pass through an approved operational-control architecture with:

- authenticated operators
- least-privilege authorization
- network segmentation
- secure telemetry ingestion
- command validation
- fail-safe control logic
- independent safety interlocks
- cybersecurity monitoring
- tested rollback/fallback behavior
- formal acceptance testing

The application intentionally keeps AI/optimization recommendations separate from direct equipment actuation.

---

## 24. Repository cleanliness

This GitHub release intentionally contains **one project README only**. Historical phase notes, generated release markdown, nested READMEs, Python bytecode, pytest caches, Node modules and local build artifacts are excluded.

The source tree is organized for direct GitHub upload:

```text
DHRUVA/
├── README.md
├── backend/
└── frontend/
```

---

## 25. Final product identity

**DHRUVA — Polar Mission Intelligence & Energy Management System**

### Core product promise

> Turn uncertain polar station conditions into explainable, safe and operator-supervised mission decisions.

### Final intelligence loop

**Sense → Predict → World Model → Stress → Optimize → Verify → Explain → Safety Shield → Human Approval → Audit → Learn**

DHRUVA is designed to evolve from an engineering/reference platform into a field-validated polar mission intelligence system as approved real station telemetry, hardware-in-the-loop testing and standardized external benchmarks become available.
