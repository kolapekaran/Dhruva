"""Transparent forecast-driven multi-objective EMS optimizer.

This is a deterministic engineering heuristic rather than a global mathematical
solver. It searches feasible dispatch decisions while respecting station limits.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from app.config import STATION_CONFIG

@dataclass(frozen=True)
class OptimizationWeights:
    cost: float = 1.0
    emissions: float = 1.0
    reliability: float = 4.0
    fuel: float = 2.0
    renewable: float = 2.0

def _clamp(v,a,b): return max(a,min(b,v))

def optimize_schedule(forecast: list[dict], state, weights: OptimizationWeights | None = None, min_reserve_ratio: float | None = None, soc_min_ratio: float | None = None, soc_max_ratio: float | None = None, generator_available: bool = True) -> dict:
    weights = weights or OptimizationWeights()
    cfg=STATION_CONFIG
    configured_min_soc = cfg.battery.min_soc_ratio if soc_min_ratio is None else _clamp(float(soc_min_ratio), 0.0, 1.0)
    configured_max_soc = cfg.battery.max_soc_ratio if soc_max_ratio is None else _clamp(float(soc_max_ratio), configured_min_soc, 1.0)
    configured_reserve = configured_min_soc if min_reserve_ratio is None else _clamp(float(min_reserve_ratio), configured_min_soc, configured_max_soc)
    soc=_clamp(state.battery.soc_ratio, configured_min_soc, configured_max_soc)
    fuel=state.fuel.fuel_remaining_liters
    soh=state.battery.state_of_health_percent
    rows=[]; totals={k:0.0 for k in ('load_kwh','renewable_kwh','battery_discharge_kwh','battery_charge_kwh','diesel_kwh','shed_kwh','fuel_liters','cost','emissions_kg','battery_degradation_cost')}
    # Weight-driven dispatch preference: the optimizer must let the configured
    # objective weights influence the physical dispatch, not only the reported
    # objective value.  This keeps alternative strategies meaningfully distinct
    # while preserving the same hard load, SOC, fuel, and reserve constraints.
    weight_total = max(1.0, weights.cost + weights.emissions + weights.reliability + weights.fuel + weights.renewable)
    battery_health = float(getattr(state.battery, "state_of_health_percent", getattr(state.battery, "health_percent", 100.0)))
    generator_health = float(getattr(state.generation, "generator_health_percent", 100.0))
    asset_stress = max(0.0, (90.0 - min(battery_health, generator_health)) / 100.0)
    battery_priority = _clamp(
        0.25
        + 0.10 * (weights.fuel / weight_total)
        + 0.10 * (weights.renewable / weight_total)
        + 0.05 * (weights.emissions / weight_total)
        - 0.08 * (weights.reliability / weight_total)
        + 0.12 * max(0.0, (90.0 - generator_health) / 100.0)
        - 0.10 * max(0.0, (90.0 - battery_health) / 100.0),
        0.15,
        0.75,
    )
    reliability_reserve_boost = 0.10 * (weights.reliability / weight_total)

    for i,r in enumerate(forecast):
        load=max(0.0,float(r.get('load_kw',0.0)))
        solar=max(0.0,float(r.get('solar_kw',0.0)))
        wind=max(0.0,float(r.get('wind_kw',0.0)))
        renewable=min(load, solar+wind)
        residual=max(0.0,load-renewable)
        surplus=max(0.0,solar+wind-load)
        available_batt=max(0.0,(soc-configured_min_soc)*cfg.battery.capacity_kwh)
        # Higher fuel/renewable emphasis uses more available battery energy;
        # higher reliability emphasis retains more energy for contingencies.
        discharge=min(residual,cfg.battery.max_discharge_power_kw,available_batt) * battery_priority
        if soh<80: discharge*=max(0.6,soh/100.0)
        if generator_health < 85.0:
            # Preserve BESS headroom when a diesel asset is degraded; this is
            # an asset-aware preference, not permission to violate reserve limits.
            discharge *= min(1.25, 1.0 + (85.0 - generator_health) / 100.0)
        residual=max(0.0,residual-discharge)
        # Preserve a larger SOC reserve when forecast confidence is low, fuel is
        # low, or reliability is weighted strongly.
        conf=float(r.get('confidence',1.0))
        reserve=max(configured_reserve,
                    cfg.simulation.safe_battery_reserve_ratio + (1-conf)*0.10,
                    configured_reserve + reliability_reserve_boost)
        if soc < reserve and fuel > cfg.fuel.emergency_reserve_liters:
            discharge=0.0
            residual=max(0.0,load-renewable)
        diesel=0.0
        if residual>0 and generator_available:
            diesel=_clamp(residual,cfg.diesel.minimum_power_kw,cfg.diesel.rated_power_kw)
            if fuel <= cfg.fuel.emergency_reserve_liters and residual < cfg.diesel.rated_power_kw:
                diesel=0.0
        residual=max(0.0,residual-diesel)
        # Charge only true renewable surplus, never by diesel.
        charge=min(surplus,cfg.battery.max_charge_power_kw,(configured_max_soc-soc)*cfg.battery.capacity_kwh)
        dt_h=1.0
        soc += charge*cfg.battery.round_trip_efficiency_ratio*dt_h/cfg.battery.capacity_kwh
        soc -= discharge/cfg.battery.round_trip_efficiency_ratio*dt_h/cfg.battery.capacity_kwh
        soc=_clamp(soc,configured_min_soc,configured_max_soc)
        fuel_use=(cfg.diesel.fuel_intercept_lph*dt_h + cfg.diesel.fuel_slope_l_per_kwh*diesel*dt_h) if diesel>0 else 0.0
        fuel=max(0.0,fuel-fuel_use)
        shed=residual
        emissions=diesel*0.68*dt_h
        # Approximate battery ageing cost rises as SOH falls; this is an engineering
        # penalty, not a monetary claim or manufacturer degradation curve.
        degradation_factor = max(0.0, (100.0 - battery_health) / 20.0)
        battery_degradation_cost = discharge * (0.002 + 0.003 * degradation_factor)
        cost=fuel_use*1.0 + diesel*0.02
        totals['battery_degradation_cost'] += battery_degradation_cost
        totals['load_kwh']+=load; totals['renewable_kwh']+=solar+wind; totals['battery_discharge_kwh']+=discharge; totals['battery_charge_kwh']+=charge; totals['diesel_kwh']+=diesel; totals['shed_kwh']+=shed; totals['fuel_liters']+=fuel_use; totals['cost']+=cost; totals['emissions_kg']+=emissions
        rows.append({'timestamp':r.get('timestamp'), 'hour_offset':i,'load_kw':load,'solar_kw':solar,'wind_kw':wind,'renewable_kw':solar+wind,'battery_charge_kw':charge,'battery_discharge_kw':discharge,'diesel_kw':diesel,'load_shed_kw':shed,'soc_percent':soc*100,'fuel_remaining_liters':fuel,'renewable_first':True,'confidence':conf})
    renewable_share=totals['renewable_kwh']/max(1e-9,totals['renewable_kwh']+totals['diesel_kwh'])
    service=100.0*(1-totals['shed_kwh']/max(1e-9,totals['load_kwh']))
    asset_health_penalty = (100.0 - generator_health) * totals['diesel_kwh'] * 0.05 + (100.0 - battery_health) * totals['battery_discharge_kwh'] * 0.03
    objective=(weights.cost*totals['cost'] + weights.emissions*totals['emissions_kg'] + weights.reliability*totals['shed_kwh']*10 + weights.fuel*totals['fuel_liters'] - weights.renewable*totals['renewable_kwh'] + asset_health_penalty + totals['battery_degradation_cost'])
    return {'engine':'polar_ems_multi_objective_asset_aware_heuristic','optimality_claim':False,'weights':weights.__dict__,'horizon_hours':len(forecast),'schedule':rows,'summary':{**totals,'renewable_share_percent':renewable_share*100,'service_level_percent':service,'minimum_soc_percent':min(x['soc_percent'] for x in rows) if rows else soc*100,'final_soc_percent':soc*100,'final_fuel_liters':fuel,'objective_value':objective},'asset_awareness':{'battery_soh_percent':round(battery_health,2),'generator_health_percent':round(generator_health,2),'asset_stress_index':round(asset_stress,4),'asset_health_penalty':round(asset_health_penalty,2),'battery_degradation_cost':round(totals['battery_degradation_cost'],2)},'timescales':{'hourly':True,'daily':len(forecast)>=24,'weekly':len(forecast)>=168},'generator_available': bool(generator_available)}

def optimize_multitimescale(forecast,state,weights=None): return optimize_schedule(forecast,state,weights)
