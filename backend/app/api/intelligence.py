from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from app.api.twin import twin
from app.database.schemas import state_to_dict
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.ml.inference.predictor import ARTIFACT_DIR
from app.optimization.optimizer import optimize_schedule, OptimizationWeights
from app.ml.evaluation.backtesting import (
    parse_observation, parse_csv_text, run_backtest, append_observations, load_stored_observations, artifact_manifest, validate_dataset,
)

router=APIRouter(prefix='/intelligence',tags=['AI Intelligence'])
telemetry_history=[]

class Telemetry(BaseModel):
    timestamp: datetime | None=None
    temperature_celsius: float=Field(-20,ge=-90,le=20)
    wind_speed_mps: float=Field(8,ge=0,le=80)
    solar_irradiance_w_m2: float=Field(0,ge=0,le=2000)
    snowfall_rate: float=Field(0,ge=0,le=100)
    load_kw: float|None=Field(None,ge=0,le=500)
    battery_soc_percent: float|None=Field(None,ge=0,le=100)
    fuel_percent: float|None=Field(None,ge=0,le=100)

@router.post('/telemetry')
def ingest_telemetry(payload:Telemetry):
    from dataclasses import replace
    from app.config import STATION_CONFIG
    ts=payload.timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None: ts=ts.replace(tzinfo=timezone.utc)
    s=twin.state
    icing=max(0.0,min(1.0,1.0-0.012*max(0.0,-payload.temperature_celsius-5.0)-0.03*payload.snowfall_rate))
    solar_derate=max(0.0,min(1.0,1.0-0.025*payload.snowfall_rate))
    s.time=replace(s.time,timestamp=ts)
    s.weather=replace(s.weather,temperature_celsius=payload.temperature_celsius,wind_speed_mps=payload.wind_speed_mps,solar_irradiance_w_m2=payload.solar_irradiance_w_m2,snowfall_rate=payload.snowfall_rate,icing_factor=icing)
    if payload.battery_soc_percent is not None: s.battery=replace(s.battery,soc_ratio=payload.battery_soc_percent/100.0)
    if payload.fuel_percent is not None: s.fuel=replace(s.fuel,fuel_remaining_liters=payload.fuel_percent/100.0*STATION_CONFIG.fuel.tank_capacity_liters)
    if payload.load_kw is not None:
        s.loads=replace(s.loads,requested_load_kw=payload.load_kw,total_load_kw=payload.load_kw,served_load_kw=min(payload.load_kw,s.loads.served_load_kw if s.loads.served_load_kw>0 else payload.load_kw))
    item={'received_at':datetime.now(timezone.utc).isoformat(),'timestamp':ts.isoformat(),'quality':'accepted','state':state_to_dict(s),'source':'external_telemetry'}
    telemetry_history.append(item)
    if len(telemetry_history)>5000: del telemetry_history[:-5000]
    return {'status':'accepted','telemetry':item,'solar_derate_factor':solar_derate}

@router.get('/telemetry/history')
def telemetry_history_get(limit:int=Query(100,ge=1,le=5000)): return telemetry_history[-limit:]


class HistoricalBacktestRequest(BaseModel):
    observations: list[dict[str, Any]] = Field(default_factory=list)
    calibration_fraction: float = Field(0.60, ge=0.20, le=0.80)
    persist: bool = False


@router.post('/historical/ingest')
def ingest_historical(payload: HistoricalBacktestRequest):
    if not payload.observations:
        raise HTTPException(status_code=400, detail='observations must not be empty')
    try:
        rows = [parse_observation(r) for r in payload.observations]
        quality = __import__('app.ml.evaluation.backtesting', fromlist=['validate_dataset']).validate_dataset(rows)
        if quality['duplicate_timestamps']:
            raise ValueError('duplicate timestamps are not allowed')
        if not quality['chronological']:
            raise ValueError('timestamps must be chronological for ingestion')
        stored = append_observations(rows) if payload.persist else {'stored_count': 0, 'storage': 'request_only'}
        return {'status': 'accepted', 'dataset': quality, 'storage': stored, 'field_validated': False}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post('/historical/backtest')
def historical_backtest(payload: HistoricalBacktestRequest):
    if not payload.observations:
        raise HTTPException(status_code=400, detail='observations must not be empty')
    try:
        rows = [parse_observation(r) for r in payload.observations]
        return run_backtest(rows, payload.calibration_fraction)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post('/historical/backtest-csv')
def historical_backtest_csv(csv_text: str = Body(..., media_type='text/plain'), calibration_fraction: float = Query(0.60, ge=0.20, le=0.80)):
    try:
        rows = parse_csv_text(csv_text)
        return run_backtest(rows, calibration_fraction)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get('/historical/backtest-stored')
def historical_backtest_stored(limit: int = Query(5000, ge=4, le=5000), calibration_fraction: float = Query(0.60, ge=0.20, le=0.80)):
    rows = load_stored_observations(limit)
    if not rows:
        return {'status': 'NO_DATA', 'dataset': {'sample_count': 0}, 'field_validated': False}
    try:
        return run_backtest(rows, calibration_fraction)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get('/historical/readiness')
def historical_readiness(limit: int = Query(5000, ge=4, le=5000)):
    """Return a single reproducibility/readiness snapshot for the historical ML pipeline."""
    stored = load_stored_observations(limit)
    dataset = validate_dataset(stored) if stored else {
        'sample_count': 0,
        'duplicate_timestamps': 0,
        'chronological': True,
        'target_observations': {k: 0 for k in ('load_kw', 'solar_kw', 'wind_kw')},
        'target_completeness_percent': {k: 0.0 for k in ('load_kw', 'solar_kw', 'wind_kw')},
        'required_field_completeness_percent': 0.0,
        'provenance_counts': {p: 0 for p in sorted({'FIELD_TELEMETRY', 'REFERENCE', 'SYNTHETIC', 'SIMULATION'})},
        'quality_status': 'NO_DATA',
    }
    return {
        'engine': 'DHRUVA_HISTORICAL_READINESS_V1',
        'dataset': dataset,
        'artifact_manifest': artifact_manifest(),
        'field_validation_eligible': bool(stored) and all(r.provenance == 'FIELD_TELEMETRY' for r in stored),
        'field_validation_status': 'NOT_ESTABLISHED',
        'required_protocol': [
            'independently verified Maitri telemetry',
            'time-aligned held-out evaluation window',
            'documented sensor/data-quality acceptance criteria',
            'pre-registered metrics and calibration target',
            'operator/engineering review before operational claims',
        ],
        'station_state_mutated': False,
    }


@router.get('/historical/schema')
def historical_schema():
    return {
        'engine': 'DHRUVA_HISTORICAL_BACKTEST_V1',
        'required_columns': ['timestamp', 'temperature_celsius', 'wind_speed_mps'],
        'optional_columns': ['solar_irradiance_w_m2', 'snowfall_rate', 'load_kw', 'solar_kw', 'wind_kw', 'provenance'],
        'provenance_values': ['FIELD_TELEMETRY', 'REFERENCE', 'SYNTHETIC', 'SIMULATION'],
        'timestamp': 'ISO-8601',
        'field_validation_rule': 'Only independently verified FIELD_TELEMETRY records can be marked field-valid; the engine never upgrades provenance.',
        'storage': 'local JSONL prototype; production deployment should use the configured database/object store.',
    }

def _forecast(hours:int):
    s=twin.state
    return generate_multi_day_forecast(s.time.timestamp,hours,s.weather.temperature_celsius,s.weather.wind_speed_mps)

@router.get('/forecast')
def intelligence_forecast(hours:int=Query(24,ge=1,le=168)): return _forecast(hours)
@router.get('/weather')
def weather():
    s=twin.state
    polar_night = s.time.timestamp.month in (5, 6, 7, 8)
    return {'timestamp':s.time.timestamp.isoformat(),'temperature_celsius':s.weather.temperature_celsius,'wind_speed_mps':s.weather.wind_speed_mps,'solar_irradiance_w_m2':s.weather.solar_irradiance_w_m2,'snowfall_rate':s.weather.snowfall_rate,'wind_icing_factor':s.weather.icing_factor,'polar_night':polar_night,'source':'digital_twin_reference','data_status':'REFERENCE','uncertainty':'confidence comes from forecast ensemble intervals'}

@router.get('/weather/live')
def live_weather(hours:int=Query(72,ge=1,le=168)):
    """Fetch current + forecast weather for Maitri from Open-Meteo.

    The result is external weather data only; it does not silently overwrite the
    authoritative Digital Twin. The operator/twin ingestion path can explicitly
    ingest selected observations through POST /intelligence/telemetry.
    """
    import httpx
    from datetime import datetime, timezone
    latitude=-70.766111
    longitude=11.732222
    url='https://api.open-meteo.com/v1/forecast'
    params={
        'latitude':latitude,'longitude':longitude,
        'current':'temperature_2m,wind_speed_10m,wind_direction_10m,precipitation,snowfall,cloud_cover,surface_pressure',
        'hourly':'temperature_2m,wind_speed_10m,wind_direction_10m,shortwave_radiation,cloud_cover,precipitation,snowfall',
        'forecast_days':7,'timezone':'UTC'
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            r=client.get(url,params=params); r.raise_for_status(); data=r.json()
        c=data.get('current',{})
        h=data.get('hourly',{})
        rows=[]
        times=h.get('time',[])[:hours]
        keys=['temperature_2m','wind_speed_10m','wind_direction_10m','shortwave_radiation','cloud_cover','precipitation','snowfall']
        for i,t in enumerate(times):
            row={'timestamp':t}
            for k in keys: row[k]=h.get(k,[None]*len(times))[i]
            rows.append(row)
        return {'station':'Maitri Research Station','coordinates':{'latitude':latitude,'longitude':longitude},'source':'Open-Meteo','data_status':'LIVE_API','retrieved_at':datetime.now(timezone.utc).isoformat(),'current':c,'forecast':rows}
    except Exception as exc:
        raise HTTPException(status_code=503,detail={'message':'Live weather API unavailable','source':'Open-Meteo','data_status':'OFFLINE','error':str(exc)})

@router.get('/assets')
def assets():
    s=twin.state
    from app.ml.inference.predictor import asset_failure_probabilities
    probs=asset_failure_probabilities(s.weather.temperature_celsius,s.weather.wind_speed_mps,s.weather.solar_irradiance_w_m2,s.loads.requested_load_kw,s.battery.soc_ratio*100,100*s.fuel.fuel_remaining_liters/__import__('app.config',fromlist=['STATION_CONFIG']).STATION_CONFIG.fuel.tank_capacity_liters,s.battery.state_of_health_percent,s.system.diesel_runtime_seconds/3600)
    generator = {'running':s.system.diesel_running,'health_percent':s.generation.generator_health_percent,'runtime_hours':s.system.diesel_runtime_seconds/3600,'start_count':s.generation.generator_start_count}
    battery = {'soc_percent':s.battery.soc_ratio*100,'soh_percent':s.battery.state_of_health_percent,'cycle_count':s.battery.cycle_count,'temperature_celsius':s.battery.battery_temperature_celsius}
    fleet = [
        {'id':'DG1','type':'diesel_generator','role':'primary','status':'RUNNING' if s.system.diesel_running else 'STANDBY','health_percent':generator['health_percent'],'runtime_hours':generator['runtime_hours']},
        {'id':'DG2','type':'diesel_generator','role':'N+1 standby','status':'STANDBY','health_percent':generator['health_percent'],'runtime_hours':generator['runtime_hours']},
        {'id':'DG3','type':'diesel_generator','role':'reserve','status':'RESERVE','health_percent':generator['health_percent'],'runtime_hours':generator['runtime_hours']},
        {'id':'WT1','type':'wind_turbine','role':'renewable','status':'ONLINE','power_kw':s.generation.wind_power_kw},
        {'id':'PV1','type':'solar_array','role':'renewable','status':'ONLINE' if s.generation.solar_power_kw>0 else 'IDLE','power_kw':s.generation.solar_power_kw},
        {'id':'BAT1','type':'battery','role':'storage','status':'ONLINE','soc_percent':battery['soc_percent'],'soh_percent':battery['soh_percent']},
        {'id':'HR1','type':'heat_recovery','role':'thermal recovery','status':'MODELLED','data_status':'ENGINEERING_MODEL'},
    ]
    return {'battery':battery,'generator':generator,'fleet':fleet,'failure_probability':probs,'models':{'battery_failure':(ARTIFACT_DIR/'battery_failure_model.pkl').exists(),'generator_failure':(ARTIFACT_DIR/'generator_failure_model.pkl').exists()}}
@router.get('/loads')
def loads():
    s=twin.state; total=max(1e-9,s.loads.requested_load_kw)
    return {'classification':{'critical_kw':s.loads.critical_load_kw,'important_kw':s.loads.important_load_kw,'flexible_kw':s.loads.flexible_load_kw,'heating_kw':s.loads.heating_load_kw},'criticality_score':100*s.loads.critical_load_kw/total,'flexible_shift_potential_kw':s.loads.flexible_load_kw,'shedding':{'automatic':True,'current_shed_kw':s.loads.shed_load_kw,'critical_protected':s.loads.served_load_kw>=s.loads.critical_load_kw-1e-6}}
@router.get('/flexible-load-optimization')
def flexible_load_optimization(hours: int = Query(24, ge=6, le=72)):
    """Return backend-authoritative windows where flexible demand can be shifted toward renewable availability.

    This is an advisory calculation only: it does not mutate station state. Critical and important
    loads are never included in the shiftable quantity. Forecast values are reference/ML outputs,
    so the response explicitly carries provenance rather than presenting them as live telemetry.
    """
    s = twin.state
    flex_kw = max(0.0, float(s.loads.flexible_load_kw))
    non_flexible_kw = max(0.0, float(s.loads.critical_load_kw + s.loads.important_load_kw + s.loads.heating_load_kw))
    bundle = _forecast(hours)
    forecast = bundle['forecast']
    optimized = optimize_schedule(forecast, s)
    schedule_by_offset = {int(r.get('hour_offset', i)): r for i, r in enumerate(optimized.get('schedule', []))}

    candidates = []
    for i, row in enumerate(forecast):
        offset = int(row.get('hour_offset', i))
        load_kw = max(0.0, float(row.get('load_kw', 0.0)))
        renewable_kw = max(0.0, float(row.get('solar_kw', 0.0)) + float(row.get('wind_kw', 0.0)))
        # Only renewable power above non-flexible demand can safely absorb shifted flexible load.
        renewable_headroom_kw = max(0.0, renewable_kw - non_flexible_kw)
        shiftable_kw = min(flex_kw, renewable_headroom_kw)
        opt = schedule_by_offset.get(offset, {})
        diesel_kw = max(0.0, float(opt.get('diesel_kw', row.get('diesel_kw', 0.0))))
        score = shiftable_kw * 10.0 + renewable_headroom_kw + max(0.0, diesel_kw) * 0.5
        candidates.append({
            'hour_offset': offset,
            'timestamp': row.get('timestamp'),
            'forecast_load_kw': round(load_kw, 2),
            'renewable_available_kw': round(renewable_kw, 2),
            'renewable_headroom_kw': round(renewable_headroom_kw, 2),
            'recommended_shift_kw': round(shiftable_kw, 2),
            'predicted_diesel_kw': round(diesel_kw, 2),
            'confidence_percent': round(float(row.get('confidence', 0.0)) * 100.0, 1),
            'score': round(score, 3),
        })

    ranked = sorted(candidates, key=lambda x: (-x['recommended_shift_kw'], -x['renewable_headroom_kw'], x['hour_offset']))
    selected = ranked[0] if ranked else None
    recommended_shift = float(selected['recommended_shift_kw']) if selected else 0.0
    has_opportunity = recommended_shift > 0.05
    if has_opportunity:
        action = 'SHIFT_FLEXIBLE_LOAD'
        title = 'Shift flexible demand into renewable window'
        description = f"Up to {recommended_shift:.1f} kW of flexible demand can be aligned with forecast renewable headroom at +{selected['hour_offset']}h."
    else:
        action = 'HOLD'
        title = 'Hold flexible load'
        description = 'No meaningful renewable headroom is available for flexible-load shifting in the selected horizon.'

    return {
        'station': s.station_name if hasattr(s, 'station_name') else 'Maitri Research Station',
        'horizon_hours': hours,
        'flexible_load_available_kw': round(flex_kw, 2),
        'protected_load_kw': round(non_flexible_kw, 2),
        'recommended_action': action,
        'recommendation': {
            'title': title,
            'description': description,
            'recommended_shift_kw': round(recommended_shift, 2),
            'target_hour_offset': selected['hour_offset'] if selected else None,
            'target_timestamp': selected['timestamp'] if selected else None,
            'expected_renewable_headroom_kw': selected['renewable_headroom_kw'] if selected else 0.0,
            'predicted_diesel_kw': selected['predicted_diesel_kw'] if selected else 0.0,
        },
        'windows': ranked[:8],
        'forecast_source': bundle.get('source', 'integrated_ai_ml_reference_weather'),
        'synthetic_weather': bool(bundle.get('synthetic_weather', True)),
        'data_status': 'ML',
        'advisory_only': True,
        'critical_load_protected': True,
        'optimizer_summary': optimized.get('summary', {}),
    }

@router.get('/fuel-logistics-intelligence')
def fuel_logistics_intelligence(
    hours: int = Query(72, ge=24, le=168),
    resupply_lead_time_hours: int = Query(72, ge=1, le=336),
):
    """Backend-authoritative fuel inventory and resupply advisory.

    Uses the existing Digital Twin projection; it does not mutate station state.
    Values are explicitly labelled as engineering-model/projection outputs.
    """
    from app.config import STATION_CONFIG
    from app.services.projection_service import forecast_projection

    result = forecast_projection(hours)
    metrics = result['metrics']
    points = result['points']
    tank = float(STATION_CONFIG.fuel.tank_capacity_liters)
    reserve = float(STATION_CONFIG.fuel.emergency_reserve_liters)
    current = float(metrics['initial_fuel_liters'])

    lead_point = min(points, key=lambda p: abs(int(p.get('hour_offset', 0)) - resupply_lead_time_hours)) if points else None
    lead_fuel = float(lead_point.get('fuel_remaining_liters', current)) if lead_point else current
    fuel_burn = max(0.0, current - float(metrics['final_fuel_liters']))
    avg_burn_lph = fuel_burn / max(1.0, float(hours))
    autonomy_hours = (current / avg_burn_lph) if avg_burn_lph > 1e-9 else None
    reserve_hours = ((current - reserve) / avg_burn_lph) if avg_burn_lph > 1e-9 else None

    # Projected stock required at the end of the lead-time window while preserving
    # the configured emergency reserve. This is an advisory planning quantity only.
    lead_burn = max(0.0, current - lead_fuel)
    safety_target = min(tank, reserve + lead_burn * 1.10)
    projected_below_reserve = lead_fuel <= reserve
    reserve_breach_within_horizon = bool(metrics.get('fuel_reserve_reached', False))
    resupply_needed_now = projected_below_reserve or reserve_breach_within_horizon
    recommended_quantity = max(0.0, safety_target - lead_fuel) if resupply_needed_now else max(0.0, safety_target - current)

    if projected_below_reserve:
        risk_level = 'HIGH'
        action = 'RESUPPLY_REQUIRED'
        title = 'Fuel reserve is projected to breach before resupply lead time'
    elif reserve_breach_within_horizon:
        risk_level = 'MEDIUM'
        action = 'PLAN_RESUPPLY'
        title = 'Fuel reserve breach is projected within the planning horizon'
    else:
        risk_level = 'LOW'
        action = 'NO_IMMEDIATE_RESUPPLY'
        title = 'Fuel inventory remains above the configured reserve'

    return {
        'station': getattr(twin.state, 'station_name', 'Maitri Research Station'),
        'horizon_hours': hours,
        'resupply_lead_time_hours': resupply_lead_time_hours,
        'current_fuel_liters': round(current, 2),
        'tank_capacity_liters': round(tank, 2),
        'emergency_reserve_liters': round(reserve, 2),
        'current_fill_percent': round(100.0 * current / max(1e-9, tank), 1),
        'average_burn_lph': round(avg_burn_lph, 3),
        'projected_fuel_liters': round(float(metrics['final_fuel_liters']), 2),
        'fuel_consumed_liters': round(fuel_burn, 2),
        'estimated_autonomy_hours': round(autonomy_hours, 1) if autonomy_hours is not None else None,
        'estimated_hours_to_reserve': round(max(0.0, reserve_hours), 1) if reserve_hours is not None else None,
        'lead_time_projected_fuel_liters': round(lead_fuel, 2),
        'reserve_breach_within_horizon': reserve_breach_within_horizon,
        'reserve_breach_at_lead_time': projected_below_reserve,
        'resupply_needed_now': resupply_needed_now,
        'recommended_resupply_quantity_liters': round(recommended_quantity, 2),
        'recommended_action': action,
        'recommendation': {
            'title': title,
            'risk_level': risk_level,
            'description': f"Projected fuel at the {resupply_lead_time_hours}h lead-time point is {lead_fuel:.0f} L versus a {reserve:.0f} L emergency reserve.",
            'target_stock_liters': round(safety_target, 2),
        },
        'series': [
            {
                'hour_offset': int(p.get('hour_offset', 0)),
                'timestamp': p.get('timestamp'),
                'fuel_remaining_liters': round(float(p.get('fuel_remaining_liters', 0.0)), 2),
                'diesel_power_kw': round(float(p.get('diesel_power_kw', 0.0)), 2),
                'data_status': p.get('data_status', 'ENGINEERING_MODEL'),
            } for p in points
        ],
        'forecast_source': result.get('source', 'forecast_driven_digital_twin'),
        'data_status': 'ENGINEERING_MODEL',
        'advisory_only': True,
        'station_state_mutated': False,
        'provenance': 'Digital Twin fuel projection + configured emergency reserve',
        'note': 'Resupply quantities are planning advisories, not live logistics bookings or confirmed deliveries.',
    }

@router.get('/heat-recovery-intelligence')
def heat_recovery_intelligence(hours: int = Query(24, ge=6, le=72)):
    """Return heat-recovery intelligence from the existing backend forecast/thermal model.

    The route intentionally evaluates the forecast once and derives all requested
    horizon points from that shared result. This avoids repeatedly invoking the
    full Digital Twin snapshot/optimization pipeline when the Energy tab loads,
    which keeps the advisory responsive under concurrent frontend requests.
    No station state is mutated.
    """
    from app.config import STATION_CONFIG
    from app.models.heating import HeatingModelInputs, calculate_heating

    forecast = _forecast(hours)
    forecast_points = forecast.get('forecast', []) if isinstance(forecast, dict) else []
    by_offset = {int(p.get('hour_offset', 0)): p for p in forecast_points}
    offsets = [o for o in (0, 6, 12, 24, 48, 72) if o <= hours]
    points = []
    for offset in offsets:
        point = by_offset.get(offset)
        if point is None:
            # Preserve a valid response even if a forecast provider returns a
            # shorter series; use the nearest available forecast point.
            candidates = [p for p in forecast_points if int(p.get('hour_offset', 0)) <= offset]
            point = candidates[-1] if candidates else (forecast_points[0] if forecast_points else {})
        outdoor = float(point.get('temperature_celsius', twin.state.weather.temperature_celsius))
        diesel_kw = max(0.0, float(point.get('diesel_power_kw', 0.0)))
        thermal_model = calculate_heating(HeatingModelInputs(
            outdoor_temperature_celsius=outdoor,
            indoor_temperature_celsius=20.0,
            heating_electrical_power_kw=0.0,
            timestep_seconds=3600,
        ), STATION_CONFIG.heating)
        heating_demand = max(0.0, float(thermal_model.required_heating_power_kw))
        waste_heat_available = (diesel_kw / 0.38) * 0.55 if diesel_kw > 0 else 0.0
        recovered_heat = min(heating_demand, waste_heat_available * 0.65)
        electrical_heating_after = max(0.0, heating_demand - recovered_heat)
        thermal_offset = 100.0 * recovered_heat / heating_demand if heating_demand > 1e-9 else 0.0
        fuel_equivalent_lph = STATION_CONFIG.diesel.fuel_slope_l_per_kwh * recovered_heat
        confidence = float(point.get('confidence', 0.0))
        confidence = confidence * 100.0 if confidence <= 1.0 else confidence
        points.append({
            'hour_offset': offset,
            'timestamp': point.get('timestamp', twin.state.time.timestamp.isoformat()),
            'outdoor_temperature_c': round(outdoor, 2),
            'heating_demand_kwth': round(heating_demand, 2),
            'diesel_output_kw': round(diesel_kw, 2),
            'waste_heat_available_kwth': round(waste_heat_available, 2),
            'recovered_heat_kwth': round(recovered_heat, 2),
            'electrical_heating_before_kw': round(heating_demand, 2),
            'electrical_heating_after_kw': round(electrical_heating_after, 2),
            'avoided_electrical_heating_kw': round(recovered_heat, 2),
            'thermal_offset_percent': round(thermal_offset, 1),
            'fuel_equivalent_lph': round(fuel_equivalent_lph, 3),
            'confidence_percent': round(confidence, 1),
            'data_status': 'ENGINEERING_MODEL',
        })

    current = points[0] if points else None
    peak = max(points, key=lambda x: x['recovered_heat_kwth']) if points else None
    total_offset_kwhth = 0.0
    total_fuel_equivalent = 0.0
    for left, right in zip(points, points[1:]):
        delta_h = max(0.0, float(right['hour_offset']) - float(left['hour_offset']))
        total_offset_kwhth += ((left['recovered_heat_kwth'] + right['recovered_heat_kwth']) / 2.0) * delta_h
        total_fuel_equivalent += ((left['fuel_equivalent_lph'] + right['fuel_equivalent_lph']) / 2.0) * delta_h

    return {
        'station': 'Maitri Research Station',
        'horizon_hours': hours,
        'current': current,
        'peak_recovery': peak,
        'forecast': points,
        'summary': {
            'current_heating_demand_kwth': current['heating_demand_kwth'] if current else 0.0,
            'current_recovered_heat_kwth': current['recovered_heat_kwth'] if current else 0.0,
            'current_thermal_offset_percent': current['thermal_offset_percent'] if current else 0.0,
            'forecast_recovered_heat_kwhth': round(total_offset_kwhth, 2),
            'forecast_fuel_equivalent_liters': round(total_fuel_equivalent, 2),
            'peak_recovery_kwth': peak['recovered_heat_kwth'] if peak else 0.0,
        },
        'assumptions': {
            'electrical_efficiency_ratio': 0.38,
            'waste_heat_fraction': 0.55,
            'heat_recovery_efficiency_ratio': 0.65,
            'heating_efficiency_ratio': STATION_CONFIG.heating.heating_efficiency_ratio,
            'fuel_curve_slope_l_per_kwh': STATION_CONFIG.diesel.fuel_slope_l_per_kwh,
        },
        'data_status': 'ENGINEERING_MODEL',
        'advisory_only': True,
        'station_state_mutated': False,
        'provenance': 'Shared backend forecast + Digital Twin thermal model + diesel waste-heat engineering model',
        'note': 'Fuel-equivalent values are modelled indicators, not measured fuel savings.',
    }

@router.post('/load-action')
def load_action(shift_flexible_kw: float = Query(0.0, ge=0.0, le=100.0), shed_flexible: bool = False):
    from dataclasses import replace
    s=twin.state
    original=max(0.0,s.loads.flexible_load_kw)
    shifted=min(max(0.0,shift_flexible_kw), original)
    remaining=max(0.0,original-shifted)
    shed=original if shed_flexible else 0.0
    flexible_after=max(0.0,remaining-shed)
    requested=max(0.0,s.loads.critical_load_kw+s.loads.important_load_kw+flexible_after+s.loads.heating_load_kw)
    available=max(0.0,s.system.total_generation_kw+s.system.battery_discharging_kw-s.system.battery_charging_kw)
    served=min(requested,available)
    shed_total=max(0.0,requested-served)
    twin.state=replace(s, loads=replace(s.loads, flexible_load_kw=flexible_after, requested_load_kw=requested, total_load_kw=requested, served_load_kw=served, shed_load_kw=shed_total), system=replace(s.system, power_balance_kw=s.system.total_generation_kw-requested))
    return {'action':'shed_flexible' if shed_flexible else ('shift_flexible' if shifted>0 else 'hold'),'critical_load_kw':s.loads.critical_load_kw,'important_load_kw':s.loads.important_load_kw,'original_flexible_load_kw':original,'shifted_kw':shifted,'shed_kw':shed,'projected_flexible_served_kw':flexible_after,'critical_protected':True,'state':state_to_dict(twin.state),'data_status':'ENGINEERING_MODEL'}

@router.get('/fuel')
def fuel():
    from app.config import STATION_CONFIG
    s=twin.state; rate=s.fuel.consumption_rate_lph
    reserve=STATION_CONFIG.fuel.emergency_reserve_liters
    if rate <= 0:
        autonomy = None
        days = None
        exhaustion_date = None
        resupply_date = None
        shortage_probability = 0.0
    else:
        autonomy = s.fuel.fuel_remaining_liters/rate
        days=(max(0,s.fuel.fuel_remaining_liters-reserve)/rate)/24
        exhaustion_date=(s.time.timestamp+__import__('datetime').timedelta(hours=autonomy)).isoformat()
        resupply_date=(s.time.timestamp+__import__('datetime').timedelta(hours=max(0,days*24))).isoformat()
        shortage_probability=min(100,max(0,(1-days/7)*100))
    return {'remaining_liters':s.fuel.fuel_remaining_liters,'remaining_percent':100*s.fuel.fuel_remaining_liters/STATION_CONFIG.fuel.tank_capacity_liters,'consumption_rate_lph':rate,'autonomy_hours':autonomy,'autonomy_days':None if days is None else days,'emergency_reserve_liters':reserve,'reserve_status':s.fuel.fuel_remaining_liters<=reserve,'exhaustion_date':exhaustion_date,'recommended_resupply_date':resupply_date,'shortage_probability_percent':shortage_probability}
@router.get('/optimization')
def intelligence_optimization(hours:int=Query(24,ge=1,le=168),cost_weight:float=Query(1,ge=0),emission_weight:float=Query(1,ge=0),reliability_weight:float=Query(4,ge=0),fuel_weight:float=Query(2,ge=0),renewable_weight:float=Query(2,ge=0)):
    b=_forecast(hours); w=OptimizationWeights(cost_weight,emission_weight,reliability_weight,fuel_weight,renewable_weight); return optimize_schedule(b['forecast'],twin.state,w)
@router.get('/analytics')
def analytics(hours:int=Query(24,ge=1,le=168)):
    f=_forecast(hours)['forecast']; return {'horizon_hours':hours,'load':{'mean_kw':sum(x['load_kw'] for x in f)/len(f),'peak_kw':max(x['load_kw'] for x in f)},'renewables':{'mean_kw':sum(x['renewable_kw'] for x in f)/len(f),'peak_kw':max(x['renewable_kw'] for x in f)},'risk':{'max_failure_probability':max(x['failure_probability'] for x in f),'anomaly_hours':sum(1 for x in f if x['anomaly']==-1)}}
@router.get('/seasonal-plan')
def seasonal_plan(days:int=Query(30,ge=1,le=90)):
    hours=days*24; chunks=[]; remaining=hours; start=twin.state.time.timestamp
    while remaining:
        n=min(168,remaining); bundle=generate_multi_day_forecast(start,n,twin.state.weather.temperature_celsius,twin.state.weather.wind_speed_mps); opt=optimize_schedule(bundle['forecast'],twin.state); chunks.append(opt['summary']); start=start.replace()+__import__('datetime').timedelta(hours=n); remaining-=n
    return {'days':days,'chunks':chunks,'planning_basis':'rolling_168h_reference_forecast','note':'Seasonal plan is a rolling reference plan; it is not a climatological field forecast.'}
@router.post('/coordination')
def coordination(stations:list[dict]):
    out=[]
    for st in stations:
        load=float(st.get('load_kw',0)); renewable=float(st.get('renewable_kw',0)); battery=float(st.get('battery_available_kw',0)); out.append({'station_id':st.get('station_id','unknown'),'surplus_kw':max(0,renewable+max(0,battery)-load),'deficit_kw':max(0,load-renewable-max(0,battery))})
    total=sum(x['surplus_kw'] for x in out); deficits=sum(x['deficit_kw'] for x in out)
    return {'stations':out,'transferable_surplus_kw':total,'unmet_after_local_balance_kw':max(0,deficits-total),'coordination_recommended':total>0 and deficits>0}
@router.get('/offline-mode')
def offline_mode(): return {'enabled':True,'mode':'edge_autonomous','local_models':True,'telemetry_buffering':True,'cloud_dependency':False,'note':'Control can continue from local Twin/ML state; external weather data is not required for the reference controller.'}
@router.get('/maintenance')
def maintenance():
    a=assets(); actions=[]
    if a['battery']['soh_percent']<80: actions.append('Schedule battery inspection/replacement planning')
    if a['generator']['health_percent']<80: actions.append('Schedule generator preventive maintenance')
    if a['generator']['runtime_hours']>500: actions.append('Review generator service interval')
    if not actions: actions.append('No immediate predictive-maintenance action from reference health indicators')
    return {'actions':actions,'battery_health_percent':a['battery']['soh_percent'],'generator_health_percent':a['generator']['health_percent'],'advisory':True}
@router.get('/resilience')
def resilience():
    s=twin.state; return {'n_minus_one':{'diesel_outage':s.generation.solar_power_kw+s.generation.wind_power_kw>=s.loads.critical_load_kw,'battery_outage':s.generation.solar_power_kw+s.generation.wind_power_kw+s.generation.diesel_power_kw>=s.loads.critical_load_kw},'black_start_ready':s.fuel.fuel_remaining_liters>0 and s.battery.soc_ratio>=0.25,'critical_load_kw':s.loads.critical_load_kw,'communication_loss_safe':True}


@router.get('/snapshot')
def snapshot_alias(hourOffset:int=Query(0, ge=0, le=72)):
    from app.api.integration_adapter import _snapshot
    return _snapshot(hourOffset)

@router.get('/model-status')
def model_status():
    from app.api.health import detailed_health
    return detailed_health()

@router.get('/coordination')
def coordination_status():
    s=twin.state
    return {'station_count':1,'station':'Maitri Research Station','coordination_required':False,'local_balance_kw':round(float(s.generation.solar_power_kw+s.generation.wind_power_kw+s.generation.diesel_power_kw+s.battery.battery_power_kw-s.loads.requested_load_kw),2),'mode':'single_station'}


@router.get('/operational-intelligence')
def operational_intelligence(hours: int = Query(24, ge=6, le=72)):
    """Unified read-only operator intelligence bundle.

    Aggregates existing backend authorities for decision audit, performance,
    alerts/events and provenance. It does not create a second optimizer.
    """
    from app.api.alerts import alerts as alerts_endpoint
    from app.api.risk import risk as risk_endpoint
    from app.api.optimization import optimization as optimization_endpoint
    from app.api.analytics import history_analytics
    from app.config import STATION_CONFIG

    opt = optimization_endpoint(hours)
    risk = risk_endpoint(hours)
    alert_bundle = alerts_endpoint(hours)
    history_bundle = history_analytics(min(1440, max(24, hours * 12)))
    s = twin.state
    schedule = opt.get('optimization', {}).get('schedule', [])

    # The operational-intelligence panel is projection-oriented. When the
    # historical buffer is empty (common immediately after startup), do not
    # turn missing history into misleading 0.0 values. Derive the same
    # performance fields from the authoritative optimization schedule.
    performance = history_bundle.get('summary', {})
    if not performance:
        loads = [float(row.get('load_kw', 0.0)) for row in schedule]
        renewables = [float(row.get('renewable_kw', 0.0)) for row in schedule]
        fuel_remaining = [float(row.get('fuel_remaining_liters', 0.0)) for row in schedule if row.get('fuel_remaining_liters') is not None]
        shed = [float(row.get('load_shed_kw', 0.0)) for row in schedule]
        performance = {
            'average_load_kw': sum(loads) / len(loads) if loads else None,
            'average_renewable_power_kw': sum(renewables) / len(renewables) if renewables else None,
            'fuel_consumed_liters': max(0.0, fuel_remaining[0] - fuel_remaining[-1]) if len(fuel_remaining) >= 2 else None,
            'load_shed_steps': sum(value > 1e-6 for value in shed),
            'source': 'BACKEND_OPTIMIZATION_PROJECTION',
        }

    rec = opt.get('recommended', {})
    impact = opt.get('impact', {})
    weights = opt.get('optimization', {}).get('weights', {})
    first = schedule[0] if schedule else {}
    reason_points = [
        f"Renewable contribution in recommended horizon: {float(rec.get('renewable_share_percent', 0)):.1f}%.",
        f"Projected fuel saving versus diesel-only baseline: {float(impact.get('fuel_saved_liters', 0)):.1f} L.",
        f"Minimum projected battery SOC: {float(rec.get('minimum_soc_percent', 0)):.1f}%.",
        f"Critical-load service remains represented by the backend optimization outcome: {100.0 - float(rec.get('load_shed_energy_kwh', 0)):.1f}% energy not shed in the advisory horizon." if float(rec.get('load_shed_energy_kwh', 0)) == 0 else f"Projected load shedding: {float(rec.get('load_shed_energy_kwh', 0)):.1f} kWh.",
    ]
    provenance = [
        {'domain':'Digital Twin state','status':'REFERENCE','source':'authoritative station twin'},
        {'domain':'Optimization','status':'ADVISORY','source':opt.get('optimizer_engine','backend optimizer')},
        {'domain':'Risk','status':'ADVISORY','source':'backend resilience/risk model'},
        {'domain':'Forecast','status':'ML','source':'backend forecast bundle'},
        {'domain':'Fuel projection','status':'ENGINEERING MODEL','source':'digital twin projection'},
    ]
    timeline = []
    for row in schedule[:24]:
        timeline.append({
            'timestamp': row.get('timestamp'),
            'hour_offset': row.get('hour_offset'),
            'event':'OPTIMIZATION_ADVISORY',
            'strategy': rec.get('strategy'),
            'diesel_kw': row.get('diesel_kw'),
            'renewable_kw': row.get('renewable_kw'),
            'battery_soc_percent': row.get('soc_percent'),
            'load_shed_kw': row.get('load_shed_kw'),
            'confidence': row.get('confidence'),
        })
    current_alerts = alert_bundle.get('current', [])
    projected_alerts = alert_bundle.get('projected', [])
    alerts_out = [
        {**a, 'state':'ACTIVE', 'acknowledgement':'UNACKNOWLEDGED'} for a in current_alerts
    ] + [
        {**a, 'state':'PROJECTED', 'acknowledgement':'NOT_APPLICABLE'} for a in projected_alerts
    ]
    return {
        'timestamp': s.time.timestamp.isoformat(),
        'station': getattr(s, 'station_name', 'Maitri Research Station'),
        'decision_audit': {
            'strategy': rec.get('strategy'),
            'engine': opt.get('optimizer_engine'),
            'optimality_claim': opt.get('optimality_claim', False),
            'horizon_hours': hours,
            'why_selected': reason_points,
            'constraints': {'critical_load_protected': True, 'load_shed_energy_kwh': rec.get('load_shed_energy_kwh', 0), 'minimum_soc_percent': rec.get('minimum_soc_percent')},
            'weights': weights,
            'first_step': first,
            'expected_impact': impact,
        },
        'performance': performance,
        'alerts': {'active': alerts_out, 'count': len(alerts_out), 'risk_level': risk.get('risk_level'), 'overall_risk_percent': risk.get('overall_risk_percent')},
        'risk': risk,
        'timeline': timeline,
        'provenance': provenance,
        'data_status':'BACKEND_AGGREGATED_ADVISORY',
        'read_only': True,
        'station_state_mutated': False,
    }

# ---------------------------------------------------------------------------
# Phase-3 operational intelligence: advisory posture, resupply planning and
# explicit human-in-the-loop action audit. These routes never mutate the Twin
# unless an existing, explicit control endpoint is separately invoked.
# ---------------------------------------------------------------------------

class OperatorActionRequest(BaseModel):
    decision_id: str = Field(..., min_length=3, max_length=120)
    action: str = Field(..., min_length=2, max_length=32)
    operator: str = Field("OPERATOR", min_length=1, max_length=80)
    notes: str = Field("", max_length=500)


@router.get('/operational-posture')
def operational_posture(hours: int = Query(24, ge=6, le=72)):
    from app.services.operator_intelligence import emergency_posture
    return emergency_posture(hours)


@router.get('/resupply-decision')
def resupply_decision(hours: int = Query(168, ge=24, le=168), lead_time_hours: int = Query(72, ge=1, le=336)):
    from app.services.operator_intelligence import resupply_decision as build_resupply_decision
    return build_resupply_decision(hours, lead_time_hours)


@router.get('/maintenance-posture')
def maintenance_posture():
    from app.services.operator_intelligence import maintenance_posture as build_maintenance_posture
    return build_maintenance_posture(twin.state)


@router.post('/operator-action')
def operator_action(payload: OperatorActionRequest):
    from app.services.operator_intelligence import record_operator_action
    try:
        return record_operator_action(payload.decision_id, payload.action, payload.operator, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get('/operator-action-log')
def operator_action_log(limit: int = Query(50, ge=1, le=500)):
    from app.services.operator_intelligence import operator_action_log as get_operator_action_log
    return {'actions': get_operator_action_log(limit), 'data_status': 'OPERATOR_AUDIT'}

# ---------------------------------------------------------------------------
# DHRUVA Intelligence V3 — deeper ML/backend evidence
# ---------------------------------------------------------------------------
from app.ems.intelligence_engine import asset_health_context
from app.ems.intelligence_v3 import (
    polar_regime, empirical_prediction_intervals, battery_rul,
    model_drift_check, generate_stress_scenarios, dependency_graph,
    counterfactual,
)

@router.get('/mission-intelligence')
def mission_intelligence(hours: int = Query(24, ge=6, le=72)):
    s = twin.state
    bundle = _forecast(hours)
    forecast = bundle.get('forecast', [])
    from app.ems.intelligence_engine import uncertainty_summary
    return {
        'engine': 'DHRUVA_INTELLIGENCE_ENGINE_V3',
        'horizon_hours': hours,
        'regime': polar_regime(s),
        'uncertainty': {**uncertainty_summary(forecast), 'reference_intervals': empirical_prediction_intervals(forecast)},
        'battery_rul': battery_rul(s),
        'asset_health': asset_health_context(s),
        'scenario_catalog': [{'scenario': x['scenario'], 'assumptions': x['assumptions']} for x in generate_stress_scenarios(forecast)],
        'dependency_graph': dependency_graph(s),
        'station_state_mutated': False,
        'data_status': 'ENGINEERING_MODEL',
    }

class DriftCheckPayload(BaseModel):
    actual: list[float] = Field(min_length=1, max_length=1000)
    predicted: list[float] = Field(min_length=1, max_length=1000)
    threshold_ratio: float = Field(1.5, ge=1.0, le=10.0)

@router.post('/model-drift')
def model_drift(payload: DriftCheckPayload):
    try:
        return model_drift_check(payload.actual, payload.predicted, payload.threshold_ratio)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get('/counterfactual')
def intelligence_counterfactual(scenario: str = Query('GENERATOR_FAILURE'), hours: int = Query(24, ge=6, le=72)):
    s = twin.state
    forecast = _forecast(hours).get('forecast', [])
    try:
        return counterfactual(s, forecast, scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get('/robust-optimization')
def robust_optimization(
    hours: int = Query(24, ge=6, le=72),
    alpha: float = Query(0.80, ge=0.50, le=0.99),
):
    """Evaluate DHRUVA dispatch against adverse futures using a CVaR-style tail metric.

    This endpoint is advisory and isolated: it never mutates the authoritative
    Digital Twin and does not claim global stochastic optimality.
    """
    from app.optimization.robust_optimizer import robust_scenario_evaluation
    forecast_bundle = _forecast(hours)
    forecast = forecast_bundle.get('forecast', [])
    result = robust_scenario_evaluation(forecast, twin.state, alpha=alpha)
    result['horizon_hours'] = hours
    result['forecast_source'] = forecast_bundle.get('source', 'integrated_ai_ml_reference_weather')
    result['synthetic_weather'] = bool(forecast_bundle.get('synthetic_weather', True))
    return result

@router.get('/physics-informed-mpc')
def physics_informed_mpc(
    hours: int = Query(24, ge=6, le=72),
    control_horizon_hours: int = Query(6, ge=1, le=24),
    lookahead_hours: int = Query(12, ge=3, le=24),
    alpha: float = Query(0.80, ge=0.50, le=0.99),
):
    """Run advisory rolling-horizon policy selection with physics-constrained renewables."""
    from app.optimization.mpc_controller import run_physics_informed_mpc
    bundle = _forecast(hours)
    result = run_physics_informed_mpc(
        bundle.get('forecast', []), twin.state,
        control_horizon=control_horizon_hours,
        lookahead_hours=lookahead_hours,
        alpha=alpha,
    )
    result['horizon_hours'] = hours
    result['forecast_source'] = bundle.get('source', 'integrated_ai_ml_reference_weather')
    result['synthetic_weather'] = bool(bundle.get('synthetic_weather', True))
    return result

# ---------------------------------------------------------------------------
# Phase 8 — calibration / model governance
# ---------------------------------------------------------------------------
class CalibrationRequest(BaseModel):
    calibration_actual: list[float] = Field(..., min_length=4)
    calibration_predicted: list[float] = Field(..., min_length=4)
    evaluation_actual: list[float] = Field(..., min_length=4)
    evaluation_predicted: list[float] = Field(..., min_length=4)
    alpha: float = Field(0.10, gt=0.0, lt=1.0)

class ModelComparisonRequest(BaseModel):
    actual: list[float] = Field(..., min_length=4)
    candidates: dict[str, list[float]]

@router.post('/calibration/split-conformal')
def split_conformal_calibration(payload: CalibrationRequest):
    from app.ml.evaluation.calibration import split_conformal_evaluation
    try:
        return split_conformal_evaluation(
            payload.calibration_actual,
            payload.calibration_predicted,
            payload.evaluation_actual,
            payload.evaluation_predicted,
            payload.alpha,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.post('/models/compare')
def compare_models(payload: ModelComparisonRequest):
    from app.ml.evaluation.calibration import compare_forecasters
    try:
        return compare_forecasters(payload.actual, payload.candidates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.get('/data-quality')
def intelligence_data_quality(limit: int = Query(500, ge=10, le=5000)):
    """Screen recent ingested telemetry for completeness/range/duplicate issues."""
    rows = telemetry_history[-limit:]
    timestamps = [r.get('timestamp') for r in rows]
    duplicate_timestamps = len(timestamps) - len(set(timestamps))
    required_weather = ('temperature_celsius', 'wind_speed_mps', 'solar_irradiance_w_m2', 'snowfall_rate')
    missing = 0
    range_flags = 0
    for row in rows:
        state = row.get('state', {})
        weather = state.get('weather', {}) if isinstance(state, dict) else {}
        for key in required_weather:
            if weather.get(key) is None:
                missing += 1
        try:
            if not (-90 <= float(weather.get('temperature_celsius')) <= 20): range_flags += 1
            if not (0 <= float(weather.get('wind_speed_mps')) <= 80): range_flags += 1
            if not (0 <= float(weather.get('solar_irradiance_w_m2')) <= 2000): range_flags += 1
            if not (0 <= float(weather.get('snowfall_rate')) <= 100): range_flags += 1
        except (TypeError, ValueError):
            range_flags += 1
    sample_count = len(rows)
    completeness = 100.0 if sample_count == 0 else max(0.0, 100.0 * (1 - missing / max(1, sample_count * len(required_weather))))
    quality = 'NO_DATA' if sample_count == 0 else ('DEGRADED' if (missing or range_flags or duplicate_timestamps) else 'PASS')
    return {
        'sample_count': sample_count,
        'completeness_percent': round(completeness, 2),
        'missing_field_count': missing,
        'range_violation_count': range_flags,
        'duplicate_timestamp_count': duplicate_timestamps,
        'quality': quality,
        'source': 'external_telemetry_buffer',
        'field_validated': False,
        'note': 'This is a data-quality gate for ingested observations; it does not establish sensor calibration or station-wide representativeness.',
    }
