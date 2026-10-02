from __future__ import annotations
from datetime import datetime, timezone
import math
import random
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.api.twin import twin
from app.config import STATION_CONFIG

router = APIRouter(prefix='/intelligence', tags=['Mission Survival'])

class SurvivalRequest(BaseModel):
    horizon_hours: int = Field(72, ge=24, le=168)
    ensemble_members: int = Field(250, ge=50, le=1000)
    resupply_delay_hours: int = Field(0, ge=0, le=168)
    wind_factor: float = Field(1.0, ge=0.0, le=1.0)
    solar_factor: float = Field(1.0, ge=0.0, le=1.0)
    load_factor: float = Field(1.0, ge=0.7, le=1.6)
    generator_available: bool = True
    resupply_quantity_liters: float = Field(5000.0, ge=0.0, le=20000.0)


def _simulate(member: int, hours: int, state, req: SurvivalRequest):
    rng = random.Random(26061 + member * 7919)
    fuel = float(state.fuel.fuel_remaining_liters)
    fuel_capacity = float(STATION_CONFIG.fuel.tank_capacity_liters)
    soc = float(state.battery.soc_ratio)
    battery_kwh = 500.0
    critical = max(1.0, float(state.loads.critical_load_kw))
    base_load = max(critical, float(state.loads.total_load_kw)) * req.load_factor
    wind = max(0.0, float(state.generation.wind_power_kw)) * req.wind_factor
    solar = max(0.0, float(state.generation.solar_power_kw)) * req.solar_factor
    diesel_capacity = 150.0 if req.generator_available else 0.0
    reserve_soc = 0.20
    reserve_fuel = max(0.15 * fuel_capacity, 1.0)
    first_breach = None
    min_soc = soc
    min_fuel = fuel
    critical_served = True
    diesel_hours = 0
    thermal_unserved_kwh = 0.0
    recovered_heat_kwh = 0.0

    resupply_applied = req.resupply_quantity_liters <= 0
    for h in range(hours):
        # A 0-hour delay means the planned delivery is available at the start
        # of the horizon. A zero quantity explicitly means "no resupply".
        if (not resupply_applied) and h >= req.resupply_delay_hours:
            fuel = min(fuel_capacity, fuel + req.resupply_quantity_liters)
            resupply_applied = True
        weather_stress = max(0.0, rng.gauss(0.0, 0.14))
        renewable = max(0.0, (wind * rng.uniform(0.55, 1.05) + solar * rng.uniform(0.45, 1.10)) * (1.0 - min(0.35, weather_stress)))
        thermal_demand_kw = max(0.0, (20.0 - (float(state.weather.temperature_celsius) - 3.0 * rng.random())) * 0.8)
        load = max(critical, base_load * rng.uniform(0.92, 1.12) + thermal_demand_kw)
        deficit = max(0.0, load - renewable)
        diesel = min(diesel_capacity, deficit) if fuel > reserve_fuel else 0.0
        thermal_recovery_kw = min(thermal_demand_kw, diesel * 0.55 * 0.65) if diesel > 0 else 0.0
        recovered_heat_kwh += thermal_recovery_kw
        thermal_unserved_kwh += max(0.0, thermal_demand_kw - thermal_recovery_kw)
        diesel_hours += 1 if diesel > 0 else 0
        fuel_burn = diesel * 0.24  # engineering reference: ~0.24 L/kWh
        fuel = max(0.0, fuel - fuel_burn)
        battery_delta = (renewable + diesel - load) * 0.95 / battery_kwh
        soc = max(0.0, min(1.0, soc + battery_delta))
        min_soc = min(min_soc, soc)
        min_fuel = min(min_fuel, fuel)

        if deficit > diesel + max(0.0, (soc - reserve_soc) * battery_kwh):
            critical_served = False
        if first_breach is None and (soc < reserve_soc or fuel < reserve_fuel or not critical_served):
            first_breach = h + 1
            break

    return first_breach, min_soc, min_fuel, diesel_hours, critical_served, thermal_unserved_kwh, recovered_heat_kwh


@router.post('/mission-survival')
def mission_survival(req: SurvivalRequest):
    s = twin.state
    results = [_simulate(i, req.horizon_hours, s, req) for i in range(req.ensemble_members)]
    breach_hours = [r[0] for r in results if r[0] is not None]
    survival_hours = [req.horizon_hours if r[0] is None else r[0] - 1 for r in results]
    survival_sorted = sorted(survival_hours)
    p10 = survival_sorted[max(0, int(0.10 * len(survival_sorted)) - 1)]
    p50 = survival_sorted[max(0, int(0.50 * len(survival_sorted)) - 1)]
    p90 = survival_sorted[max(0, int(0.90 * len(survival_sorted)) - 1)]
    survival_pct = 100.0 * sum(1 for r in results if r[0] is None) / len(results)
    limiting = min((r[0] or req.horizon_hours + 1, i, r) for i, r in enumerate(results))
    limiting_reason = 'critical-load protection' if not limiting[2][4] else ('battery reserve' if limiting[2][1] < 0.20 else 'fuel reserve')
    hours_to_reserve = max(0, int(p50))

    if survival_pct >= 95 and p10 >= req.horizon_hours:
        status = 'MISSION_SECURE'
        action = 'Maintain current dispatch and preserve reserve margins.'
    elif survival_pct >= 70:
        status = 'WATCH'
        action = 'Protect reserve margins and shift flexible load toward renewable windows.'
    else:
        status = 'SURVIVAL_MODE'
        action = 'Start conservative dispatch, shed flexible load, and plan resupply / generator readiness.'

    return {
        'station': 'Maitri Research Station',
        'station_state_mutated': False,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'horizon_hours': req.horizon_hours,
        'ensemble_members': req.ensemble_members,
        'status': status,
        'survival_percent': round(survival_pct, 1),
        'survival_horizon_hours': {'p10': int(p10), 'p50': int(p50), 'p90': int(p90)},
        'limiting_factor': limiting_reason,
        'minimum_soc_percent': round(min(r[1] for r in results) * 100, 1),
        'minimum_fuel_liters': round(min(r[2] for r in results), 1),
        'median_diesel_runtime_hours': round(sorted(r[3] for r in results)[len(results)//2], 1),
        'thermal_unserved_energy_kwh': round(sum(r[5] for r in results) / len(results), 2),
        'recovered_waste_heat_kwh': round(sum(r[6] for r in results) / len(results), 2),
        'hierarchical_control': {
            'day_ahead': 'mission-reserve and resupply posture',
            'rolling_mpc': 'receding-horizon dispatch',
            'real_time_safety': 'deterministic safety shield before operator application',
        },
        'recommendation': action,
        'assumptions': {
            'resupply_delay_hours': req.resupply_delay_hours,
            'wind_factor': req.wind_factor,
            'solar_factor': req.solar_factor,
            'load_factor': req.load_factor,
            'generator_available': req.generator_available,
            'resupply_quantity_liters': req.resupply_quantity_liters,
        },
        'data_status': 'REFERENCE_STRESS_ENSEMBLE',
        'provenance': 'Seeded engineering stress ensemble using current Digital Twin state; not a calibrated probability of station failure.',
    }

@router.get('/strategy-benchmark')
def strategy_benchmark(hours: int = Query(168, ge=24, le=168)):
    """Reproducible baseline-vs-DHRUVA benchmark on the same engineering forecast.

    Baseline is a conservative renewable-first heuristic with fixed reserve rules;
    DHRUVA uses the existing robust rolling-MPC engine. This is a comparative
    engineering benchmark, not a field-validated performance claim.
    """
    from app.api.intelligence import _forecast
    from app.optimization.mpc_controller import run_physics_informed_mpc
    from app.config import STATION_CONFIG

    bundle = _forecast(hours)
    forecast = bundle.get('forecast', [])
    state = twin.state
    current_fuel = float(state.fuel.fuel_remaining_liters)
    fuel_cap = float(STATION_CONFIG.fuel.tank_capacity_liters)

    def diesel_liters(schedule):
        total = 0.0
        unserved = 0.0
        renewable = 0.0
        diesel_hours = 0
        for p in schedule:
            load = max(0.0, float(p.get('load_kw', p.get('predicted_total_load_kw', 0.0))))
            ren = max(0.0, float(p.get('solar_kw', 0.0))) + max(0.0, float(p.get('wind_kw', 0.0)))
            diesel = max(0.0, float(p.get('diesel_kw', 0.0)))
            renewable += min(load, ren)
            supplied = ren + diesel + max(0.0, float(p.get('battery_discharge_kw', 0.0)))
            unserved += max(0.0, load - supplied)
            if diesel > 0: diesel_hours += 1
            total += (STATION_CONFIG.diesel.fuel_intercept_lph + STATION_CONFIG.diesel.fuel_slope_l_per_kwh * diesel) if diesel > 0 else 0.0
        return total, unserved, renewable, diesel_hours

    diesel_only = []
    for p in forecast:
        load = max(float(state.loads.total_load_kw), float(p.get('load_kw', p.get('predicted_total_load_kw', 0.0))))
        diesel_only.append({'load_kw': load, 'solar_kw': 0.0, 'wind_kw': 0.0, 'diesel_kw': min(STATION_CONFIG.diesel.rated_power_kw, load), 'battery_discharge_kw': 0.0})
    do_fuel, do_unserved, do_renewable, do_diesel_hours = diesel_liters(diesel_only)

    baseline = []
    for p in forecast:
        load = max(float(state.loads.total_load_kw), float(p.get('load_kw', p.get('predicted_total_load_kw', 0.0))))
        solar = max(0.0, float(p.get('solar_kw', p.get('predicted_solar_kw', 0.0))))
        wind = max(0.0, float(p.get('wind_kw', p.get('predicted_wind_kw', 0.0))))
        ren = solar + wind
        diesel = max(0.0, min(STATION_CONFIG.diesel.rated_power_kw, load - ren))
        baseline.append({'load_kw': load, 'solar_kw': solar, 'wind_kw': wind, 'diesel_kw': diesel, 'battery_discharge_kw': 0.0})
    b_fuel, b_unserved, b_renewable, b_diesel_hours = diesel_liters(baseline)

    mpc = run_physics_informed_mpc(forecast, state, control_horizon=min(24, hours), lookahead_hours=min(24, hours), alpha=0.80)
    mpc_schedule = mpc.get('controls', [])
    # Controls are intentionally limited to the receding control horizon; benchmark
    # the comparable executed window rather than extrapolating unsupported values.
    d_fuel, d_unserved, d_renewable, d_diesel_hours = diesel_liters(mpc_schedule)
    compared_hours = len(mpc_schedule)
    if compared_hours == 0:
        compared_hours = min(24, len(forecast))

    return {
        'engine': 'DHRUVA_COMPARATIVE_BENCHMARK_V1',
        'benchmark_horizon_hours': hours,
        'compared_control_window_hours': compared_hours,
        'baseline': {
            'strategy': 'FIXED_RENEWABLE_FIRST_DIESEL_BACKUP',
            'fuel_liters': round(b_fuel, 2),
            'unserved_energy_kwh': round(b_unserved, 2),
            'renewable_served_kwh': round(b_renewable, 2),
            'diesel_runtime_hours': b_diesel_hours,
        },
        'diesel_only_baseline': {
            'strategy': 'DIESEL_ONLY',
            'fuel_liters': round(do_fuel, 2),
            'unserved_energy_kwh': round(do_unserved, 2),
            'renewable_served_kwh': round(do_renewable, 2),
            'diesel_runtime_hours': do_diesel_hours,
        },
        'dhruva': {
            'strategy': mpc.get('engine'),
            'fuel_liters': round(d_fuel, 2),
            'unserved_energy_kwh': round(d_unserved, 2),
            'renewable_served_kwh': round(d_renewable, 2),
            'diesel_runtime_hours': d_diesel_hours,
            'cvar_alpha': 0.80,
        },
        'delta': {
            'fuel_liters': round(b_fuel - d_fuel, 2),
            'fuel_percent': round(100.0 * (b_fuel - d_fuel) / max(b_fuel, 1e-9), 2),
            'unserved_energy_kwh': round(b_unserved - d_unserved, 2),
            'diesel_runtime_hours': round(b_diesel_hours - d_diesel_hours, 2),
            'vs_diesel_only_fuel_liters': round(do_fuel - d_fuel, 2),
            'vs_diesel_only_fuel_percent': round(100.0 * (do_fuel - d_fuel) / max(do_fuel, 1e-9), 2),
        },
        'current_fuel_liters': round(current_fuel, 2),
        'fuel_capacity_liters': round(fuel_cap, 2),
        'data_status': 'ENGINEERING_MODEL',
        'field_validated': False,
        'station_state_mutated': False,
        'reproducibility': 'Same forecast, same station state, same deterministic benchmark seed/path.',
        'limitations': 'This benchmark does not establish real-world savings or superiority without independently verified Maitri telemetry and held-out validation.',
    }

@router.get('/mission-assurance')
def mission_assurance(horizon_hours: int = Query(168, ge=72, le=168), ensemble_members: int = Query(300, ge=100, le=1000)):
    """Deterministic multi-scenario mission-assurance envelope.

    Evaluates the same station state across materially different polar operating
    regimes. This is engineering stress analysis, not a calibrated probability
    of failure. No live twin state is mutated.
    """
    scenarios = [
        ('BASELINE', dict(wind_factor=1.0, solar_factor=1.0, load_factor=1.0, generator_available=True, resupply_delay_hours=0)),
        ('LOW_WIND', dict(wind_factor=0.45, solar_factor=1.0, load_factor=1.0, generator_available=True, resupply_delay_hours=24)),
        ('SOLAR_LOSS', dict(wind_factor=1.0, solar_factor=0.05, load_factor=1.0, generator_available=True, resupply_delay_hours=24)),
        ('EXTREME_COLD_LOAD', dict(wind_factor=0.75, solar_factor=0.65, load_factor=1.25, generator_available=True, resupply_delay_hours=48)),
        ('BLIZZARD', dict(wind_factor=0.35, solar_factor=0.10, load_factor=1.20, generator_available=True, resupply_delay_hours=48)),
        ('GENERATOR_FAILURE', dict(wind_factor=0.70, solar_factor=0.35, load_factor=1.15, generator_available=False, resupply_delay_hours=72)),
        ('COMBINED_ASSET_STRESS', dict(wind_factor=0.30, solar_factor=0.05, load_factor=1.30, generator_available=False, resupply_delay_hours=72)),
    ]
    state = twin.state
    rows = []
    for name, kwargs in scenarios:
        req = SurvivalRequest(horizon_hours=horizon_hours, ensemble_members=ensemble_members, resupply_quantity_liters=5000.0, **kwargs)
        results = [_simulate(i, req.horizon_hours, state, req) for i in range(req.ensemble_members)]
        survival_hours = [req.horizon_hours if r[0] is None else max(0, r[0] - 1) for r in results]
        survival_hours.sort()
        p10 = survival_hours[max(0, int(0.10 * len(survival_hours)) - 1)]
        p50 = survival_hours[max(0, int(0.50 * len(survival_hours)) - 1)]
        survival_pct = 100.0 * sum(r[0] is None for r in results) / len(results)
        thermal_gap = sum(r[5] for r in results) / len(results)
        fuel_floor = min(r[2] for r in results)
        rows.append({
            'scenario': name,
            'survival_percent': round(survival_pct, 1),
            'p10_survival_hours': int(p10),
            'p50_survival_hours': int(p50),
            'minimum_fuel_liters': round(fuel_floor, 1),
            'thermal_unserved_kwh': round(thermal_gap, 2),
            'generator_available': req.generator_available,
            'resupply_delay_hours': req.resupply_delay_hours,
        })
    worst = min(rows, key=lambda r: (r['survival_percent'], r['p10_survival_hours'], -r['minimum_fuel_liters']))
    action = (
        'PREPARE SURVIVAL POSTURE' if worst['survival_percent'] < 70 else
        'RAISE RESERVE AND CONFIRM RESUPPLY' if worst['p10_survival_hours'] < horizon_hours else
        'MAINTAIN MISSION POSTURE'
    )
    return {
        'engine': 'DHRUVA_MISSION_ASSURANCE_V1',
        'station': 'Maitri Research Station',
        'horizon_hours': horizon_hours,
        'ensemble_members_per_scenario': ensemble_members,
        'scenario_count': len(rows),
        'worst_case': worst,
        'recommended_posture': action,
        'scenario_matrix': rows,
        'hierarchy': ['DAY_AHEAD_MISSION_POSTURE', 'ROLLING_PHYSICS_INFORMED_MPC', 'REAL_TIME_SAFETY_SHIELD'],
        'station_state_mutated': False,
        'data_status': 'REFERENCE_STRESS_ENSEMBLE',
        'field_validated': False,
        'provenance': 'Seeded engineering stress ensemble over the current Digital Twin state; not a calibrated probability of station failure.',
        'limitations': 'Independent Maitri telemetry, held-out field validation, calibrated probabilistic forecasts and operator-reviewed acceptance thresholds are still required for field claims.',
    }
