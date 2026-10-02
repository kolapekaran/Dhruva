import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Battery,
  CheckCircle2,
  CloudSnow,
  Fuel,
  Gauge,
  Play,
  RotateCcw,
  Snowflake,
  Sun,
  Wind,
  Zap,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { SIMULATION_SCENARIOS } from '../../data/stationData';
import { SimulatorScenario } from '../../types';
import { compareWhatIfScenario, simulateFailureScenario, fetchDhruva72hStressTest } from '../../integration/api';
import { ResilienceScenarioResult, SimulationPoint, WhatIfComparisonResult } from '../../integration/types';
import { useStation } from '../../integration/StationContext';

const scenarioMap: Record<string, string> = {
  'generator-failure': 'DG1_FAILURE',
  'battery-failure': 'BATTERY_FAILURE',
  'renewable-collapse': 'RENEWABLE_COLLAPSE',
  'extreme-cold': 'EXTREME_COLD',
  'fuel-shortage': 'FUEL_SHORTAGE',
  'high-research-load': 'HIGH_RESEARCH_LOAD',
  'storm-high-wind': 'STORM_HIGH_WIND',
  'low-wind': 'LOW_WIND',
  'low-solar': 'LOW_SOLAR',
  'multiple-failures': 'MULTIPLE_FAILURES',
};

type ViewMode = 'twin' | 'flow' | 'assets' | 'environment' | 'loads';

const VIEW_LABELS: Record<ViewMode, string> = {
  twin: 'Scenario Map',
  flow: 'Energy Flow',
  assets: 'Asset Status',
  environment: 'Environment',
  loads: 'Load View',
};

const ScenarioMapVisual: React.FC<{ scenarioLabel: string; failedAssetId?: string | null; summary: Record<string,string>; snapshot: any }> = ({ scenarioLabel, failedAssetId, summary, snapshot }) => {
  const failed = failedAssetId === 'DG1' || summary.failure === 'Diesel Gen 1';
  return <div className="relative min-h-[430px] overflow-hidden bg-[#020914] p-4 sm:p-6"><div className="absolute inset-0 opacity-35" style={{backgroundImage:'linear-gradient(rgba(34,211,238,.06) 1px, transparent 1px),linear-gradient(90deg, rgba(34,211,238,.06) 1px, transparent 1px)',backgroundSize:'30px 30px'}}/><div className="relative h-[385px]"><div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-cyan-400/70 bg-cyan-950/70 px-7 py-5 text-center shadow-[0_0_35px_rgba(34,211,238,.12)]"><div className="text-[9px] tracking-widest text-cyan-300">SIMULATION BUS</div><div className="mt-1 text-xl font-black text-white">SCENARIO STATE</div><div className="mt-1 text-[9px] text-slate-400">{scenarioLabel}</div></div><div className="absolute left-1/2 top-5 -translate-x-1/2 w-44 rounded-xl border border-emerald-900/70 bg-[#061425]/95 p-3 text-center"><div className="text-[8px] tracking-widest text-slate-500">RENEWABLES</div><div className="text-sm font-black text-emerald-300">{Math.round(snapshot.powerBalance.solarGenKw + snapshot.powerBalance.windGenKw)} kW</div></div><div className="absolute left-4 top-[34%] w-40 rounded-xl border border-cyan-900/80 bg-[#061425]/95 p-3"><div className="text-[8px] tracking-widest text-slate-500">BATTERY</div><div className="text-sm font-black text-cyan-300">{summary.battery}</div></div><div className={`absolute right-4 top-[34%] w-40 rounded-xl border ${failed?'border-red-500/60 bg-red-950/30':'border-orange-900/70 bg-[#061425]/95'} p-3`}><div className="text-[8px] tracking-widest text-slate-500">DIESEL GENERATION</div><div className={`text-sm font-black ${failed?'text-red-300':'text-orange-300'}`}>{failed?'DG-01 FAILED':`${Math.round(snapshot.powerBalance.dieselGenKw)} kW`}</div></div><div className="absolute left-1/2 bottom-5 -translate-x-1/2 w-52 rounded-xl border border-cyan-900/80 bg-[#061425]/95 p-3 text-center"><div className="text-[8px] tracking-widest text-slate-500">CRITICAL LOAD</div><div className="text-sm font-black text-white">{summary.researchLoad}</div><div className="text-[9px] text-emerald-300">Scenario coverage tracked</div></div><svg className="absolute inset-0 h-full w-full pointer-events-none" viewBox="0 0 900 385"><g stroke="#155e75" strokeWidth="3" fill="none" strokeDasharray="7 8"><path d="M450 60 L450 150"/><path d="M175 180 L390 190"/><path d="M725 180 L510 190"/><path d="M450 235 L450 325"/></g><circle cx="450" cy="120" r="4" fill="#22d3ee"><animate attributeName="cy" values="70;140" dur="1.5s" repeatCount="indefinite"/></circle><circle cx="240" cy="183" r="4" fill="#22d3ee"><animate attributeName="cx" values="180;370" dur="1.8s" repeatCount="indefinite"/></circle></svg></div></div>;
};

export const SimulatorTab: React.FC = () => {
  const { snapshot, systemMode, setSystemMode, applySimulationPoint, clearSimulationState, setSimulationTrajectory } = useStation();
  const [selectedScenario, setSelectedScenario] = useState<SimulatorScenario>(SIMULATION_SCENARIOS.find(s => s.id === 'generator-failure') || SIMULATION_SCENARIOS[0]);
  const [scenarioMode, setScenarioMode] = useState<'preset' | 'custom'>('preset');
  const [viewMode, setViewMode] = useState<ViewMode>('twin');
  const [hours, setHours] = useState(72);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ResilienceScenarioResult | null>(null);
  const [comparison, setComparison] = useState<WhatIfComparisonResult | null>(null);
  const [error, setError] = useState('');
  const [stressTest, setStressTest] = useState<import('../../integration/types').DhruvaStressTest72h | null>(null);
  const [stressLoading, setStressLoading] = useState(false);
  const simulationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const simulationIndexRef = useRef(0);

  const [custom, setCustom] = useState({
    loadIncrease: 30,
    windReduction: 0,
    solarReduction: 60,
    temperature: -35,
    windSpeed: 20,
    initialSoc: Math.round(snapshot.battery.socPercent),
    fuelLiters: Math.round(snapshot.fuel.currentVolumeLiters),
    batteryHealth: 100,
    dieselAvailable: false,
    resupplyDelayDays: 0,
  });

  const runDhruvaStressTest = async () => {
    setStressLoading(true);
    setError('');
    try {
      setStressTest(await fetchDhruva72hStressTest());
    } catch (e) {
      setError(e instanceof Error ? e.message : '72h stress test failed');
    } finally {
      setStressLoading(false);
    }
  };

  const scenarioKey = scenarioMode === 'custom'
    ? 'CUSTOM_SCENARIO'
    : (scenarioMap[selectedScenario.id] || selectedScenario.id.toUpperCase().replaceAll('-', '_'));

  const overrides = scenarioMode === 'custom'
    ? {
        wind_reduction_percent: custom.windReduction,
        wind_speed_override_mps: custom.windSpeed,
        solar_reduction_percent: custom.solarReduction,
        load_increase_percent: custom.loadIncrease,
        temperature_override_celsius: custom.temperature,
        battery_health_percent: custom.batteryHealth,
        initial_soc_percent: custom.initialSoc,
        initial_fuel_liters: custom.fuelLiters,
        diesel_available: custom.dieselAvailable,
        resupply_delay_days: custom.resupplyDelayDays,
      }
    : {};

  const points = result?.points ?? [];
  const chartData = useMemo(() => points.map((p: SimulationPoint) => ({
    hour: p.hour_offset,
    load: Math.round(p.load_kw),
    solar: Math.round(p.solar_power_kw),
    wind: Math.round(p.wind_power_kw),
    diesel: Math.round(p.diesel_power_kw),
    batteryFlow: Math.round(p.load_kw - p.solar_power_kw - p.wind_power_kw - p.diesel_power_kw),
    soc: Math.round(p.battery_soc_percent),
    fuel: Math.round(p.fuel_remaining_liters),
  })), [points]);

  const scenarioLabel = scenarioMode === 'custom' ? 'Custom scenario' : selectedScenario.name;
  const failedAssetId = scenarioMode === 'custom'
    ? (!custom.dieselAvailable ? 'diesel-generators' : custom.batteryHealth <= 0 ? 'battery-system' : undefined)
    : selectedScenario.id === 'generator-failure' || selectedScenario.id === 'multiple-failures' ? 'diesel-generators'
      : selectedScenario.id === 'battery-failure' ? 'battery-system'
        : selectedScenario.id === 'fuel-shortage' ? 'fuel-tanks'
          : selectedScenario.id === 'low-solar' ? 'solar-array'
            : selectedScenario.id === 'low-wind' || selectedScenario.id === 'storm-high-wind' ? 'wind-turbines' : undefined;

  const scenarioSummary = useMemo(() => {
    if (scenarioMode === 'custom') {
      return {
        temperature: `${custom.temperature}°C`,
        wind: `${custom.windSpeed} m/s`,
        solar: custom.solarReduction > 0 ? `-${custom.solarReduction}%` : 'Normal',
        snowfall: custom.temperature <= -30 ? 'High' : 'Medium',
        researchLoad: `+${custom.loadIncrease}%`,
        livingLoad: `+${Math.round(custom.loadIncrease * 0.65)}%`,
        failure: custom.dieselAvailable ? 'None' : 'Diesel Gen 1',
        battery: custom.batteryHealth < 80 ? 'Degraded' : 'Normal',
      };
    }
    const id = selectedScenario.id;
    return {
      temperature: id === 'extreme-cold' || id === 'multiple-failures' ? '-35°C' : `${Math.round(snapshot.weather.temperature)}°C`,
      wind: id === 'storm-high-wind' ? '20 m/s' : id === 'low-wind' ? '2.5 m/s' : `${snapshot.weather.windSpeed.toFixed(1)} m/s`,
      solar: id === 'low-solar' || id === 'renewable-collapse' ? 'Low' : 'Normal',
      snowfall: id === 'extreme-cold' || id === 'multiple-failures' ? 'High' : 'Medium',
      researchLoad: id === 'high-research-load' ? '+40%' : id === 'extreme-cold' || id === 'multiple-failures' ? '+35%' : 'Normal',
      livingLoad: id === 'high-research-load' ? '+26%' : 'Normal',
      failure: failedAssetId === 'diesel-generators' ? 'Diesel Gen 1' : failedAssetId ? failedAssetId.replaceAll('-', ' ') : 'None',
      battery: failedAssetId === 'battery-system' ? 'Failed' : 'Normal',
    };
  }, [scenarioMode, selectedScenario.id, snapshot.weather.temperature, snapshot.weather.windSpeed, custom, failedAssetId]);

  const currentGeneration = Math.round(snapshot.powerBalance.totalGenerationKw);
  const currentLoad = Math.round(snapshot.powerBalance.totalLoadKw);
  const currentFuel = Math.round(snapshot.fuel.currentVolumeLiters);
  const currentSoc = Math.round(snapshot.battery.socPercent);

  const resultMetrics = result ? {
    generation: Math.round(result.totalGenerationKw),
    load: Math.round(points.at(-1)?.load_kw ?? currentLoad),
    fuel: result.fuelConsumptionLhr,
    soc: Math.round(result.batterySocMinPercent),
  } : {
    generation: currentGeneration,
    load: currentLoad,
    fuel: Math.round(snapshot.fuel.currentConsumptionRateLhr),
    soc: currentSoc,
  };

  const fuelStart = points[0]?.fuel_remaining_liters ?? currentFuel;
  const fuelEnd = points.at(-1)?.fuel_remaining_liters ?? fuelStart;
  const fuelDelta = fuelEnd - fuelStart;
  const dieselDispatchHours = points.filter((p) => p.diesel_power_kw > 0.1).length;
  const unservedEnergyKwh = comparison?.whatIf.loadShedEnergyKwh ?? null;

  const outcome = result?.resilienceOutcome ?? 'OPTIMAL_RECOVERY';
  const outcomeLabel = outcome === 'CRITICAL_RISK' ? 'High Risk Scenario' : outcome === 'MITIGATED' ? 'Mitigated Operation' : 'Stable Operation';
  const outcomeClass = outcome === 'CRITICAL_RISK' ? 'border-red-500/40 bg-red-500/10 text-red-200' : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200';

  // Replay the returned trajectory through the shared StationContext so the
  // The simulator and every other tab consume the shared simulated station state.
  useEffect(() => {
    if (simulationTimerRef.current) {
      clearInterval(simulationTimerRef.current);
      simulationTimerRef.current = null;
    }
    if (systemMode !== 'SIMULATION' || points.length < 2) return;
    simulationIndexRef.current = 0;
    applySimulationPoint(points[0]);
    simulationTimerRef.current = setInterval(() => {
      simulationIndexRef.current += 1;
      const next = points[simulationIndexRef.current];
      if (!next) {
        if (simulationTimerRef.current) clearInterval(simulationTimerRef.current);
        simulationTimerRef.current = null;
        return;
      }
      applySimulationPoint(next);
    }, 1200);
    return () => {
      if (simulationTimerRef.current) clearInterval(simulationTimerRef.current);
      simulationTimerRef.current = null;
    };
  }, [result, systemMode, points, applySimulationPoint]);

  const runSimulation = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    setComparison(null);
    setSystemMode('SIMULATION');
    try {
      const data = await simulateFailureScenario(scenarioKey, hours, 0, overrides, true);
      setResult(data);
      setSimulationTrajectory(data.points ?? []);
      const compare = await compareWhatIfScenario(scenarioKey, hours, 0, overrides, true);
      setComparison(compare);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setRunning(false);
    }
  };

  const reset = async () => {
    if (simulationTimerRef.current) {
      clearInterval(simulationTimerRef.current);
      simulationTimerRef.current = null;
    }
    setResult(null);
    setComparison(null);
    setError('');
    await clearSimulationState();
  };

  const insightList = result?.recommendedActions?.slice(0, 4) ?? [
    'Configure a scenario and run the isolated simulated station state.',
    'Compare the simulated trajectory with the current operating plan.',
    'Review fuel reserve and battery headroom before applying an action.',
  ];

  return (
    <div className="space-y-3 text-slate-200">
  <section className="polar-interactive-card mb-3 rounded-xl border border-violet-900/60 bg-[#030b17] p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div><h2 className="text-sm font-black text-white">72-Hour Polar Stress Test</h2><p className="text-[10px] text-slate-500">Staged failures run on an isolated Digital Twin; live state is untouched.</p></div>
      <button onClick={runDhruvaStressTest} disabled={stressLoading} className="rounded-lg border border-violet-600/60 bg-violet-500/10 px-3 py-2 text-[10px] font-black text-violet-200 disabled:opacity-50">{stressLoading ? 'RUNNING 72H…' : 'RUN 72H STRESS TEST'}</button>
    </div>
    {stressTest && <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-2">
      <StatusTile icon={<Fuel />} label="Fuel Used" value={`${stressTest.metrics.fuel_consumed_liters.toFixed(0)} L`} />
      <StatusTile icon={<Battery />} label="Min SOC" value={`${stressTest.metrics.minimum_battery_soc_percent.toFixed(1)}%`} />
      <StatusTile icon={<CheckCircle2 />} label="Critical Coverage" value={`${stressTest.metrics.critical_load_coverage_percent.toFixed(1)}%`} />
      <StatusTile icon={<AlertTriangle />} label="Shed Energy" value={`${stressTest.metrics.load_shed_energy_kwh.toFixed(1)} kWh`} />
      <StatusTile icon={<Gauge />} label="Safety" value={stressTest.success ? 'PASS' : `${stressTest.metrics.critical_load_failure_steps} breach(es)`} />
    </div>}
    {stressTest && <div className="mt-2 flex flex-wrap gap-1.5">{stressTest.events.map(e => <span key={`${e.hour_offset}-${e.event}`} className="rounded-md border border-slate-800 bg-black/20 px-2 py-1 text-[9px] text-slate-400">H+{e.hour_offset} · {e.event.replaceAll('_',' ')}</span>)}</div>}
  </section>

      <div className="polar-interactive-card flex flex-col gap-2 rounded-xl border border-cyan-900/60 bg-[#030b17] px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-lg font-bold text-white">Simulator</h1>
          <p className="text-[11px] text-cyan-400">Configure → simulate → compare → act</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-[10px] ${systemMode === 'SIMULATION' ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300' : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'}`}>
            ● {systemMode}
          </span>
          <span className="rounded-full border border-slate-800 bg-[#07111f] px-2.5 py-1 text-[10px] text-slate-400">ENGINEERING MODEL</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <aside className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-cyan-300">Scenario Configuration</h2>
              <p className="text-[10px] text-slate-500">Build the operating condition</p>
            </div>
            <button onClick={reset} className="rounded-md border border-slate-700 bg-[#07111f] p-1.5 text-slate-400 hover:text-white" title="Reset"><RotateCcw className="h-3.5 w-3.5" /></button>
          </div>

          <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg border border-cyan-900/50 bg-[#020914] p-1 text-[10px]">
            <button onClick={() => setScenarioMode('preset')} className={`rounded-md py-1.5 ${scenarioMode === 'preset' ? 'bg-cyan-600 text-white' : 'text-slate-400'}`}>Preset</button>
            <button onClick={() => setScenarioMode('custom')} className={`rounded-md py-1.5 ${scenarioMode === 'custom' ? 'bg-cyan-600 text-white' : 'text-slate-400'}`}>Custom</button>
          </div>

          <div className="space-y-3">
            <FieldLabel label="Simulation period">
              <div className="grid grid-cols-3 gap-1">
                {[24, 48, 72].map(v => <button key={v} onClick={() => setHours(v)} className={`rounded-md border py-1.5 text-[10px] ${hours === v ? 'border-cyan-400 bg-cyan-500/15 text-cyan-200' : 'border-slate-800 bg-[#07111f] text-slate-400'}`}>{v}h</button>)}
              </div>
            </FieldLabel>

            {scenarioMode === 'preset' ? (
              <FieldLabel label="Scenario preset">
                <select value={selectedScenario.id} onChange={e => { const next = SIMULATION_SCENARIOS.find(s => s.id === e.target.value); if (next) setSelectedScenario(next); }} className="w-full rounded-md border border-cyan-900 bg-[#061425] px-2 py-2 text-xs text-slate-200 outline-none">
                  {SIMULATION_SCENARIOS.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </FieldLabel>
            ) : (
              <>
                <Slider label="Research load" value={custom.loadIncrease} suffix="%" min={0} max={80} onChange={v => setCustom(c => ({ ...c, loadIncrease: v }))} />
                <Slider label="Wind reduction" value={custom.windReduction} suffix="%" min={0} max={100} onChange={v => setCustom(c => ({ ...c, windReduction: v }))} />
                <Slider label="Solar reduction" value={custom.solarReduction} suffix="%" min={0} max={100} onChange={v => setCustom(c => ({ ...c, solarReduction: v }))} />
                <Slider label="Temperature" value={custom.temperature} suffix="°C" min={-50} max={-5} onChange={v => setCustom(c => ({ ...c, temperature: v }))} />
                <Slider label="Wind speed" value={custom.windSpeed} suffix=" m/s" min={0} max={40} onChange={v => setCustom(c => ({ ...c, windSpeed: v }))} />
                <Slider label="Battery SOC" value={custom.initialSoc} suffix="%" min={0} max={100} onChange={v => setCustom(c => ({ ...c, initialSoc: v }))} />
                <Slider label="Battery health" value={custom.batteryHealth} suffix="%" min={0} max={100} onChange={v => setCustom(c => ({ ...c, batteryHealth: v }))} />
                <Slider label="Fuel reserve" value={custom.fuelLiters} suffix=" L" min={0} max={20000} onChange={v => setCustom(c => ({ ...c, fuelLiters: v }))} />
                <label className="flex items-center justify-between rounded-md border border-slate-800 bg-[#07111f] px-2.5 py-2 text-[10px] text-slate-300"><span>Diesel available</span><input type="checkbox" checked={custom.dieselAvailable} onChange={e => setCustom(c => ({ ...c, dieselAvailable: e.target.checked }))} className="accent-cyan-400" /></label>
              </>
            )}

            <div className="rounded-lg border border-slate-800 bg-[#07111f] p-2.5 text-[10px]">
              <div className="mb-1 flex items-center gap-1 text-slate-400"><CloudSnow className="h-3.5 w-3.5 text-cyan-300" />Active condition</div>
              <div className="font-semibold text-white">{scenarioLabel}</div>
              <div className="mt-1 text-slate-500">{scenarioMode === 'custom' ? `${custom.loadIncrease}% load • ${custom.windReduction}% wind reduction • ${custom.solarReduction}% solar reduction` : selectedScenario.description}</div>
            </div>

            <button disabled={running} onClick={runSimulation} className="w-full rounded-lg bg-cyan-500 py-2.5 text-xs font-bold text-slate-950 shadow-lg shadow-cyan-500/20 disabled:opacity-50">
              <Play className="mr-1 inline h-3.5 w-3.5" />{running ? 'Running simulation…' : 'Run Simulation'}
            </button>
            {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-[10px] text-red-300">{error}</div>}
          </div>
        </aside>

        <section className="polar-interactive-card min-w-0 overflow-hidden rounded-xl border border-cyan-900/60 bg-[#030b17]">
          <div className="flex items-center justify-between border-b border-cyan-900/50 px-3 py-2">
            <div className="flex gap-1 overflow-x-auto">
              {(Object.keys(VIEW_LABELS) as ViewMode[]).map(view => <button key={view} onClick={() => setViewMode(view)} className={`whitespace-nowrap rounded-md px-2.5 py-1.5 text-[10px] ${viewMode === view ? 'border border-cyan-400/60 bg-cyan-500/15 text-cyan-200' : 'text-slate-500 hover:text-slate-300'}`}>{VIEW_LABELS[view]}</button>)}
            </div>
            <div className="ml-2 flex shrink-0 items-center rounded-md border border-cyan-900 bg-[#020914] p-0.5 text-[9px]">
              <button onClick={() => setSystemMode('ONLINE')} className={`rounded px-2 py-1 ${systemMode === 'ONLINE' ? 'bg-emerald-500/15 text-emerald-300' : 'text-slate-500'}`}>ONLINE</button>
              <button onClick={() => setSystemMode('SIMULATION')} className={`rounded px-2 py-1 ${systemMode === 'SIMULATION' ? 'bg-cyan-500/15 text-cyan-300' : 'text-slate-500'}`}>SIMULATION</button>
            </div>
          </div>
          <div className="relative">
            <ScenarioMapVisual scenarioLabel={scenarioLabel} failedAssetId={failedAssetId} summary={scenarioSummary} snapshot={snapshot} />
            <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-cyan-700/50 bg-[#061425]/90 px-3 py-2 backdrop-blur">
              <div className="text-[10px] uppercase tracking-wider text-cyan-400">Scenario Environment</div>
              <div className="text-sm font-semibold text-white">{scenarioLabel}</div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 border-t border-cyan-900/50 p-2 md:grid-cols-4">
            <StatusTile icon={<Snowflake />} label="Temperature" value={scenarioSummary.temperature} />
            <StatusTile icon={<Wind />} label="Wind speed" value={scenarioSummary.wind} />
            <StatusTile icon={<Sun />} label="Solar" value={scenarioSummary.solar} />
            <StatusTile icon={<Gauge />} label="Load change" value={scenarioSummary.researchLoad} />
          </div>
          {viewMode !== 'twin' && <ViewStrip mode={viewMode} snapshot={snapshot} result={result} summary={scenarioSummary} />}
        </section>

        <aside className="space-y-3">
          <section className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3">
            <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-bold text-cyan-300">Scenario Summary</h2><span className="text-[10px] text-slate-500">{hours} hours</span></div>
            <div className="space-y-1.5 text-[10px]">
              <SummaryRow icon={<Snowflake />} label="Weather" value={`${scenarioSummary.temperature} • ${scenarioSummary.snowfall} snowfall`} />
              <SummaryRow icon={<Wind />} label="Wind" value={scenarioSummary.wind} />
              <SummaryRow icon={<Sun />} label="Solar" value={scenarioSummary.solar} />
              <SummaryRow icon={<Gauge />} label="Research load" value={scenarioSummary.researchLoad} />
              <SummaryRow icon={<Gauge />} label="Living load" value={scenarioSummary.livingLoad} />
              <SummaryRow icon={<AlertTriangle />} label="Asset failure" value={scenarioSummary.failure} danger={scenarioSummary.failure !== 'None'} />
              <SummaryRow icon={<Battery />} label="Battery" value={scenarioSummary.battery} />
            </div>
          </section>

          <section className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3">
            <div className="mb-2 flex items-center gap-2"><Zap className="h-4 w-4 text-cyan-300" /><h2 className="text-sm font-bold text-cyan-300">AI Recommendation</h2></div>
            <div className={`rounded-lg border p-2.5 ${outcomeClass}`}><div className="text-xs font-semibold">{result ? outcomeLabel : 'Ready to evaluate'}</div><p className="mt-1 text-[10px] opacity-80">{result?.aiAnalysis ?? 'Run the scenario to generate a backend-grounded recommendation.'}</p></div>
            <div className="mt-2 space-y-1.5">{insightList.map((item, index) => <div key={`${item}-${index}`} className="flex gap-2 rounded-md border border-slate-800 bg-[#07111f] p-2 text-[10px]"><span className="font-mono text-cyan-400">{index + 1}</span><span className="text-slate-300">{item}</span></div>)}</div>
          </section>
        </aside>
      </div>

      <section className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Metric icon={<Zap />} label="Total generation" value={`${resultMetrics.generation} kW`} delta={result ? `${result.generationDeltaPercent >= 0 ? '+' : ''}${result.generationDeltaPercent.toFixed(0)}% vs live` : 'Live baseline'} />
        <Metric icon={<Gauge />} label="Total load" value={`${resultMetrics.load} kW`} delta={result ? `${((resultMetrics.load / Math.max(1, currentLoad) - 1) * 100).toFixed(0)}% vs live` : 'Live baseline'} />
        <Metric icon={<Fuel />} label="Fuel consumption" value={`${resultMetrics.fuel.toFixed(1)} L/h`} delta={result ? `${result.fuelDeltaPercent >= 0 ? '+' : ''}${result.fuelDeltaPercent.toFixed(0)}% vs live` : `${currentFuel.toLocaleString()} L remaining`} />
        <Metric icon={<Battery />} label="Battery SOC" value={`${resultMetrics.soc}%`} delta={result ? `${result.batterySocMinPercent.toFixed(0)}% minimum` : `${currentSoc}% current`} />
      </section>

      {result && (
        <section className="grid grid-cols-1 gap-3 xl:grid-cols-[1.65fr_.85fr]">
          <div className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3">
            <div className="mb-2 flex items-center justify-between"><div><h2 className="text-sm font-bold text-cyan-300">Simulation Results ({hours} hours)</h2><p className="text-[10px] text-slate-500">Closed-loop scenario trajectory</p></div><span className="rounded-md border border-cyan-900 bg-cyan-500/10 px-2 py-1 text-[9px] text-cyan-300">ENGINEERING MODEL</span></div>
            <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-slate-500">
              <span><b className="text-slate-200">Load</b> demand</span>
              <span><b className="text-amber-300">Solar</b> renewable</span>
              <span><b className="text-emerald-300">Wind</b> renewable</span>
              <span><b className="text-rose-300">Diesel</b> dispatch</span>
              <span><b className="text-cyan-300">Battery</b> charge/discharge</span>
            </div>
            <div className="h-64"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><CartesianGrid stroke="#14304a" strokeDasharray="3 3" /><XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={v => `+${v}h`} /><YAxis tick={{ fill: '#64748b', fontSize: 9 }} unit=" kW" /><Tooltip contentStyle={{ background: '#061425', border: '1px solid #164e63', borderRadius: 8, color: '#fff' }} labelFormatter={v => `Hour +${v}`} formatter={(value: number, name: string) => [`${Number(value).toFixed(1)} kW`, name]} /><Line type="monotone" dataKey="load" stroke="#e2e8f0" strokeWidth={2} dot={false} name="Load" /><Line type="monotone" dataKey="solar" stroke="#facc15" strokeWidth={2} dot={false} name="Solar" /><Line type="monotone" dataKey="wind" stroke="#34d399" strokeWidth={2} dot={false} name="Wind" /><Line type="monotone" dataKey="diesel" stroke="#fb7185" strokeWidth={2} dot={false} name="Diesel" /><Line type="monotone" dataKey="batteryFlow" stroke="#22d3ee" strokeWidth={1.5} dot={false} name="Battery flow (+ discharge / − charge)" /></LineChart></ResponsiveContainer></div>
          </div>
          <div className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3">
            <div className="flex items-start justify-between gap-2">
              <div><h2 className="text-sm font-bold text-cyan-300">Fuel Level Projection</h2><p className="text-[10px] text-slate-500">Projected remaining fuel across the selected horizon</p></div>
              <span className="rounded-md border border-slate-800 bg-[#07111f] px-2 py-1 text-[9px] text-slate-400">{dieselDispatchHours > 0 ? `${dieselDispatchHours} dispatch points` : 'No diesel dispatch'}</span>
            </div>
            <div className="mt-2 h-40"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><CartesianGrid stroke="#14304a" strokeDasharray="3 3" /><XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 9 }} tickFormatter={v => `+${v}h`} /><YAxis tick={{ fill: '#64748b', fontSize: 9 }} /><Tooltip contentStyle={{ background: '#061425', border: '1px solid #164e63', borderRadius: 8, color: '#fff' }} labelFormatter={v => `Hour +${v}`} formatter={(value: number) => [`${Number(value).toFixed(0)} L`, 'Fuel remaining']} /><Area type="monotone" dataKey="fuel" stroke="#fb7185" fill="#fb7185" fillOpacity={0.12} name="Fuel (L)" /></AreaChart></ResponsiveContainer></div>
            <div className="mb-2 grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-slate-800 bg-[#07111f] p-2"><div className="text-[9px] uppercase tracking-wide text-slate-500">Start fuel</div><div className="mt-1 text-sm font-bold text-white">{fuelStart.toLocaleString()} L</div></div>
              <div className="rounded-lg border border-slate-800 bg-[#07111f] p-2"><div className="text-[9px] uppercase tracking-wide text-slate-500">End fuel</div><div className="mt-1 text-sm font-bold text-white">{fuelEnd.toLocaleString()} L <span className="text-[9px] font-normal text-cyan-300">({fuelDelta >= 0 ? '+' : ''}{fuelDelta.toFixed(0)} L)</span></div></div>
            </div>
            <div className={`rounded-lg border p-2.5 ${outcomeClass}`}><div className="flex items-center gap-2 text-xs font-semibold"><CheckCircle2 className="h-4 w-4" />{outcomeLabel}</div><p className="mt-1 text-[10px] opacity-80">Critical-load coverage: {result.criticalLoadCoveragePercent.toFixed(1)}% • Minimum SOC: {result.batterySocMinPercent.toFixed(1)}% • Unserved energy: {unservedEnergyKwh === null ? 'pending comparison' : `${unservedEnergyKwh.toFixed(1)} kWh`}</p></div>
          </div>
        </section>
      )}

      {result && (
        <section className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3">
          <div className="flex items-center justify-between"><div><h2 className="text-sm font-bold text-cyan-300">Decision Impact</h2><p className="text-[10px] text-slate-500">What changes if this scenario occurs?</p></div><span className="rounded-md border border-cyan-900 bg-cyan-500/10 px-2 py-1 text-[9px] text-cyan-300">BACKEND COMPARISON</span></div>
          <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2">
            <StatusTile icon={<CheckCircle2 />} label="Critical coverage" value={`${comparison?.whatIf.criticalLoadCoveragePercent.toFixed(1) ?? result.criticalLoadCoveragePercent.toFixed(1)}%`} />
            <StatusTile icon={<Battery />} label="Minimum SOC" value={`${comparison?.whatIf.minimumSocPercent.toFixed(1) ?? result.batterySocMinPercent.toFixed(1)}%`} />
            <StatusTile icon={<Fuel />} label="Fuel impact" value={comparison ? `${comparison.delta.fuelConsumedLiters >= 0 ? '+' : ''}${comparison.delta.fuelConsumedLiters.toFixed(0)} L` : `${result.fuelConsumptionLhr.toFixed(0)} L/h`} />
            <StatusTile icon={<AlertTriangle />} label="Unserved energy" value={comparison ? `${comparison.whatIf.loadShedEnergyKwh.toFixed(1)} kWh` : `${result.unservedLoadKw.toFixed(1)} kW load shed`} />
          </div>
        </section>
      )}

      {result && (
        <section className="grid grid-cols-1 gap-3 xl:grid-cols-[.9fr_1.1fr]">
          <div className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3"><h2 className="text-sm font-bold text-cyan-300">Key Metrics</h2><div className="mt-2 grid grid-cols-2 gap-2">{[
            ['Total load', `${Math.round(resultMetrics.load)} kW`, ''],
            ['Generation', `${Math.round(resultMetrics.generation)} kW`, `${result.generationDeltaPercent >= 0 ? '+' : ''}${result.generationDeltaPercent.toFixed(0)}%`],
            ['Fuel use', `${result.fuelConsumptionLhr.toFixed(1)} L/h`, `${result.fuelDeltaPercent >= 0 ? '+' : ''}${result.fuelDeltaPercent.toFixed(0)}%`],
            ['Battery SOC', `${result.batterySocMinPercent.toFixed(0)}%`, `${result.reserveLevelPercent.toFixed(0)}% reserve`],
          ].map(([label, value, sub]) => <div key={label} className="rounded-lg border border-slate-800 bg-[#07111f] p-2.5"><div className="text-[10px] text-slate-500">{label}</div><div className="mt-1 text-sm font-bold text-white">{value}</div><div className="text-[9px] text-cyan-300">{sub}</div></div>)}</div></div>
          <div className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3"><div className="mb-2 flex items-center justify-between"><h2 className="text-sm font-bold text-cyan-300">Scenario Comparison</h2><span className="text-[9px] text-slate-500">Baseline vs scenario · same horizon</span></div><div className="space-y-3">{comparison ? <>
            <CompareBar label="Generation" baseline={comparison.baseline.averageGenerationKw} scenario={comparison.whatIf.averageGenerationKw} unit=" kW" max={Math.max(comparison.baseline.averageGenerationKw, comparison.whatIf.averageGenerationKw, 1)} />
            <CompareBar label="Fuel consumption" baseline={comparison.baseline.fuelConsumedLiters} scenario={comparison.whatIf.fuelConsumedLiters} unit=" L" max={Math.max(comparison.baseline.fuelConsumedLiters, comparison.whatIf.fuelConsumedLiters, 1)} />
            <CompareBar label="Minimum battery" baseline={comparison.baseline.minimumSocPercent} scenario={comparison.whatIf.minimumSocPercent} unit="%" max={100} />
            <CompareBar label="Unserved energy" baseline={comparison.baseline.loadShedEnergyKwh} scenario={comparison.whatIf.loadShedEnergyKwh} unit=" kWh" max={Math.max(comparison.baseline.loadShedEnergyKwh, comparison.whatIf.loadShedEnergyKwh, 1)} />
          </> : <div className="rounded-lg border border-slate-800 bg-[#07111f] p-3 text-[10px] text-slate-500">Run a simulation to compare the baseline and scenario trajectories.</div>}</div></div>
        </section>
      )}
    </div>
  );
};

const FieldLabel: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => <label className="block"><div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>{children}</label>;

const Slider: React.FC<{ label: string; value: number; suffix: string; min: number; max: number; onChange: (v: number) => void }> = ({ label, value, suffix, min, max, onChange }) => <label className="block"><div className="mb-1 flex justify-between text-[10px]"><span className="text-slate-300">{label}</span><span className="font-mono text-cyan-300">{value}{suffix}</span></div><input type="range" min={min} max={max} value={value} onChange={e => onChange(Number(e.target.value))} className="w-full accent-cyan-400" /></label>;

const SummaryRow: React.FC<{ icon: React.ReactNode; label: string; value: string; danger?: boolean }> = ({ icon, label, value, danger }) => <div className="flex items-center justify-between gap-2 rounded-md border border-slate-800 bg-[#07111f] px-2 py-1.5"><span className="flex min-w-0 items-center gap-1.5 text-slate-500">{icon}<span>{label}</span></span><span className={`truncate text-right ${danger ? 'text-red-300' : 'text-slate-200'}`}>{value}</span></div>;

const StatusTile: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => <div className="rounded-lg border border-slate-800 bg-[#07111f] p-2"><div className="flex items-center gap-1 text-[9px] uppercase tracking-wide text-slate-500">{icon}{label}</div><div className="mt-1 text-xs font-semibold text-white">{value}</div></div>;

const Metric: React.FC<{ icon: React.ReactNode; label: string; value: string; delta: string }> = ({ icon, label, value, delta }) => <div className="polar-interactive-card rounded-xl border border-cyan-900/60 bg-[#030b17] p-3"><div className="flex items-center gap-2 text-slate-500"><span className="text-cyan-300">{icon}</span><span className="text-[10px] uppercase tracking-wide">{label}</span></div><div className="mt-1 text-xl font-bold text-white">{value}</div><div className="text-[10px] text-cyan-300">{delta}</div></div>;

const CompareBar: React.FC<{ label: string; baseline: number; scenario: number; unit: string; max: number }> = ({ label, baseline, scenario, unit, max }) => <div><div className="mb-1 flex justify-between text-[10px]"><span className="text-slate-400">{label}</span><span className="text-slate-500">Baseline / Scenario</span></div><div className="grid grid-cols-[38px_1fr_64px] items-center gap-2"><span className="text-[9px] text-slate-500">Base</span><div className="h-2 rounded-full bg-slate-900"><div className="h-2 rounded-full bg-slate-500" style={{ width: `${Math.min(100, baseline / max * 100)}%` }} /></div><span className="text-right text-[9px] text-slate-300">{baseline.toFixed(0)}{unit}</span></div><div className="mt-1 grid grid-cols-[38px_1fr_64px] items-center gap-2"><span className="text-[9px] text-cyan-400">Scenario</span><div className="h-2 rounded-full bg-slate-900"><div className="h-2 rounded-full bg-cyan-400" style={{ width: `${Math.min(100, scenario / max * 100)}%` }} /></div><span className="text-right text-[9px] text-cyan-200">{scenario.toFixed(0)}{unit}</span></div></div>;

const ViewStrip: React.FC<{ mode: Exclude<ViewMode, 'twin'>; snapshot: any; result: ResilienceScenarioResult | null; summary: Record<string, string> }> = ({ mode, snapshot, result, summary }) => {
  if (mode === 'flow') return <div className="grid grid-cols-3 gap-2 border-t border-cyan-900/50 p-2 text-[10px]"><StatusTile icon={<Sun />} label="Solar" value={`${Math.round(snapshot.powerBalance.solarGenKw)} kW`} /><StatusTile icon={<Wind />} label="Wind" value={`${Math.round(snapshot.powerBalance.windGenKw)} kW`} /><StatusTile icon={<Fuel />} label="Diesel" value={`${Math.round(snapshot.powerBalance.dieselGenKw)} kW`} /></div>;
  if (mode === 'assets') return <div className="grid grid-cols-3 gap-2 border-t border-cyan-900/50 p-2 text-[10px]"><StatusTile icon={<Zap />} label="DG-01" value={summary.failure === 'Diesel Gen 1' ? 'FAILED' : 'ONLINE'} /><StatusTile icon={<Battery />} label="Battery" value={summary.battery} /><StatusTile icon={<Fuel />} label="Fuel" value={`${Math.round(snapshot.fuel.currentVolumeLiters).toLocaleString()} L`} /></div>;
  if (mode === 'environment') return <div className="grid grid-cols-4 gap-2 border-t border-cyan-900/50 p-2 text-[10px]"><StatusTile icon={<Snowflake />} label="Temp" value={summary.temperature} /><StatusTile icon={<Wind />} label="Wind" value={summary.wind} /><StatusTile icon={<Sun />} label="Solar" value={summary.solar} /><StatusTile icon={<CloudSnow />} label="Snow" value={summary.snowfall} /></div>;
  return <div className="grid grid-cols-3 gap-2 border-t border-cyan-900/50 p-2 text-[10px]"><StatusTile icon={<Gauge />} label="Research" value={summary.researchLoad} /><StatusTile icon={<Gauge />} label="Living" value={summary.livingLoad} /><StatusTile icon={<CheckCircle2 />} label="Critical" value={result ? `${result.criticalLoadCoveragePercent.toFixed(0)}% served` : 'Protected'} /></div>;
};
