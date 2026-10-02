from __future__ import annotations
from app.api.twin import twin
from app.ml.forecasting.multi_day import generate_multi_day_forecast
from app.optimization.optimizer import optimize_schedule, OptimizationWeights

def optimization_advisory(hours:int=24)->dict:
    if not 1<=hours<=168: raise ValueError('hours must be between 1 and 168')
    state=twin.state
    bundle=generate_multi_day_forecast(state.time.timestamp,hours,state.weather.temperature_celsius,state.weather.wind_speed_mps)
    result=optimize_schedule(bundle['forecast'],state)
    s=result['summary']
    return {'status':'advisory','optimizer_engine':result['engine'],'optimality_claim':False,'horizon_hours':hours,'baseline':{'strategy':'diesel_only','fuel_consumed_liters':5.0*hours+0.25*s['load_kwh'],'load_energy_kwh':s['load_kwh']},'recommended':{'strategy':'forecast_driven_multi_objective_ems','fuel_consumed_liters':s['fuel_liters'],'renewable_share_percent':s['renewable_share_percent'],'minimum_soc_percent':s['minimum_soc_percent'],'load_shed_energy_kwh':s['shed_kwh']},'impact':{'fuel_saved_liters':max(0.0,5.0*hours+0.25*s['load_kwh']-s['fuel_liters']),'fuel_saving_percent':max(0.0,100*(5.0*hours+0.25*s['load_kwh']-s['fuel_liters'])/max(1e-9,5.0*hours+0.25*s['load_kwh'])),'renewable_energy_kwh':s['renewable_kwh'],'diesel_energy_kwh':s['diesel_kwh'],'autonomy_days':None if s['fuel_liters']<=0 else s['final_fuel_liters']/max(1e-9,s['fuel_liters']/hours)/24},'optimization':result}
