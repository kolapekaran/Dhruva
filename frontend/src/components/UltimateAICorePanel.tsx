import React, { useState } from 'react';
import { BrainCircuit, ShieldCheck, Activity, Cpu, GitBranch, BatteryCharging, Wind, Snowflake, Network, Sparkles } from 'lucide-react';
import { fetchUltimateAICore, UltimateAICoreResult } from '../integration/api';
import { useStation } from '../integration/StationContext';

const modelLabels: Record<string,string> = {
  world_model: 'WORLD MODEL', physics_informed: 'PHYSICS-INFORMED', forecast_ensemble: 'FORECAST ENSEMBLE',
  battery_digital_twin: 'BATTERY DIGITAL TWIN', asset_rul: 'ASSET RUL', safe_rl_challenger: 'SAFE RL CHALLENGER',
  causal_engine: 'CAUSAL MISSION ENGINE', model_selector: 'MODEL SELECTOR', gnn_dependency: 'DEPENDENCY GRAPH'
};

export const UltimateAICorePanel: React.FC = () => {
  const { systemMode, backendConnected } = useStation();
  const [data, setData] = useState<UltimateAICoreResult|null>(null);
  const [loading, setLoading] = useState(false);
  const run = async () => {
    if (systemMode !== 'ONLINE' || !backendConnected) return;
    setLoading(true);
    try { setData(await fetchUltimateAICore()); } catch (e) { console.warn('Ultimate AI Core unavailable', e); }
    finally { setLoading(false); }
  };
  return <section className="cc-ai-core-card polar-interactive-card" aria-label="DHRUVA Ultimate AI Core">
    <div className="cc-ai-core-head">
      <div><div className="cc-section-title"><BrainCircuit className="w-4 h-4 inline mr-2"/>ULTIMATE AI CORE · MODEL ENSEMBLE</div><div className="cc-section-subtitle">World model · physics · ensemble forecasting · safe RL challenger · causal reasoning · asset twins</div></div>
      <button className="cc-ai-core-run" disabled={loading || systemMode !== 'ONLINE' || !backendConnected} onClick={() => void run()}>{loading ? 'RUNNING…' : data ? 'REFRESH AI CORE' : 'RUN AI CORE'}</button>
    </div>
    {!data ? <div className="cc-ai-core-empty"><Sparkles/><div><b>Integrated model stack</b><span>All models are advisory. MPC and the deterministic Safety Shield remain authoritative.</span></div></div> : <>
      <div className="cc-ai-core-risk"><div><span>MISSION REGIME</span><b>{data.mission_risk.regime.replaceAll('_',' ')}</b></div><div><span>MISSION RISK</span><b>{(data.mission_risk.score*100).toFixed(0)}%</b></div><div><span>RESERVE TARGET</span><b>{data.mission_risk.reserve_target_percent.toFixed(1)}%</b></div><div><span>FIELD VALIDATION</span><b>NOT ESTABLISHED</b></div></div>
      <div className="cc-ai-model-grid">{Object.entries(data.models).map(([key,value]: any) => {
        const icon = key.includes('battery') ? BatteryCharging : key.includes('physics') ? Wind : key.includes('rul') ? Activity : key.includes('causal') ? GitBranch : key.includes('gnn') ? Network : key.includes('world') ? BrainCircuit : Cpu;
        const Icon = icon; const status = value.status ?? 'READY';
        let detail = status;
        if (key === 'physics_informed') detail = `W ${value.wind_kw} kW · PV ${value.solar_kw} kW · TH ${value.thermal_kw} kW`;
        if (key === 'forecast_ensemble') detail = `P10 ${value.p10} · P50 ${value.p50} · P90 ${value.p90} · ${value.confidence}% conf.`;
        if (key === 'battery_digital_twin') detail = `SOC ${value.soc_percent}% · SOH ${value.soh_percent}% · usable ${value.usable_energy_kwh} kWh`;
        if (key === 'asset_rul') detail = `RUL ${value.rul_hours.toFixed(0)}h · ${value.maintenance_pressure}`;
        if (key === 'safe_rl_challenger') detail = `${value.policy} · ${value.candidate_action.replaceAll('_',' ')}`;
        if (key === 'model_selector') detail = `${value.selected_model} · promotion gated`;
        if (key === 'gnn_dependency') detail = `${value.nodes} nodes · ${value.edges} edges · graph surrogate`;
        if (key === 'causal_engine') detail = `${value.links.length} causal links active`;
        return <div className="cc-ai-model" key={key}><div className="cc-ai-model-top"><Icon/><span>{modelLabels[key] ?? key}</span><em>{status}</em></div><small>{detail}</small></div>
      })}</div>
      <div className="cc-ai-governance"><ShieldCheck/><div><b>GOVERNANCE LOCK</b><span>Human approval: {data.governance.human_approval_required ? 'REQUIRED' : 'OFF'} · Safety Shield authoritative · Automatic equipment control: NO · Automatic model promotion: NO</span></div></div>
      <div className="cc-ai-chain"><span>SENSE</span><i>→</i><span>PREDICT</span><i>→</i><span>WORLD MODEL</span><i>→</i><span>OPTIMIZE</span><i>→</i><span>SAFETY SHIELD</span><i>→</i><span>HUMAN APPROVAL</span></div>
      <div className="cc-ai-note">{data.limitations}</div>
    </>}
  </section>;
};
