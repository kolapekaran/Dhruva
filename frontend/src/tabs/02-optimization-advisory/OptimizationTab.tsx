import React, { useEffect, useMemo, useState } from 'react';
import {
  Battery,
  Check,
  ChevronRight,
  CircleHelp,
  Fuel,
  Leaf,
  Play,
  RotateCcw,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Wind,
  Zap,
} from 'lucide-react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { TabType } from '../../types';
import { applyStationStrategy, fetchDhruvaDecisionTrace, fetchDhruvaOperationalPosture, fetchDhruvaResupplyDecision, recordDhruvaOperatorAction } from '../../integration/api';
import { useStation } from '../../integration/StationContext';
import { DhruvaDecisionTrace } from '../../integration/types';
import type { DhruvaOperationalPosture, DhruvaResupplyDecision } from '../../integration/api';

interface OptimizationTabProps {
  onNavigateTab: (tab: TabType) => void;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export const OptimizationTab: React.FC<OptimizationTabProps> = ({ onNavigateTab }) => {
  const {
    snapshot,
    strategy,
    refreshStrategy,
    refreshSnapshot,
    appliedStrategyCode,
    setAppliedStrategyCode,
    strategyLoading,
    strategyError,
  } = useStation();

  const [fuelWeight, setFuelWeight] = useState(40);
  const [renewableWeight, setRenewableWeight] = useState(25);
  const [reliabilityWeight, setReliabilityWeight] = useState(20);
  const [emissionsWeight, setEmissionsWeight] = useState(10);
  const [costWeight, setCostWeight] = useState(5);
  const [minReserve, setMinReserve] = useState(20);
  const [horizon, setHorizon] = useState(24);
  const [recalculating, setRecalculating] = useState(false);
  const [applied, setApplied] = useState(false);
  const [showWhy, setShowWhy] = useState(true);
  const [message, setMessage] = useState('');
  const [selectedStrategyCode, setSelectedStrategyCode] = useState<'A' | 'B' | 'C' | 'D' | null>(null);
  const [decisionTrace, setDecisionTrace] = useState<DhruvaDecisionTrace | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [operationalPosture, setOperationalPosture] = useState<DhruvaOperationalPosture | null>(null);
  const [resupplyDecision, setResupplyDecision] = useState<DhruvaResupplyDecision | null>(null);
  const [operatorAction, setOperatorAction] = useState('');

  const recommended = strategy?.recommendedStrategy;
  const alternatives = strategy?.alternativeStrategies ?? [];
  const allStrategies = useMemo(() => [recommended, ...alternatives].filter(Boolean), [recommended, alternatives]);
  const selectedOption = useMemo(
    () => selectedStrategyCode ? allStrategies.find(option => option?.code === selectedStrategyCode) ?? recommended : recommended,
    [selectedStrategyCode, allStrategies, recommended],
  );
  const isPreviewingAlternative = Boolean(selectedOption && recommended && selectedOption.code !== recommended.code);
  const forecast = useMemo(
    () => (snapshot.horizonForecast ?? []).filter(point => point.hourOffset <= horizon),
    [snapshot.horizonForecast, horizon],
  );

  const chartData = useMemo(() => {
    if (selectedOption?.dispatchSchedule?.length) {
      return selectedOption.dispatchSchedule.map(point => ({
        hour: point.hourOffset === 0 ? 'Now' : `+${point.hourOffset}h`,
        load: point.loadKw,
        solar: point.solarKw,
        wind: point.windKw,
        battery: Math.max(point.batteryChargeKw, point.batteryDischargeKw),
        diesel: point.dieselKw,
      }));
    }
    return forecast.map(point => ({
      hour: point.hourOffset === 0 ? 'Now' : `+${point.hourOffset}h`,
      load: point.predictedTotalLoadKw,
      solar: point.predictedSolarKw,
      wind: point.predictedWindKw,
      battery: Math.abs(point.predictedBatteryKw),
      diesel: point.predictedDieselKw,
    }));
  }, [forecast, selectedOption]);

  const currentKpis = [
    { label: 'Current Load', value: `${snapshot.powerBalance.totalLoadKw.toFixed(0)} kW`, icon: Zap, tone: 'text-amber-300' },
    { label: 'Battery SOC', value: `${snapshot.battery.socPercent.toFixed(0)}%`, icon: Battery, tone: 'text-emerald-300' },
    { label: 'Fuel Reserve', value: `${snapshot.fuel.fillPercent.toFixed(0)}%`, icon: Fuel, tone: 'text-orange-300' },
    { label: 'Renewable Share', value: `${snapshot.powerBalance.renewableSharePercent.toFixed(0)}%`, icon: Leaf, tone: 'text-emerald-300' },
    { label: 'Station Risk', value: snapshot.reserve.status === 'ADEQUATE' ? 'LOW' : snapshot.reserve.status === 'ELEVATED_WATCH' ? 'WATCH' : 'HIGH', icon: Shield, tone: snapshot.reserve.status === 'ADEQUATE' ? 'text-emerald-300' : 'text-amber-300' },
  ];

  const loadOperationalIntelligence = async () => {
    try {
      const [posture, resupply] = await Promise.all([fetchDhruvaOperationalPosture(horizon), fetchDhruvaResupplyDecision(168, 72)]);
      setOperationalPosture(posture);
      setResupplyDecision(resupply);
    } catch {
      setOperationalPosture(null);
      setResupplyDecision(null);
    }
  };

  useEffect(() => { void loadOperationalIntelligence(); }, [horizon]);

  const acknowledgeDecision = async (action: 'ACKNOWLEDGE' | 'DEFER') => {
    if (!decisionTrace?.decision_id) return;
    try {
      await recordDhruvaOperatorAction(decisionTrace.decision_id, action);
      setOperatorAction(action === 'ACKNOWLEDGE' ? 'Decision acknowledged and audit-recorded.' : 'Decision deferred and audit-recorded.');
    } catch {
      setOperatorAction('Operator audit action failed.');
    }
  };

  const loadDecisionTrace = async () => {
    setTraceLoading(true);
    try {
      setDecisionTrace(await fetchDhruvaDecisionTrace(horizon));
      void loadOperationalIntelligence();
    } catch {
      setDecisionTrace(null);
    } finally {
      setTraceLoading(false);
    }
  };

  const runOptimization = async () => {
    setRecalculating(true);
    setMessage('Running backend decision engine…');
    try {
      const result = await refreshStrategy({
        fuelWeight,
        renewableWeight,
        reliabilityWeight,
        emissionWeight: emissionsWeight,
        costWeight,
        minReserve,
        hours: horizon,
        socMin: snapshot.battery.minSocPercent,
        socMax: snapshot.battery.maxSocPercent,
      });
      if (!result?.recommendedStrategy?.code) throw new Error('No feasible strategy returned.');
      void loadDecisionTrace();
      void loadOperationalIntelligence();
      setSelectedStrategyCode(result.recommendedStrategy.code);
      setMessage(`Optimization complete · ${result.recommendedStrategy.code} selected.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Optimization failed.');
    } finally {
      setRecalculating(false);
    }
  };

  const apply = async () => {
    if (!recommended) return;
    try {
      const optionToApply = selectedOption ?? recommended;
      await applyStationStrategy(optionToApply.code);
      setAppliedStrategyCode(optionToApply.code);
      await refreshSnapshot();
      setApplied(true);
      setMessage(`Strategy ${optionToApply.code} applied to the station operating state.`);
      window.setTimeout(() => setApplied(false), 2500);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Strategy apply failed.');
    }
  };

  const simulate = () => {
    if (!selectedOption) return;
    onNavigateTab('simulator');
  };

  const selectedImpact = selectedOption ? {
    fuel: selectedOption.projectedFuelL ?? selectedOption.projectedFuel24hL ?? 0,
    renewable: selectedOption.renewableUtilizationPercent,
    reserve: selectedOption.reserveLevelPercent,
    unserved: selectedOption.unservedLoadKw,
  } : null;

  return (
    <div className="space-y-3 text-slate-200">
      {/* Current station context */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {currentKpis.map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="polar-interactive-card rounded-xl border border-cyan-950/80 bg-[#061323]/90 px-3 py-2.5 shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
              <Icon className={`h-4 w-4 ${tone}`} />
            </div>
            <div className={`mt-1 text-lg font-black tracking-tight ${tone}`}>{value}</div>
          </div>
        ))}
      </div>

      <section className="polar-interactive-card rounded-xl border border-emerald-900/70 bg-[#04150f]/80 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2"><Shield className="h-4 w-4 text-emerald-300"/><span className="text-xs font-bold text-white">SAFETY SHIELD</span><span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[9px] font-bold text-emerald-300">ACTIVE</span></div>
          <span className="text-[10px] text-slate-400">AI recommendations are checked against station constraints before application.</span>
        </div>
        <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">Critical loads</span><div className="mt-1 font-bold text-emerald-300">PROTECTED</div></div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">Battery floor</span><div className="mt-1 font-bold text-cyan-300">{snapshot.battery.minSocPercent.toFixed(0)}%</div></div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">Reserve floor</span><div className="mt-1 font-bold text-orange-300">{minReserve}%</div></div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">Dynamic reserve</span><div className="mt-1 font-bold text-violet-300">{recommended ? `${recommended.reserveLevelPercent.toFixed(0)}%` : '—'}</div></div>
        </div>
      </section>

      <section className="polar-interactive-card rounded-xl border border-violet-900/70 bg-[#0b0718]/90 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-violet-300"/><span className="text-xs font-bold text-white">DHRUVA OPERATIONAL INTELLIGENCE</span></div>
            <p className="mt-1 text-[10px] text-slate-500">Maintenance-aware posture, fuel resupply planning and human-in-the-loop decision audit.</p>
          </div>
          <span className={`rounded-full border px-2 py-1 text-[9px] font-bold ${operationalPosture?.priority === 'CRITICAL' ? 'border-red-500/40 bg-red-500/10 text-red-300' : operationalPosture?.priority === 'WATCH' ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'}`}>{operationalPosture?.posture ?? 'LOADING'}</span>
        </div>
        <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">SAFE AUTONOMY</span><div className="mt-1 font-bold text-cyan-200">{resupplyDecision ? `${resupplyDecision.safe_autonomy_days.toFixed(1)} d` : '—'}</div></div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">RESUPPLY</span><div className="mt-1 font-bold text-orange-300">{resupplyDecision ? (resupplyDecision.recommended_quantity_liters > 0 ? `${Math.round(resupplyDecision.recommended_quantity_liters).toLocaleString()} L` : 'NOT REQUIRED') : '—'}</div></div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">ASSET POSTURE</span><div className="mt-1 font-bold text-violet-300">{operationalPosture?.maintenance?.health?.dispatch_penalty_active ? 'HEALTH-AWARE' : 'NORMAL'}</div></div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2"><span className="text-slate-500">AUDIT</span><div className="mt-1 font-bold text-emerald-300">{operatorAction || 'READY'}</div></div>
        </div>
        {operationalPosture?.reasons?.length ? <div className="mt-2 rounded-lg border border-amber-900/50 bg-amber-950/15 px-3 py-2 text-[10px] text-amber-200">{operationalPosture.reasons[0]}</div> : null}
        {decisionTrace ? <div className="mt-2 flex flex-wrap items-center gap-2"><button type="button" onClick={() => acknowledgeDecision('ACKNOWLEDGE')} className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[9px] font-bold text-emerald-300 hover:bg-emerald-500/20">ACKNOWLEDGE DECISION</button><button type="button" onClick={() => acknowledgeDecision('DEFER')} className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-[9px] font-bold text-slate-300 hover:bg-slate-900">DEFER</button><span className="text-[9px] font-mono text-slate-500">{decisionTrace.decision_id}</span></div> : null}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)_330px] gap-3">
        {/* Settings */}
        <section className="polar-interactive-card rounded-2xl border border-cyan-900/70 bg-[#04101e]/95 p-4 shadow-xl">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-bold text-white"><SlidersHorizontal className="h-4 w-4 text-cyan-300" /> Optimization Settings</div>
              <p className="mt-1 text-[10px] text-slate-500">Set objectives and operating constraints.</p>
            </div>
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[9px] font-bold text-emerald-300">BACKEND</span>
          </div>

          <div className="mt-5 space-y-3">
            {[
              ['Fuel Consumption', fuelWeight, setFuelWeight, 'text-emerald-300'],
              ['Renewable Usage', renewableWeight, setRenewableWeight, 'text-cyan-300'],
              ['Reliability', reliabilityWeight, setReliabilityWeight, 'text-amber-300'],
              ['CO₂ Emissions', emissionsWeight, setEmissionsWeight, 'text-violet-300'],
              ['Operating Cost', costWeight, setCostWeight, 'text-orange-300'],
            ].map(([label, value, setter, tone]) => (
              <label key={String(label)} className="block">
                <div className="mb-1 flex justify-between text-[10px] font-semibold">
                  <span className="text-slate-300">{label}</span><span className={String(tone)}>{value}%</span>
                </div>
                <input aria-label={String(label)} type="range" min="0" max="100" value={Number(value)} onChange={e => (setter as React.Dispatch<React.SetStateAction<number>>)(Number(e.target.value))} className="w-full accent-cyan-400" />
              </label>
            ))}
          </div>

          <div className="mt-5 border-t border-cyan-950 pt-4">
            <div className="mb-3 text-xs font-bold text-white">Constraints</div>
            <div className="space-y-3 text-xs">
              <label className="flex items-center justify-between gap-3">
                <span className="text-slate-400">Minimum battery reserve</span>
                <span className="flex items-center gap-1"><input className="w-14 rounded-md border border-cyan-900 bg-black/30 px-2 py-1 text-right text-cyan-200" type="number" min="10" max="40" value={minReserve} onChange={e => setMinReserve(clamp(Number(e.target.value), 10, 40))} /><span className="text-slate-500">%</span></span>
              </label>
              <div>
                <div className="mb-2 flex justify-between"><span className="text-slate-400">Forecast horizon</span><span className="text-cyan-300">{horizon}h</span></div>
                <div className="grid grid-cols-5 gap-1">
                  {[6, 12, 24, 48, 72].map(value => <button key={value} onClick={() => setHorizon(value)} className={`rounded-md border py-1.5 text-[10px] font-bold ${horizon === value ? 'border-cyan-400 bg-cyan-500/15 text-cyan-200' : 'border-cyan-950 bg-black/20 text-slate-500'}`}>{value}h</button>)}
                </div>
              </div>
              <div className="space-y-1.5 pt-1 text-[10px] text-slate-500">
                <div>✓ Critical loads protected</div>
                <div>✓ Battery SOC {snapshot.battery.minSocPercent.toFixed(0)}–{snapshot.battery.maxSocPercent.toFixed(0)}%</div>
                <div>✓ Fuel reserve ≥ {minReserve}%</div>
              </div>
            </div>
          </div>

          <button disabled={recalculating || strategyLoading} onClick={runOptimization} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 py-3 text-xs font-black text-slate-950 shadow-lg shadow-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50">
            <RotateCcw className={`h-4 w-4 ${recalculating ? 'animate-spin' : ''}`} /> {recalculating ? 'RUNNING OPTIMIZATION…' : 'RUN OPTIMIZATION'}
          </button>
          {message && <p className="mt-2 text-[10px] leading-relaxed text-cyan-300">{message}</p>}
        </section>

        {/* Recommendation + plan */}
        <main className="min-w-0 space-y-3">
          <section className="polar-interactive-card rounded-2xl border border-cyan-700/70 bg-gradient-to-b from-[#06192d] to-[#04101e] p-4 shadow-xl">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-emerald-300" /><span className="text-base font-black text-white">{isPreviewingAlternative ? 'Strategy Preview' : 'Recommended Strategy'}</span><span className={`rounded-full px-2 py-1 text-[9px] font-bold ${isPreviewingAlternative ? 'bg-cyan-500/10 text-cyan-300' : 'bg-emerald-500/10 text-emerald-300'}`}>{isPreviewingAlternative ? 'ALTERNATIVE SELECTED' : 'OPTIMIZATION COMPLETE'}</span></div>
              <span className="text-[10px] font-mono text-slate-500">Horizon {horizon}h · {strategyLoading ? 'Updating…' : 'Backend decision engine'}</span>
            </div>

            <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_210px] gap-4">
              <div>
                <h2 className="text-2xl font-black text-white">{selectedOption?.name ?? 'Waiting for backend strategy'}</h2>
                <p className="mt-1 text-xs leading-relaxed text-slate-400">{selectedOption?.description ?? strategyError ?? 'Run optimization to receive a station-specific strategy.'}</p>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 text-[10px] font-bold text-amber-200">Solar → Wind → Battery → Diesel</span>
                  {recommended && <span className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-2 text-[10px] font-bold text-cyan-200">Confidence {selectedOption.confidencePercent.toFixed(0)}%</span>}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button disabled={!selectedOption} onClick={apply} className="flex items-center gap-1.5 rounded-lg bg-emerald-400 px-3 py-2 text-[10px] font-black text-slate-950 disabled:opacity-40"><Check className="h-3.5 w-3.5" /> {applied || appliedStrategyCode === selectedOption?.code ? 'APPLIED' : 'APPLY THIS STRATEGY'}</button>
                  <button disabled={!selectedOption} onClick={simulate} className="flex items-center gap-1.5 rounded-lg border border-cyan-400/50 bg-cyan-500/10 px-3 py-2 text-[10px] font-black text-cyan-200 disabled:opacity-40"><Play className="h-3.5 w-3.5" /> OPEN SIMULATOR</button>
                  <button onClick={() => setShowWhy(v => !v)} className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-black/20 px-3 py-2 text-[10px] font-bold text-slate-300"><CircleHelp className="h-3.5 w-3.5" /> WHY THIS STRATEGY?</button>
                </div>
              </div>

              <div className="polar-interactive-card rounded-xl border border-cyan-950 bg-black/20 p-3">
                <div className="mb-3 text-[10px] font-bold uppercase tracking-wider text-slate-500">Expected impact</div>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between"><span className="text-slate-400">Fuel / {horizon}h</span><b className="text-orange-300">{selectedImpact ? `${selectedImpact.fuel.toFixed(0)} L` : '—'}</b></div>
                  <div className="flex justify-between"><span className="text-slate-400">Renewable</span><b className="text-emerald-300">{selectedImpact ? `${selectedImpact.renewable.toFixed(0)}%` : '—'}</b></div>
                  <div className="flex justify-between"><span className="text-slate-400">Min SOC</span><b className="text-cyan-300">{selectedImpact ? `${selectedImpact.reserve.toFixed(0)}%` : '—'}</b></div>
                  <div className="flex justify-between"><span className="text-slate-400">Unserved load</span><b className={selectedImpact && selectedImpact.unserved > 0 ? 'text-red-300' : 'text-emerald-300'}>{selectedImpact ? `${selectedImpact.unserved.toFixed(1)} kW` : '—'}</b></div>
                </div>
              </div>
            </div>
          </section>

          <section className="polar-interactive-card rounded-2xl border border-violet-900/60 bg-[#050b18] p-4 shadow-xl">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div><div className="text-sm font-black text-white">DHRUVA Decision Trace</div><p className="text-[10px] text-slate-500">Forecast → Reserve → Optimization → Safety → Decision</p></div>
              <button onClick={loadDecisionTrace} disabled={traceLoading} className="rounded-lg border border-violet-700/60 bg-violet-500/10 px-3 py-1.5 text-[10px] font-bold text-violet-200">{traceLoading ? 'CHECKING…' : 'REFRESH TRACE'}</button>
            </div>
            {decisionTrace ? <>
              <div className="mt-3 grid grid-cols-2 lg:grid-cols-5 gap-2">
              <div className="rounded-lg border border-slate-800 bg-black/20 p-2"><div className="text-[9px] text-slate-500">DECISION</div><div className="mt-1 text-[11px] font-bold text-cyan-200">{decisionTrace.decision.replaceAll('_',' ')}</div></div>
              <div className="rounded-lg border border-slate-800 bg-black/20 p-2"><div className="text-[9px] text-slate-500">DYNAMIC RESERVE</div><div className="mt-1 text-sm font-black text-violet-300">{decisionTrace.dynamic_reserve_percent.toFixed(1)}%</div></div>
              <div className="rounded-lg border border-slate-800 bg-black/20 p-2"><div className="text-[9px] text-slate-500">FUEL DELTA</div><div className="mt-1 text-sm font-black text-emerald-300">{decisionTrace.baseline_comparison.delta.fuel_saved_liters >= 0 ? '+' : ''}{decisionTrace.baseline_comparison.delta.fuel_saved_liters.toFixed(1)} L</div></div>
              <div className="rounded-lg border border-slate-800 bg-black/20 p-2"><div className="text-[9px] text-slate-500">SAFETY SHIELD</div><div className={`mt-1 text-sm font-black ${decisionTrace.safety_validation.passed ? 'text-emerald-300' : 'text-red-300'}`}>{decisionTrace.safety_validation.passed ? 'PASS' : 'REJECTED'}</div></div>
              <div className="rounded-lg border border-slate-800 bg-black/20 p-2"><div className="text-[9px] text-slate-500">DECISION ID</div><div className="mt-1 truncate font-mono text-[10px] text-slate-300">{decisionTrace.decision_id}</div></div>
            </div>
            <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2">
              <div className="rounded-lg border border-cyan-950 bg-black/20 p-2"><div className="text-[9px] text-slate-500">FORECAST UNCERTAINTY</div><div className="mt-1 text-sm font-black text-cyan-200">{decisionTrace.uncertainty?.minimum_confidence_percent.toFixed(0) ?? '—'}%</div><div className="text-[9px] text-slate-600">minimum model confidence</div></div>
              <div className="rounded-lg border border-violet-950 bg-black/20 p-2"><div className="text-[9px] text-slate-500">FUEL AUTONOMY</div><div className="mt-1 text-sm font-black text-violet-200">{decisionTrace.fuel_autonomy?.p10_days.toFixed(1) ?? '—'} d</div><div className="text-[9px] text-slate-600">conservative safe window</div></div>
              <div className="rounded-lg border border-amber-950 bg-black/20 p-2"><div className="text-[9px] text-slate-500">ASSET HEALTH</div><div className="mt-1 text-sm font-black text-amber-200">DG {decisionTrace.asset_health?.generator_health_percent.toFixed(0) ?? '—'}% · BESS {decisionTrace.asset_health?.battery_soh_percent.toFixed(0) ?? '—'}%</div><div className="text-[9px] text-slate-600">dispatch-aware health context</div></div>
            </div>
            <div className="mt-2 text-[9px] text-slate-600">Planning case: {decisionTrace.planning_case ?? 'P90_LOAD_P10_RENEWABLE'} · P10/P50/P90 bands are engineering uncertainty estimates, not calibrated probabilities.</div>
            </> : <div className="mt-3 rounded-lg border border-slate-800 bg-black/20 p-3 text-[10px] text-slate-500">Run optimization to generate the backend decision trace and baseline comparison.</div>}
          </section>

          <section className="polar-interactive-card rounded-2xl border border-cyan-900/70 bg-[#04101e]/95 p-4 shadow-xl">
            <div className="mb-2 flex items-center justify-between"><div><div className="flex items-center gap-2 text-sm font-black text-white"><Zap className="h-4 w-4 text-cyan-300" /> {horizon}-Hour Optimized Energy Plan</div><p className="text-[10px] text-slate-500">{isPreviewingAlternative ? `Previewing ${selectedOption?.name}` : 'Backend forecast and selected dispatch schedule.'}</p></div><span className="text-[9px] font-mono text-cyan-300">{forecast.length} forecast points</span></div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 8, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#12304a" />
                  <XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 9 }} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: '#061323', border: '1px solid #164e63', borderRadius: 10, fontSize: 10 }} />
                  <Legend wrapperStyle={{ fontSize: 9, paddingTop: 4 }} />
                  <Line type="monotone" dataKey="load" name="Load" stroke="#e2e8f0" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="solar" name="Solar" stroke="#fbbf24" strokeWidth={1.8} dot={false} />
                  <Line type="monotone" dataKey="wind" name="Wind" stroke="#34d399" strokeWidth={1.8} dot={false} />
                  <Line type="monotone" dataKey="battery" name="Battery" stroke="#38bdf8" strokeWidth={1.6} dot={false} />
                  <Bar dataKey="diesel" name="Diesel" fill="#f97316" opacity={0.65} barSize={8} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="polar-interactive-card rounded-2xl border border-cyan-900/70 bg-[#04101e]/95 p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between"><div className="text-sm font-black text-white">Alternative Strategies Comparison</div><span className="text-[9px] text-slate-500">Backend generated</span></div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              {allStrategies.slice(0, 4).map(option => {
                const isSelected = selectedOption?.code === option!.code;
                return (
                  <button key={option!.code} onClick={() => { setSelectedStrategyCode(option!.code); setMessage(`${option!.name} selected · chart and expected impact updated.`); }} aria-pressed={isSelected} className={`rounded-xl border p-3 text-left transition-all duration-200 ${isSelected ? 'border-cyan-300 bg-cyan-500/10 ring-1 ring-cyan-300/50 shadow-lg shadow-cyan-500/10 -translate-y-0.5' : option!.isRecommended ? 'border-emerald-500/60 bg-emerald-500/5 hover:border-emerald-300' : 'border-cyan-950 bg-black/20 hover:border-cyan-800 hover:bg-cyan-500/5'}`}>
                    <div className="flex items-center justify-between gap-2"><span className="text-[11px] font-black text-white">{option!.name}</span><span className={`text-[8px] font-bold ${isSelected ? 'text-cyan-300' : option!.isRecommended ? 'text-emerald-300' : 'text-slate-500'}`}>{isSelected ? 'SELECTED' : option!.isRecommended ? 'RECOMMENDED' : 'PREVIEW'}</span></div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]"><span className="text-slate-500">Fuel <b className="ml-1 text-orange-300">{(option!.projectedFuelL ?? option!.projectedFuel24hL ?? 0).toFixed(0)} L / {horizon}h</b></span><span className="text-slate-500">Renewable <b className="ml-1 text-emerald-300">{option!.renewableUtilizationPercent.toFixed(0)}%</b></span><span className="text-slate-500">Reserve <b className="ml-1 text-cyan-300">{option!.reserveLevelPercent.toFixed(0)}%</b></span><span className="text-slate-500">Risk <b className="ml-1 text-slate-200">{option!.unservedLoadKw > 0 ? 'WATCH' : 'LOW'}</b></span></div>
                    {isSelected && <div className="mt-2 border-t border-cyan-400/20 pt-2 text-[9px] font-semibold text-cyan-200">Clicking this strategy updates the plan preview above.</div>}
                  </button>
                );
              })}
            </div>
          </section>
        </main>

        {/* Advisory */}
        <aside className="polar-interactive-card rounded-2xl border border-cyan-900/70 bg-[#04101e]/95 p-4 shadow-xl">
          <div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-black text-white"><Sparkles className="h-4 w-4 text-cyan-300" /> Advisory & Insights</div><span className="rounded-full bg-amber-500/10 px-2 py-1 text-[9px] font-bold text-amber-300">AI ADVISORY</span></div>

          <div className="polar-interactive-card mt-4 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3">
            <div className="text-[9px] font-bold uppercase tracking-wider text-amber-300">Primary recommendation</div>
            <div className="mt-2 text-sm font-black text-white">{selectedOption ? `${selectedOption.batteryAction === 'DISCHARGE' ? 'Preserve battery reserve and ' : ''}${selectedOption.generatorsOnline.length ? `use ${selectedOption.generatorsOnline.join(', ')}` : 'maximize renewable generation'}.` : 'Run optimization to generate an advisory.'}</div>
          </div>

          {showWhy && (
            <div className="polar-interactive-card mt-3 rounded-xl border border-cyan-950 bg-black/20 p-3">
              <button onClick={() => setShowWhy(v => !v)} className="flex w-full items-center justify-between text-[10px] font-bold text-cyan-300">WHY THIS RECOMMENDATION? <ChevronRight className="h-3 w-3 rotate-90" /></button>
              <div className="mt-3 space-y-3">
                {(strategy?.reasoningPoints ?? []).slice(0, 4).map((point, index) => <div key={`${point.title}-${index}`} className="flex gap-2 text-[10px] leading-relaxed"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cyan-500/10 text-cyan-300">{index + 1}</span><span className="text-slate-400"><b className="text-slate-200">{point.title}:</b> {point.explanation}</span></div>)}
                {!strategy?.reasoningPoints?.length && <p className="text-[10px] text-slate-500">Backend reasoning will appear after optimization.</p>}
              </div>
            </div>
          )}

          <div className="polar-interactive-card mt-3 rounded-xl border border-cyan-950 bg-black/20 p-3">
            <div className="mb-2 text-[9px] font-bold uppercase tracking-wider text-slate-500">Next key events</div>
            <div className="space-y-2 text-[10px]">
              {forecast.slice(0, 5).map((point, index) => <div key={`${point.timestamp}-${index}`} className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-cyan-300" /><span className="w-10 text-slate-500">{point.hourOffset === 0 ? 'NOW' : `+${point.hourOffset}h`}</span><span className="truncate text-slate-300">Load {point.predictedTotalLoadKw.toFixed(0)} kW · Wind {point.windSpeedMs.toFixed(1)} m/s</span></div>)}
            </div>
          </div>

          <div className="polar-interactive-card mt-3 rounded-xl border border-cyan-950 bg-black/20 p-3">
            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-300"><Wind className="h-3.5 w-3.5 text-cyan-300" /> Forecast context</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]"><span className="text-slate-500">Peak load <b className="text-white">{strategy?.predictedPeakLoadKw.toFixed(0) ?? '—'} kW</b></span><span className="text-slate-500">Avg wind <b className="text-white">{strategy?.predictedAvgWindMs.toFixed(1) ?? '—'} m/s</b></span><span className="text-slate-500">Peak solar <b className="text-white">{strategy?.predictedPeakSolarKw.toFixed(0) ?? '—'} kW</b></span><span className="text-slate-500">Min temp <b className="text-sky-300">{strategy?.predictedMinTempC.toFixed(1) ?? '—'}°C</b></span></div>
          </div>

          <div className="mt-3 border-t border-cyan-950 pt-3 text-[9px] leading-relaxed text-slate-600">DATA STATUS: ENGINEERING MODEL · Decision support is bounded and backend-authoritative; no global optimality claim.</div>
        </aside>
      </div>
    </div>
  );
};
