import React, { useMemo, useState } from 'react';
import {
  Activity,
  BatteryCharging,
  CloudSnow,
  Fuel,
  Leaf,
  ShieldCheck,
  MousePointer2,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { StationNode, TabType } from '../../types';
import { useStation } from '../../integration/StationContext';

interface EnergyTabProps {
  onNavigateTab: (tab: TabType) => void;
  onOpenAnalyticsModal: (node: StationNode) => void;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const formatKw = (value: number) => `${Math.round(value).toLocaleString()} kW`;
const formatMwh = (value: number) => `${value.toFixed(1)} MWh`;


const EnergyFlowVisual: React.FC<{
  solar: number; wind: number; diesel: number; battery: number; load: number;
  selectedSource: 'Solar' | 'Wind' | 'Diesel' | 'Battery';
  onSelect: (source: 'Solar' | 'Wind' | 'Diesel' | 'Battery') => void;
}> = ({ solar, wind, diesel, battery, load, selectedSource, onSelect }) => {
  const sourceTotal = Math.max(1, solar + wind + diesel + Math.max(0, battery));
  const selectedValue = selectedSource === 'Solar' ? solar : selectedSource === 'Wind' ? wind : selectedSource === 'Diesel' ? diesel : Math.abs(battery);
  return <div className="relative min-h-[420px] overflow-hidden bg-[#020914] p-4 sm:p-6">
    <div className="absolute inset-0 opacity-40" style={{backgroundImage:'linear-gradient(rgba(34,211,238,.07) 1px, transparent 1px),linear-gradient(90deg, rgba(34,211,238,.07) 1px, transparent 1px)',backgroundSize:'32px 32px'}} />
    <div className="relative z-10 h-[360px] sm:h-[380px]">
      <svg viewBox="0 0 900 380" className="absolute inset-0 h-full w-full" aria-label="Station energy flow">
        <defs><linearGradient id="energyLine" x1="0" x2="1"><stop offset="0" stopColor="#22d3ee"/><stop offset="1" stopColor="#10b981"/></linearGradient></defs>
        <g stroke="url(#energyLine)" strokeWidth="4" fill="none" strokeLinecap="round" opacity=".8">
          <path d="M150 75 C270 75 310 150 390 185"/><path d="M150 185 C270 185 320 185 390 185"/><path d="M150 295 C270 295 310 220 390 195"/><path d="M510 190 C600 190 650 125 745 125"/><path d="M510 190 C600 190 650 250 745 250"/>
        </g>
        <g fill="#22d3ee"><circle cx="230" cy="90" r="4"><animate attributeName="cx" values="180;360" dur="2s" repeatCount="indefinite"/></circle><circle cx="245" cy="185" r="4"><animate attributeName="cx" values="180;360" dur="1.7s" repeatCount="indefinite"/></circle><circle cx="235" cy="280" r="4"><animate attributeName="cx" values="180;360" dur="2.2s" repeatCount="indefinite"/></circle><circle cx="575" cy="190" r="4"><animate attributeName="cx" values="540;720" dur="1.8s" repeatCount="indefinite"/></circle></g>
      </svg>
      {[['Solar',solar,'top-7 left-3 sm:left-8','text-emerald-300'],['Wind',wind,'top-1/2 -translate-y-1/2 left-3 sm:left-8','text-cyan-300'],['Diesel',diesel,'bottom-7 left-3 sm:left-8','text-orange-300']].map(([name,value,pos,tone]) => <button key={name as string} onClick={()=>onSelect(name as any)} className={`absolute ${pos} w-32 sm:w-40 rounded-xl border ${selectedSource===name?'border-cyan-300 ring-1 ring-cyan-300/50':'border-cyan-900/80'} bg-[#061425]/95 p-3 text-left shadow-lg transition hover:border-cyan-500`}><div className="text-[9px] uppercase tracking-widest text-slate-500">SOURCE</div><div className={`mt-1 text-sm font-black ${tone as string}`}>{name as string}</div><div className="font-mono text-xs text-white">{Number(value).toFixed(0)} kW</div></button>)}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-32 sm:w-40 rounded-2xl border border-cyan-400/70 bg-cyan-950/70 p-4 text-center shadow-[0_0_35px_rgba(34,211,238,.12)]"><div className="text-[9px] uppercase tracking-widest text-cyan-300">POWER BUS</div><div className="mt-1 text-xl font-black text-white">{Math.round(solar+wind+diesel)} kW</div><div className="text-[9px] text-slate-400">SOURCE INPUT</div></div>
      <button onClick={()=>onSelect('Battery')} className={`absolute bottom-6 left-1/2 -translate-x-1/2 w-40 rounded-xl border ${selectedSource==='Battery'?'border-cyan-300 ring-1 ring-cyan-300/50':'border-cyan-900/80'} bg-[#061425]/95 p-3 text-left`}><div className="text-[9px] uppercase tracking-widest text-slate-500">STORAGE</div><div className="mt-1 text-sm font-black text-cyan-300">BATTERY</div><div className="font-mono text-xs text-white">{battery >= 0 ? '+' : ''}{battery.toFixed(0)} kW</div></button>
      <div className="absolute right-3 sm:right-8 top-[72px] w-32 sm:w-40 rounded-xl border border-cyan-900/80 bg-[#061425]/95 p-3"><div className="text-[9px] uppercase tracking-widest text-slate-500">STATION LOAD</div><div className="mt-1 text-sm font-black text-white">{load.toFixed(0)} kW</div><div className="text-[9px] text-cyan-300">ACTIVE DEMAND</div></div>
      <div className="absolute right-3 sm:right-8 bottom-[55px] w-32 sm:w-40 rounded-xl border border-slate-800 bg-[#061425]/95 p-3"><div className="text-[9px] uppercase tracking-widest text-slate-500">SELECTED</div><div className="mt-1 text-sm font-black text-cyan-300">{selectedSource}</div><div className="font-mono text-xs text-white">{selectedValue.toFixed(0)} kW</div><div className="mt-1 text-[8px] text-slate-500">{((selectedValue/sourceTotal)*100).toFixed(0)}% of available source flow</div></div>
    </div>
  </div>;
};

export const EnergyTab: React.FC<EnergyTabProps> = ({ onNavigateTab }) => {
  const { snapshot, systemMode, simulationTrajectory } = useStation();
  const [selectedSource, setSelectedSource] = useState<'Solar' | 'Wind' | 'Diesel' | 'Battery'>('Wind');
  const [selectedKpi, setSelectedKpi] = useState<'load' | 'renewable' | 'diesel' | 'battery' | 'fuel'>('load');
  const [selectedLoad, setSelectedLoad] = useState<string>('');
  const [selectedHour, setSelectedHour] = useState(0);
  const [hoverHour, setHoverHour] = useState<number | null>(null);

  const {
    totalGenerationKw,
    totalLoadKw,
    dieselGenKw,
    windGenKw,
    solarGenKw,
    renewableSharePercent,
  } = snapshot.powerBalance;

  const batterySoc = snapshot.battery.socPercent;
  const batteryPowerKw = snapshot.battery.currentPowerKw;
  const batteryDischargeKw = Math.max(0, batteryPowerKw);
  const batteryChargeKw = Math.max(0, -batteryPowerKw);
  const sourceGenerationKw = Math.max(0, totalGenerationKw);
  const effectiveSupplyKw = sourceGenerationKw + batteryDischargeKw;
  const netBalanceKw = effectiveSupplyKw - totalLoadKw - batteryChargeKw;
  const telemetrySource = systemMode === 'OFFLINE' ? 'CACHED' : systemMode === 'SIMULATION' ? 'SIMULATION' : (snapshot.provenance.powerTelemetrySource || 'BACKEND');
  const forecastSource = systemMode === 'OFFLINE' ? 'CACHED' : systemMode === 'SIMULATION' ? 'SIMULATION' : (snapshot.provenance.forecastModelSource || 'FORECAST');
  // SOURCE · {forecastSource}
  const fuelLiters = snapshot.fuel.currentVolumeLiters;
  const fuelPercent = snapshot.fuel.fillPercent;
  const forecast = useMemo(() => {
    if (systemMode === 'SIMULATION' && simulationTrajectory.length) {
      return simulationTrajectory.map(point => ({
        hourOffset: point.hour_offset,
        predictedTotalLoadKw: point.load_kw,
        predictedSolarKw: point.solar_power_kw,
        predictedWindKw: point.wind_power_kw,
        predictedDieselKw: point.diesel_power_kw,
        predictedBatteryKw: point.diesel_power_kw + point.solar_power_kw + point.wind_power_kw - point.load_kw,
      }));
    }
    return snapshot.horizonForecast;
  }, [systemMode, simulationTrajectory, snapshot.horizonForecast]);

  const energy24 = useMemo(() => {
    const points = forecast.filter(point => point.hourOffset >= 0 && point.hourOffset <= 24).sort((a, b) => a.hourOffset - b.hourOffset);
    if (points.length < 2) return { load: 0, solar: 0, wind: 0, diesel: 0, battery: 0 };

    // Integrate the actual forecast intervals instead of multiplying a point sum
    // by an assumed interval. This remains correct if the backend changes from
    // hourly points to a coarser or mixed-resolution horizon.
    const integrate = (selector: (point: typeof points[number]) => number) => {
      let energyKwh = 0;
      for (let i = 1; i < points.length; i += 1) {
        const hours = Math.max(0, points[i].hourOffset - points[i - 1].hourOffset);
        energyKwh += ((Math.max(0, selector(points[i - 1])) + Math.max(0, selector(points[i]))) / 2) * hours;
      }
      return energyKwh / 1000;
    };
    return {
      load: integrate(p => p.predictedTotalLoadKw),
      solar: integrate(p => p.predictedSolarKw),
      wind: integrate(p => p.predictedWindKw),
      diesel: integrate(p => p.predictedDieselKw),
      battery: integrate(p => Math.abs(p.predictedBatteryKw)),
    };
  }, [forecast]);

  const loadGroups = useMemo(() => {
    const groups = [
      { label: 'Research Facilities', categories: ['CRITICAL_RESEARCH'], color: 'bg-cyan-400' },
      { label: 'Life Support Systems', categories: ['LIFE_SAFETY'], color: 'bg-emerald-400' },
      { label: 'Heating', categories: ['HEATING'], color: 'bg-amber-400' },
      { label: 'Water & Utilities', categories: ['WATER_PUMPS', 'WORKSHOP_UTILITIES'], color: 'bg-sky-400' },
      { label: 'Secondary', categories: ['SECONDARY'], color: 'bg-slate-400' },
    ];
    return groups.map(group => ({
      ...group,
      kw: snapshot.loads.filter(load => group.categories.includes(load.category)).reduce((sum, load) => sum + load.currentLoadKw, 0),
    })).filter(group => group.kw > 0);
  }, [snapshot.loads]);

  const maxLoadGroup = Math.max(1, ...loadGroups.map(group => group.kw));
  const energySourceTotal = Math.max(0.1, energy24.solar + energy24.wind + energy24.diesel);
  const solarShare = energy24.solar / energySourceTotal * 100;
  const windShare = energy24.wind / energySourceTotal * 100;
  const dieselShare = energy24.diesel / energySourceTotal * 100;

  const trend = forecast.filter(point => point.hourOffset >= 0 && point.hourOffset <= 24).slice(0, 25);
  const hoverPoint = hoverHour == null ? null : (trend.find(point => point.hourOffset === hoverHour) || null);
  const chartW = 900;
  const chartH = 220;
  const maxPower = Math.max(100, ...trend.flatMap(point => [point.predictedTotalLoadKw, point.predictedSolarKw, point.predictedWindKw, point.predictedDieselKw]));
  const toX = (index: number) => trend.length <= 1 ? 0 : index / (trend.length - 1) * chartW;
  const toY = (value: number) => chartH - clamp(value / maxPower, 0, 1) * chartH;
  const line = (values: number[]) => values.map((value, index) => `${toX(index)},${toY(value)}`).join(' ');

  return (
    <div className="space-y-3 text-slate-200">
      {/* Energy header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-white tracking-wide">Energy</h1>
          <p className="text-xs text-cyan-400 font-mono mt-0.5">Operational generation, storage, consumption and energy balance</p>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <span className={`rounded-lg border px-2.5 py-1.5 ${systemMode === 'ONLINE' ? 'border-emerald-800/70 bg-emerald-950/30 text-emerald-300' : systemMode === 'SIMULATION' ? 'border-cyan-800/70 bg-cyan-950/30 text-cyan-300' : 'border-slate-700 bg-slate-900/60 text-slate-300'}`}>● {systemMode} · {telemetrySource}</span>
          <span className="flex items-center gap-2 rounded-lg border border-cyan-900/70 bg-[#040d1a] px-2.5 py-1.5 text-slate-300">
            <CloudSnow className="h-3.5 w-3.5 text-cyan-400" /> {snapshot.weather.temperature.toFixed(0)}°C · {snapshot.weather.windSpeed.toFixed(1)} m/s
          </span>
        </div>
      </div>

      {/* Five essential interactive KPIs */}
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-2">
        <KpiButton active={selectedKpi==='load'} onClick={() => setSelectedKpi('load')} icon={<Zap />} label="Total Load" value={formatKw(totalLoadKw)} note={netBalanceKw >= 0 ? (batteryDischargeKw > 0 ? `Battery covers ${batteryDischargeKw.toFixed(0)} kW` : 'Supply balanced') : `${Math.abs(netBalanceKw).toFixed(0)} kW deficit`} tone="amber" />
        <KpiButton active={selectedKpi==='renewable'} onClick={() => setSelectedKpi('renewable')} icon={<Leaf />} label="Renewable Generation" value={formatKw(windGenKw + solarGenKw)} note={`${renewableSharePercent.toFixed(1)}% of source generation`} tone="green" />
        <KpiButton active={selectedKpi==='diesel'} onClick={() => setSelectedKpi('diesel')} icon={<Fuel />} label="Diesel Generation" value={formatKw(dieselGenKw)} note={`${snapshot.generators.filter(g => g.status === 'ONLINE').length}/${snapshot.generators.length} online`} tone="red" />
        <KpiButton active={selectedKpi==='battery'} onClick={() => setSelectedKpi('battery')} icon={<BatteryCharging />} label="Battery SOC" value={`${batterySoc.toFixed(0)}%`} note={`${snapshot.battery.status} · ${Math.abs(batteryPowerKw).toFixed(0)} kW`} tone="cyan" />
        <KpiButton active={selectedKpi==='fuel'} onClick={() => setSelectedKpi('fuel')} icon={<Fuel />} label="Fuel Reserve" value={`${fuelLiters.toLocaleString()} L`} note={`${fuelPercent.toFixed(0)}% · ${snapshot.fuel.estimatedAutonomyDays?.toFixed(1) ?? '—'} days`} tone="orange" />
      </div>
      <div className="rounded-xl border border-cyan-900/60 bg-[#03101d]/95 px-3 py-2 flex flex-wrap items-center justify-between gap-3 text-[10px]">
        <div className="flex items-center gap-2"><MousePointer2 className="h-3.5 w-3.5 text-cyan-400" /><span className="text-slate-400">Selected energy metric</span><b className="text-white uppercase">{selectedKpi}</b></div>
        <div className="text-slate-500">Click a KPI, source, or load group to inspect its live contribution.</div>
      </div>

      {/* Main energy-flow workspace */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2.1fr)_minmax(340px,0.9fr)] gap-3">
        <section className="polar-interactive-card rounded-2xl border border-cyan-900/60 bg-[#030a16] overflow-hidden min-w-0">
          <div className="flex items-center justify-between px-4 py-3 border-b border-cyan-950/80">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <div><h2 className="text-sm font-bold text-white">LIVE ENERGY FLOW</h2><p className="text-[9px] text-slate-500">Generation → storage → load · {systemMode}</p></div>
            </div>
            <button onClick={() => onNavigateTab('command-center')} className="text-[10px] font-semibold text-cyan-300 hover:text-white">Open Command Center →</button>
          </div>
          <EnergyFlowVisual solar={solarGenKw} wind={windGenKw} diesel={dieselGenKw} battery={batteryPowerKw} load={totalLoadKw} selectedSource={selectedSource} onSelect={setSelectedSource} />
        </section>

        <div className="space-y-3">
          <Panel title="Energy Balance" icon={<Activity />}>
            <div className="grid grid-cols-2 gap-2 text-xs mb-2"><div><span className="text-slate-400">Source generation</span><b className="ml-2 text-white">{formatKw(totalGenerationKw)}</b></div><div className="text-right"><span className="text-slate-400">Load</span><b className="ml-2 text-white">{formatKw(totalLoadKw)}</b></div></div>
            <div className="h-3 rounded-full overflow-hidden flex bg-slate-900">
              <div className="bg-emerald-400" style={{ width: `${clamp(totalGenerationKw > 0 ? solarGenKw / totalGenerationKw * 100 : 0, 0, 100)}%` }} />
              <div className="bg-cyan-400" style={{ width: `${clamp(totalGenerationKw > 0 ? windGenKw / totalGenerationKw * 100 : 0, 0, 100)}%` }} />
              <div className="bg-orange-400" style={{ width: `${clamp(totalGenerationKw > 0 ? dieselGenKw / totalGenerationKw * 100 : 0, 0, 100)}%` }} />
            </div>
            <div className="grid grid-cols-3 gap-2 mt-3 text-[10px]
            "><Source label="Solar" value={solarGenKw} color="text-emerald-300" /><Source label="Wind" value={windGenKw} color="text-cyan-300" /><Source label="Diesel" value={dieselGenKw} color="text-orange-300" /></div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-[10px]"><div className="rounded-lg border border-cyan-950 bg-[#030914] p-2"><span className="block text-slate-500">Battery discharge</span><b className="text-cyan-300">{batteryDischargeKw.toFixed(1)} kW</b></div><div className="rounded-lg border border-cyan-950 bg-[#030914] p-2"><span className="block text-slate-500">Battery charge</span><b className="text-cyan-300">{batteryChargeKw.toFixed(1)} kW</b></div><div className="rounded-lg border border-cyan-950 bg-[#030914] p-2"><span className="block text-slate-500">Net balance</span><b className={netBalanceKw >= 0 ? 'text-emerald-300' : 'text-red-300'}>{netBalanceKw >= 0 ? '+' : ''}{netBalanceKw.toFixed(1)} kW</b></div></div>
          </Panel>

          <Panel title="Renewable Share" icon={<Leaf />}>
            <div className="flex items-center gap-4">
              <div className="relative h-28 w-28 rounded-full" style={{ background: `conic-gradient(#10b981 0 ${renewableSharePercent}%, #f59e0b ${renewableSharePercent}% ${clamp(renewableSharePercent + dieselShare, 0, 100)}%, #0f172a ${clamp(renewableSharePercent + dieselShare, 0, 100)}% 100%)` }}>
                <div className="absolute inset-3 rounded-full bg-[#040d1a] flex flex-col items-center justify-center"><b className="text-2xl text-white">{renewableSharePercent.toFixed(0)}%</b><span className="text-[8px] text-slate-500">renewable</span></div>
              </div>
              <div className="space-y-2 text-[10px] flex-1">{([['Solar',solarShare,'bg-emerald-400'],['Wind',windShare,'bg-cyan-400'],['Diesel',dieselShare,'bg-orange-400']] as const).map(([name,share,color]) => <button key={name} onClick={() => setSelectedSource(name as any)} className={`w-full rounded-lg px-2 py-1.5 text-left transition-all ${selectedSource===name ? 'bg-cyan-950/60 ring-1 ring-cyan-400/60' : 'hover:bg-slate-900/70'}`}><LegendDot color={color} label={name} value={`${share.toFixed(0)}%`} /></button>)}</div>
            </div>
          </Panel>

          <Panel title="Battery Operation" icon={<BatteryCharging />} selected={selectedSource==='Battery'} onClick={() => setSelectedSource('Battery')}>
            <div className="grid grid-cols-2 gap-2"><Metric label="State of Charge" value={`${batterySoc.toFixed(0)}%`} /><Metric label="Power" value={`${batteryPowerKw >= 0 ? '+' : ''}${batteryPowerKw.toFixed(0)} kW · ${snapshot.battery.status}`} /><Metric label="Capacity" value={`${snapshot.battery.capacityKwh.toFixed(0)} kWh`} /><Metric label="Health" value={`${snapshot.battery.healthPercent.toFixed(0)}%`} /></div>
            <div className="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-cyan-400" style={{ width: `${clamp(batterySoc, 0, 100)}%` }} /></div>
          </Panel>
        </div>
      </div>

      {/* Trends and breakdown */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.65fr)_minmax(260px,0.65fr)_minmax(280px,0.8fr)] gap-3">
        <Panel title="24-Hour Energy Generation vs Load" icon={<Activity />} subtitle={`Forecast · ${forecastSource}`}>
          <div className="relative h-56 overflow-hidden rounded-lg border border-cyan-950 bg-[#020914]"
            onMouseMove={(event) => {
              if (!trend.length) return;
              const rect = event.currentTarget.getBoundingClientRect();
              const x = clamp(event.clientX - rect.left, 0, rect.width);
              const ratio = rect.width <= 0 ? 0 : x / rect.width;
              const index = Math.max(0, Math.min(trend.length - 1, Math.round(ratio * (trend.length - 1))));
              setHoverHour(trend[index]?.hourOffset ?? null);
            }}
            onMouseLeave={() => setHoverHour(null)}
          >
            {hoverPoint && trend.length > 1 && (
              <div
                className="pointer-events-none absolute top-2 z-20 w-[min(360px,calc(100%-16px))] -translate-x-1/2 rounded-xl border border-cyan-400/50 bg-[#03101d]/95 p-3 shadow-[0_12px_35px_rgba(0,0,0,.45)] backdrop-blur-xl"
                style={{ left: `${clamp((trend.findIndex(p => p.hourOffset === hoverPoint.hourOffset) / (trend.length - 1)) * 100, 18, 82)}%` }}
              >
                <div className="flex items-center justify-between gap-3 border-b border-cyan-950 pb-2">
                  <span className="text-[9px] font-mono uppercase tracking-widest text-cyan-300">Forecast point</span>
                  <b className="font-mono text-xs text-white">H+{hoverPoint.hourOffset}</b>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[10px]">
                  <span className="text-slate-400">Load <b className="text-white">{hoverPoint.predictedTotalLoadKw.toFixed(2)} kW</b></span>
                  <span className="text-slate-400">Solar <b className="text-yellow-300">{hoverPoint.predictedSolarKw.toFixed(2)} kW</b></span>
                  <span className="text-slate-400">Wind <b className="text-emerald-300">{hoverPoint.predictedWindKw.toFixed(2)} kW</b></span>
                  <span className="text-slate-400">Diesel <b className="text-orange-300">{hoverPoint.predictedDieselKw.toFixed(2)} kW</b></span>
                  <span className="text-slate-400 col-span-2">Balance <b className={((hoverPoint.predictedSolarKw + hoverPoint.predictedWindKw + hoverPoint.predictedDieselKw) - hoverPoint.predictedTotalLoadKw) >= 0 ? 'text-emerald-300' : 'text-red-300'}>{((hoverPoint.predictedSolarKw + hoverPoint.predictedWindKw + hoverPoint.predictedDieselKw) - hoverPoint.predictedTotalLoadKw).toFixed(2)} kW</b></span>
                </div>
              </div>
            )}
            <svg viewBox={`0 0 ${chartW} ${chartH + 30}`} className="w-full h-full" preserveAspectRatio="none">
              {[0, 0.25, 0.5, 0.75, 1].map(r => <line key={r} x1="0" y1={chartH * r} x2={chartW} y2={chartH * r} stroke="#10243b" strokeWidth="1" />)}
              {trend.length > 1 && <>
                <polyline points={line(trend.map(p => p.predictedTotalLoadKw))} fill="none" stroke="#e2e8f0" strokeWidth="3" />
                <polyline points={line(trend.map(p => p.predictedSolarKw))} fill="none" stroke="#facc15" strokeWidth="2.5" />
                <polyline points={line(trend.map(p => p.predictedWindKw))} fill="none" stroke="#34d399" strokeWidth="2.5" />
                <polyline points={line(trend.map(p => p.predictedDieselKw))} fill="none" stroke="#f97316" strokeWidth="2.5" />
                {trend.map((p, i) => <circle key={p.hourOffset} cx={toX(i)} cy={toY(selectedSource==='Wind'?p.predictedWindKw:selectedSource==='Solar'?p.predictedSolarKw:selectedSource==='Diesel'?p.predictedDieselKw:p.predictedTotalLoadKw)} r={p.hourOffset===hoverHour ? 5 : 2.5} fill="#22d3ee" opacity={p.hourOffset===hoverHour ? 1 : .45} onMouseEnter={() => setHoverHour(p.hourOffset)} onClick={() => setSelectedHour(p.hourOffset)} className="cursor-pointer" />)}
                <line x1={toX(trend.findIndex(p=>p.hourOffset===(hoverHour ?? selectedHour)))} x2={toX(trend.findIndex(p=>p.hourOffset===(hoverHour ?? selectedHour)))} y1="0" y2={chartH} stroke="#22d3ee" strokeDasharray="4 5" opacity=".55" />
              </>}
            </svg>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-4 text-[9px] font-mono text-slate-400"><div className="flex flex-wrap gap-4"><LegendDot color="bg-slate-200" label="Load" /><LegendDot color="bg-yellow-400" label="Solar" /><LegendDot color="bg-emerald-400" label="Wind" /><LegendDot color="bg-orange-400" label="Diesel" /></div><span className="text-cyan-400">Move the pointer over the chart to inspect a time slice</span></div>
        </Panel>

        <Panel title="Energy Sources · 24h" icon={<Zap />}>
          <div className="text-center py-1"><b className="text-3xl text-white">{formatMwh(energySourceTotal)}</b><p className="text-[9px] text-slate-500">forecast generation · {forecastSource}</p></div>
          <div className="mt-3 space-y-3">{([['Solar',energy24.solar,'bg-yellow-400'],['Wind',energy24.wind,'bg-emerald-400'],['Diesel',energy24.diesel,'bg-orange-400'],['Battery',energy24.battery,'bg-cyan-400']] as const).map(([name,value,color]) => <button key={name} onClick={() => setSelectedSource(name)} className={`w-full text-left rounded-lg p-1.5 transition-all ${selectedSource===name ? 'bg-cyan-950/50 ring-1 ring-cyan-400/60' : 'hover:bg-slate-900/60'}`}><SourceRow label={name === 'Battery' ? 'Battery throughput' : name} value={value} total={energySourceTotal} color={color} /></button>)}</div>
        </Panel>

        <Panel title={`Load Breakdown · ${systemMode}`} icon={<ShieldCheck />}>
          <div className="space-y-2">{loadGroups.map(group => <button key={group.label} onClick={() => setSelectedLoad(group.label)} className={`w-full text-left rounded-lg p-2 transition-all ${selectedLoad===group.label ? 'bg-cyan-950/50 ring-1 ring-cyan-400/60' : 'hover:bg-slate-900/60'}`}><div className="flex justify-between text-[10px] mb-1"><span className="text-slate-300">{group.label}</span><b className="text-white">{group.kw.toFixed(0)} kW</b></div><div className="h-2 rounded-full bg-slate-900 overflow-hidden"><div className={`h-full ${group.color}`} style={{ width: `${group.kw / maxLoadGroup * 100}%` }} /></div></button>)}{!loadGroups.length && <p className="text-xs text-slate-500">No load telemetry available.</p>}</div>
        </Panel>
      </div>

      <div className="rounded-xl border border-cyan-900/60 bg-[#03101d]/95 p-3 flex flex-wrap items-center justify-between gap-3">
        <div><div className="text-[9px] uppercase tracking-wider text-cyan-400">Energy Inspector</div><div className="text-sm font-bold text-white mt-1">{selectedSource} <span className="text-slate-500">·</span> {selectedLoad || 'Station-wide flow'}</div></div>
        <div className="grid grid-cols-3 gap-4 text-[10px]"><span className="text-slate-500">Live source <b className="block text-white">{selectedSource==='Solar'?formatKw(solarGenKw):selectedSource==='Wind'?formatKw(windGenKw):selectedSource==='Diesel'?formatKw(dieselGenKw):formatKw(batteryDischargeKw)}</b></span><span className="text-slate-500">Balance <b className={netBalanceKw>=0?'block text-emerald-300':'block text-red-300'}>{netBalanceKw>=0?'+':''}{netBalanceKw.toFixed(1)} kW</b></span><span className="text-slate-500">Mode <b className="block text-cyan-300">{systemMode}</b></span></div>
      </div>

      {/* Compact operational footer */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
        <Status label="Critical loads" value={snapshot.loads.filter(l => l.priority === 'P0' && l.shedStatus === 'SERVED').length === snapshot.loads.filter(l => l.priority === 'P0').length ? 'PROTECTED' : 'AT RISK'} ok={snapshot.loads.filter(l => l.priority === 'P0').every(l => l.shedStatus === 'SERVED')} />
        <Status label="Reserve" value={`${snapshot.reserve.targetReservePercent.toFixed(0)}% target`} ok={snapshot.reserve.status !== 'CRITICAL_SHORTFALL'} />
        <Status label="Battery" value={snapshot.battery.status} ok={snapshot.battery.healthPercent >= 80} />
        <Status label="Fuel autonomy" value={`${snapshot.fuel.estimatedAutonomyDays?.toFixed(1) ?? '—'} days`} ok={(snapshot.fuel.estimatedAutonomyDays ?? 999) > 2} />
      </div>
    </div>
  );
};

const Kpi = ({ icon, label, value, note, tone }: { icon: React.ReactNode; label: string; value: string; note: string; tone: 'amber'|'green'|'red'|'cyan'|'orange' }) => {
  const styles = { amber: 'text-amber-300 border-amber-900/50', green: 'text-emerald-300 border-emerald-900/50', red: 'text-red-300 border-red-900/50', cyan: 'text-cyan-300 border-cyan-900/50', orange: 'text-orange-300 border-orange-900/50' };
  return <div className={`rounded-xl border bg-[#040d1a]/95 p-3 ${styles[tone]}`}><div className="flex items-center gap-2"><span className="opacity-90">{React.cloneElement(icon as React.ReactElement, { className: 'w-4 h-4' })}</span><span className="text-[9px] uppercase tracking-wider text-slate-500">{label}</span></div><div className="text-lg font-extrabold text-white font-mono mt-1">{value}</div><div className="text-[9px] text-slate-400 mt-0.5">{note}</div></div>;
};

const Panel = ({ title, icon, children, selected=false, onClick, subtitle }: { title: string; icon: React.ReactNode; children: React.ReactNode; selected?: boolean; onClick?: () => void; subtitle?: string }) => <section onClick={onClick} className={`polar-interactive-card rounded-xl border bg-[#040d1a]/95 p-3 transition-all ${selected ? 'border-cyan-400 ring-1 ring-cyan-400/40 shadow-[0_0_22px_rgba(34,211,238,.12)]' : 'border-cyan-900/60'} ${onClick ? 'cursor-pointer hover:border-cyan-700' : ''}`}><div className="flex items-center justify-between gap-2 mb-3"><div className="flex items-center gap-2"><span className="text-cyan-400">{React.cloneElement(icon as React.ReactElement, { className: 'w-4 h-4' })}</span><div><h3 className="text-xs font-bold text-white uppercase tracking-wide">{title}</h3>{subtitle && <p className="text-[8px] text-slate-500 mt-0.5">{subtitle}</p>}</div></div>{selected && <span className="text-[8px] font-bold text-cyan-300 border border-cyan-700 rounded px-1.5 py-0.5">SELECTED</span>}</div>{children}</section>;
const KpiButton = ({ icon, label, value, note, tone, active, onClick }: { icon: React.ReactNode; label: string; value: string; note: string; tone: 'amber'|'green'|'red'|'cyan'|'orange'; active: boolean; onClick: () => void }) => { const styles = { amber: 'text-amber-300 border-amber-900/50', green: 'text-emerald-300 border-emerald-900/50', red: 'text-red-300 border-red-900/50', cyan: 'text-cyan-300 border-cyan-900/50', orange: 'text-orange-300 border-orange-900/50' }; return <button onClick={onClick} className={`rounded-xl border bg-[#040d1a]/95 p-3 text-left transition-all ${styles[tone]} ${active ? 'ring-1 ring-cyan-400 border-cyan-400 shadow-[0_0_22px_rgba(34,211,238,.14)] -translate-y-0.5' : 'hover:-translate-y-0.5 hover:border-cyan-700'}`}><div className="flex items-center gap-2"><span className="opacity-90">{React.cloneElement(icon as React.ReactElement, { className: 'w-4 h-4' })}</span><span className="text-[9px] uppercase tracking-wider text-slate-500">{label}</span><TrendingUp className={`ml-auto h-3 w-3 ${active ? 'text-cyan-300' : 'text-slate-700'}`} /></div><div className="text-lg font-extrabold text-white font-mono mt-1">{value}</div><div className="text-[9px] text-slate-400 mt-0.5">{note}</div></button>; };
const Metric = ({ label, value }: { label: string; value: string }) => <div className="rounded-lg border border-cyan-950 bg-[#030914] p-2"><span className="text-[8px] text-slate-500 block">{label}</span><b className="text-sm text-white font-mono">{value}</b></div>;
const Source = ({ label, value, color }: { label: string; value: number; color: string }) => <div><span className="block text-slate-500">{label}</span><b className={color}>{value.toFixed(0)} kW</b></div>;
const LegendDot = ({ color, label, value }: { color: string; label: string; value?: string }) => <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-1.5"><span className={`w-2 h-2 rounded-full ${color}`} />{label}</span>{value && <b className="text-slate-300">{value}</b>}</div>;
const SourceRow = ({ label, value, total, color }: { label: string; value: number; total: number; color: string }) => <div><div className="flex justify-between text-[10px] mb-1"><span className="text-slate-300">{label}</span><b className="text-white">{value.toFixed(1)} MWh</b></div><div className="h-1.5 rounded-full bg-slate-900 overflow-hidden"><div className={`h-full ${color}`} style={{ width: `${clamp(value / total * 100, 0, 100)}%` }} /></div></div>;
const Status = ({ label, value, ok }: { label: string; value: string; ok: boolean }) => <div className="rounded-lg border border-cyan-950 bg-[#040d1a] px-3 py-2 flex items-center justify-between"><span className="text-slate-500">{label}</span><span className={ok ? 'text-emerald-300' : 'text-red-300'}>{value}</span></div>;
