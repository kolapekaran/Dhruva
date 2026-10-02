import React, { useEffect, useState } from 'react';
import { Activity, Clock3, Fuel, ShieldCheck, TriangleAlert, Zap } from 'lucide-react';
import { fetchDhruvaStrategyBenchmark, fetchMissionSurvival, DhruvaStrategyBenchmark, MissionSurvivalResult } from '../integration/api';
import { useStation } from '../integration/StationContext';

export const MissionSurvivalPanel: React.FC = () => {
  const { systemMode, backendConnected } = useStation();
  const [result, setResult] = useState<MissionSurvivalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [delay, setDelay] = useState(0);
  const [resupplyPlanned, setResupplyPlanned] = useState(true);
  const [stress, setStress] = useState(false);
  const [baselineResult, setBaselineResult] = useState<MissionSurvivalResult | null>(null);
  const [selectedMetric, setSelectedMetric] = useState('MISSION');
  const [benchmark, setBenchmark] = useState<DhruvaStrategyBenchmark | null>(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [assurance, setAssurance] = useState<MissionAssuranceResult | null>(null);
  const [assuranceLoading, setAssuranceLoading] = useState(false);

  const run = async () => {
    if (systemMode !== 'ONLINE' || !backendConnected) return;
    setLoading(true);
    try {
      const next = await fetchMissionSurvival({ horizonHours: 72, ensembleMembers: 250, resupplyDelayHours: delay, resupplyQuantityLiters: resupplyPlanned ? 5000 : 0, windFactor: stress ? 0.4 : 1, solarFactor: stress ? 0.2 : 1, loadFactor: stress ? 1.3 : 1, generatorAvailable: !stress });
      setResult(next);
      if (!stress) setBaselineResult(next);
    } catch (e) {
      setResult(null);
      console.warn('Mission survival engine unavailable', e);
    } finally { setLoading(false); }
  };

  const runAssurance = async () => {
    if (systemMode !== 'ONLINE' || !backendConnected) return;
    setAssuranceLoading(true);
    try { setAssurance(await fetchMissionAssurance(168, 300)); } catch { setAssurance(null); } finally { setAssuranceLoading(false); }
  };

  const runBenchmark = async () => {
    if (systemMode !== 'ONLINE' || !backendConnected) return;
    setBenchmarkLoading(true);
    try { setBenchmark(await fetchDhruvaStrategyBenchmark(168)); } catch { setBenchmark(null); } finally { setBenchmarkLoading(false); }
  };

  useEffect(() => {
    if (systemMode !== 'ONLINE' || !backendConnected) { setResult(null); setBaselineResult(null); setBenchmark(null); return; }
    void run();
  }, [systemMode, backendConnected, delay, stress, resupplyPlanned]);

  const tone = result?.status === 'MISSION_SECURE' ? 'emerald' : result?.status === 'WATCH' ? 'amber' : 'red';
  return (
    <section className="cc-survival-card polar-interactive-card" aria-label="Polar mission survival engine" data-card-title="MISSION SURVIVAL ENGINE">
      <div className="cc-survival-header">
        <div>
          <div className="cc-section-title"><ShieldCheck className="w-4 h-4 inline mr-2" />POLAR MISSION SURVIVAL ENGINE</div>
          <div className="cc-section-subtitle">72h seeded stress ensemble · engineering decision support, not a failure probability</div>
        </div>
        <div className="cc-survival-actions"><button onClick={() => setStress(false)} disabled={loading || systemMode !== 'ONLINE' || !backendConnected}>BASELINE</button><button className={stress ? 'stress' : ''} onClick={() => setStress(true)} disabled={loading || systemMode !== 'ONLINE' || !backendConnected}>POLAR STRESS TEST</button><button className="benchmark" onClick={() => void runBenchmark()} disabled={benchmarkLoading || systemMode !== 'ONLINE' || !backendConnected}>{benchmarkLoading ? 'BENCHMARKING…' : 'BASELINE vs DHRUVA'}</button><button className="benchmark" onClick={() => void runAssurance()} disabled={assuranceLoading || systemMode !== 'ONLINE' || !backendConnected}>{assuranceLoading ? 'ASSURANCE…' : '7-DAY ASSURANCE'}</button></div>
      </div>
      <div className="cc-survival-grid">
        <button type="button" data-card-title="MISSION SECURE" aria-pressed={selectedMetric === 'MISSION'} onClick={() => setSelectedMetric('MISSION')} className={`cc-survival-status ${tone} ${selectedMetric === 'MISSION' ? 'cc-survival-selected' : ''}`}>
          <span>{result?.status?.replace('_', ' ') ?? 'READY'}</span>
          <strong>{result ? `${result.survival_percent.toFixed(0)}%` : '—'}</strong>
          <small>{systemMode === 'ONLINE' && backendConnected ? 'reference ensemble paths' : 'requires live backend'}</small>
        </button>
        <button type="button" data-card-title="P50 HORIZON" aria-pressed={selectedMetric === 'HORIZON'} onClick={() => setSelectedMetric('HORIZON')} className={`cc-survival-stat ${selectedMetric === 'HORIZON' ? 'cc-survival-selected' : ''}`}><Clock3 /><span>P50 HORIZON</span><b>{result ? `${result.survival_horizon_hours.p50}h` : '—'}</b></button>
        <button type="button" data-card-title="LIMITING FACTOR" aria-pressed={selectedMetric === 'LIMITING'} onClick={() => setSelectedMetric('LIMITING')} className={`cc-survival-stat ${selectedMetric === 'LIMITING' ? 'cc-survival-selected' : ''}`}><Activity /><span>LIMITING FACTOR</span><b>{result ? result.limiting_factor : '—'}</b></button>
        <button type="button" data-card-title="MIN FUEL" aria-pressed={selectedMetric === 'FUEL'} onClick={() => setSelectedMetric('FUEL')} className={`cc-survival-stat ${selectedMetric === 'FUEL' ? 'cc-survival-selected' : ''}`}><Fuel /><span>MIN FUEL</span><b>{result ? `${result.minimum_fuel_liters.toFixed(0)} L` : '—'}</b></button>
      </div>
      <div className="cc-survival-focus">
        <span>SELECTED</span>
        <b>{selectedMetric === 'MISSION' ? 'Mission survival status' : selectedMetric === 'HORIZON' ? 'P50 survival horizon' : selectedMetric === 'LIMITING' ? 'Primary limiting factor' : 'Minimum fuel requirement'}</b>
        <small>{selectedMetric === 'MISSION' ? 'Use the stress test controls to compare the operating envelope.' : selectedMetric === 'HORIZON' ? 'Median horizon across the reference ensemble.' : selectedMetric === 'LIMITING' ? 'The current resource or constraint limiting the horizon.' : 'Lowest fuel volume required across the evaluated horizon.'}</small>
      </div>
      {stress && result && baselineResult && (
        <div className="cc-survival-delta">
          <span>STRESS IMPACT</span>
          <b>P50 {result.survival_horizon_hours.p50 - baselineResult.survival_horizon_hours.p50 >= 0 ? '+' : ''}{result.survival_horizon_hours.p50 - baselineResult.survival_horizon_hours.p50}h</b>
          <b>Survival {result.survival_percent - baselineResult.survival_percent >= 0 ? '+' : ''}{(result.survival_percent - baselineResult.survival_percent).toFixed(0)}pp</b>
          <small>vs current baseline</small>
        </div>
      )}
      {result && (
        <div className="cc-survival-delta">
          <span>THERMAL COUPLING</span>
          <b>{result.recovered_waste_heat_kwh.toFixed(1)} kWh recovered</b>
          <b>{result.thermal_unserved_energy_kwh.toFixed(1)} kWh thermal gap</b>
          <small>diesel waste-heat recovery included in the survival envelope</small>
        </div>
      )}
      {assurance && (
        <div className="cc-survival-delta">
          <span>7-DAY MISSION ASSURANCE · {assurance.scenario_count} SCENARIOS</span>
          <b>{assurance.worst_case.scenario.replaceAll('_', ' ')} · P10 {assurance.worst_case.p10_survival_hours}h</b>
          <b>{assurance.recommended_posture}</b>
          <small>300 seeded paths/scenario · field validation not established · state unchanged</small>
        </div>
      )}
      {benchmark && (
        <div className="cc-survival-delta">
          <span>REPRODUCIBLE 168H BENCHMARK</span>
          <b>DHRUVA vs diesel-only {benchmark.delta.vs_diesel_only_fuel_percent.toFixed(1)}% less fuel</b>
          <b>Unserved delta {benchmark.delta.unserved_energy_kwh.toFixed(1)} kWh</b>
          <small>Same forecast + same station state · engineering model · field validation not established</small>
        </div>
      )}
      <div className="cc-survival-bottom">
        <div><TriangleAlert className="w-4 h-4" /><span>Resupply plan</span>
          <button className={!resupplyPlanned ? 'active' : ''} onClick={() => { setResupplyPlanned(false); setStress(false); }}>NONE</button>
          {resupplyPlanned && [0,24,48,72].map(v => <button key={v} className={delay === v ? 'active' : ''} onClick={() => { setDelay(v); setStress(false); }}>{v === 0 ? 'NOW' : `+${v}H`}</button>)}
        </div>
        <p><Zap className="w-4 h-4" />{result?.recommendation ?? 'Run the engine to evaluate the station survival horizon.'}</p>
      </div>
    </section>
  );
};
