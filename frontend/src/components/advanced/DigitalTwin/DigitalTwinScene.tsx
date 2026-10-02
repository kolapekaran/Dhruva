import React, { useState } from 'react';
import { useStation } from '../../../integration/StationContext';
import { AssetInspector } from './AssetInspector';
import {
  Play,
  Pause,
  Wind,
  Sun,
  Flame,
  BatteryCharging,
  Zap,
  Building,
  FlaskConical,
  Wrench,
  Fuel,
  Compass,
  ArrowRight,
  TrendingUp,
  Lightbulb,
  CloudSnow,
  Droplets,
  Search,
  Calendar,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';

export const DigitalTwinScene: React.FC = () => {
  const {
    snapshot,
    timeOffset,
    setTimeOffset,
    isPlayingTimeline,
    setIsPlayingTimeline,
    setSelectedAssetId,
    setActiveTab,
    systemMode,
    setSystemMode,
  } = useStation();

  // Default to MAIN building open, exactly as in screenshot 1
  const [activeAsset, setActiveAsset] = useState<string | null>('MAIN');

  // Timeline scrubber steps
  const timelineSteps = [
    { label: 'Now', offset: 0 },
    { label: '+6h', offset: 6 },
    { label: '+12h', offset: 12 },
    { label: '+24h', offset: 24 },
    { label: '+48h', offset: 48 },
    { label: '+72h', offset: 72 },
  ];

  const hourPoint = snapshot.horizonForecast.find((p) => p.hourOffset === timeOffset) ?? snapshot.horizonForecast[0];
  const displayLoad = hourPoint?.predictedTotalLoadKw ?? snapshot.powerBalance.totalLoadKw;
  const displayWind = hourPoint?.predictedWindKw ?? snapshot.powerBalance.windGenKw;
  const displaySolar = hourPoint?.predictedSolarKw ?? snapshot.powerBalance.solarGenKw;
  const displayDiesel = hourPoint?.predictedDieselKw ?? snapshot.powerBalance.dieselGenKw;
  const displayBattery = hourPoint?.predictedBatteryKw ?? snapshot.battery.currentPowerKw;
  const displaySoc = hourPoint?.batterySocPercent ?? snapshot.battery.socPercent;
  const displayFuel = hourPoint?.fuelRemainingLiters ?? snapshot.fuel.currentVolumeLiters;
  const displayReserve = hourPoint?.dynamicReserveTargetPercent ?? snapshot.reserve.currentReservePercent;
  const displayGeneration = displayWind + displaySolar + displayDiesel;
  const displayBalance = displayGeneration + displayBattery - displayLoad;

  const handleAssetClick = (id: string) => {
    setActiveAsset(id);
    setSelectedAssetId(id);
  };

  // Use the same backend horizon series as the primary Digital Twin.
  const liveChartData = snapshot.horizonForecast.map((p) => ({
    time: `+${p.hourOffset}h`,
    load: p.predictedTotalLoadKw,
    generation: p.predictedWindKw + p.predictedSolarKw + p.predictedDieselKw,
    solar: p.predictedSolarKw,
    wind: p.predictedWindKw,
  }));

  return (
    <div className="flex flex-col flex-1 bg-[#050b16] text-slate-100 overflow-hidden relative select-none font-mono">
      {/* 2.5D Digital Twin Main Stage Canvas */}
      <div className="relative w-full h-[540px] lg:h-[580px] bg-gradient-to-b from-[#09152b] via-[#0b1b36] to-[#081223] overflow-hidden border-b border-cyan-950">
        {/* Antarctic Snowy Terrain & Mountain Backdrop */}
        <div className="absolute inset-0 pointer-events-none opacity-90">
          <svg className="w-full h-full" viewBox="0 0 1200 600" preserveAspectRatio="none">
            <defs>
              <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#040a17" />
                <stop offset="50%" stopColor="#081836" />
                <stop offset="100%" stopColor="#122d56" />
              </linearGradient>
              <linearGradient id="snowGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#1e3a6a" />
                <stop offset="40%" stopColor="#152b50" />
                <stop offset="100%" stopColor="#0c1830" />
              </linearGradient>
              <radialGradient id="aurora" cx="50%" cy="20%" r="60%">
                <stop offset="0%" stopColor="rgba(6, 182, 212, 0.18)" />
                <stop offset="50%" stopColor="rgba(16, 185, 129, 0.08)" />
                <stop offset="100%" stopColor="transparent" />
              </radialGradient>
            </defs>

            {/* Aurora and Sky */}
            <rect width="1200" height="600" fill="url(#skyGrad)" />
            <rect width="1200" height="300" fill="url(#aurora)" />

            {/* Distant Mountain Peaks */}
            <polygon points="0,220 180,120 340,240 520,110 700,230 920,95 1100,210 1200,160 1200,600 0,600" fill="#0c1d38" opacity="0.8" />
            <polygon points="0,270 240,180 480,290 740,160 980,280 1200,210 1200,600 0,600" fill="#11274d" opacity="0.9" />

            {/* Schirmacher Oasis Ground Ice Sheet */}
            <polygon points="0,320 350,300 700,315 1200,295 1200,600 0,600" fill="url(#snowGrad)" />

            {/* Flowing Energy Conduit Lines */}
            {/* Renewable Flow (Green) from Wind & Solar */}
            <path d="M 330 180 Q 420 220 540 270" stroke="#10b981" strokeWidth="2.5" fill="none" className="animate-flow-dash" opacity="0.85" />
            <path d="M 820 200 Q 720 230 540 270" stroke="#10b981" strokeWidth="2.5" fill="none" className="animate-flow-dash" opacity="0.85" />

            {/* Diesel Flow (Amber) from DG to Distribution */}
            <path d="M 210 260 Q 380 270 540 270" stroke="#f59e0b" strokeWidth="2.5" fill="none" className="animate-flow-dash" opacity="0.85" />

            {/* Battery Flow (Cyan) */}
            <path d="M 580 340 Q 560 300 540 270" stroke="#06b6d4" strokeWidth="2.5" fill="none" className="animate-flow-dash" opacity="0.9" />

            {/* Distribution Grid (Blue) */}
            <path d="M 540 270 Q 460 210 430 190" stroke="#3b82f6" strokeWidth="2.5" fill="none" className="animate-flow-dash" opacity="0.85" />
            <path d="M 540 270 Q 600 205 640 185" stroke="#3b82f6" strokeWidth="2.5" fill="none" className="animate-flow-dash" opacity="0.85" />
            <path d="M 540 270 Q 720 290 770 330" stroke="#8b5cf6" strokeWidth="2" fill="none" className="animate-flow-dash" opacity="0.75" />
          </svg>
        </div>

        {/* TOP FLOATING BAR OVER TWIN: Weather, Center Creed, Search & Controls */}
        <div className="absolute top-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-3 pointer-events-auto">
          {/* Weather Widget (Top Left) */}
          <div className="flex items-center gap-3 bg-[#061021]/85 backdrop-blur-md border border-slate-800/80 px-3.5 py-2 rounded-2xl shadow-lg">
            <div className="flex items-center gap-2">
              <CloudSnow className="w-6 h-6 text-cyan-300" />
              <div>
                <div className="text-xl font-bold text-white leading-none">{snapshot.weather.temperature.toFixed(0)}°C</div>
                <div className="text-[10px] text-slate-400 font-sans mt-0.5">{snapshot.weather.condition}</div>
              </div>
            </div>
            <div className="h-7 w-[1px] bg-slate-800 mx-1" />
            <div className="flex flex-col text-[10px] text-slate-400 gap-0.5 font-sans">
              <div className="flex items-center gap-1.5">
                <Wind className="w-3 h-3 text-cyan-400" />
                <span>Wind <strong className="text-slate-200 font-mono">{snapshot.weather.windSpeed.toFixed(1)} m/s ({snapshot.weather.windDirection})</strong></span>
              </div>
              <div className="flex items-center gap-1.5">
                <Compass className="w-3 h-3 text-indigo-400" />
                <span>Visibility <strong className="text-slate-200 font-mono">{snapshot.weather.provenance === 'ENGINEERING MODEL' ? '—' : `${snapshot.weather.visibilityKm.toFixed(1)} km`}</strong></span>
              </div>
              <div className="flex items-center gap-1.5">
                <Droplets className="w-3 h-3 text-blue-400" />
                <span>Humidity <strong className="text-slate-200 font-mono">{snapshot.weather.provenance === 'ENGINEERING MODEL' ? '—' : `${snapshot.weather.humidity.toFixed(0)}%`}</strong></span>
              </div>
            </div>
          </div>

          {/* Center Polar Creed */}
          <div className="hidden lg:block text-xs tracking-[0.25em] text-cyan-400/50 uppercase select-none font-semibold">
            CLEAN ENERGY. RESILIENT TOMORROW.
          </div>

          {/* Right Controls: Search, Mode, Compass */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search anything on station..."
                className="bg-[#061021]/90 border border-slate-800 rounded-xl pl-8.5 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-56 transition-all shadow-md"
              />
            </div>

            <div className="flex items-center bg-[#070f1e] p-0.5 rounded-xl border border-slate-800 text-xs font-semibold">
              <button
                onClick={() => setSystemMode('ONLINE')}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  systemMode === 'ONLINE'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Live
              </button>
              <button
                onClick={() => setSystemMode('SIMULATION')}
                className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                  systemMode === 'SIMULATION'
                    ? 'bg-amber-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Simulation
              </button>
            </div>

            {/* Compass Rose */}
            <div className="w-8 h-8 rounded-full bg-[#061021]/90 border border-slate-800 flex items-center justify-center text-[9px] font-bold text-slate-400 relative">
              <span className="absolute top-0.5 text-cyan-400">N</span>
              <span className="absolute bottom-0.5 text-slate-500">S</span>
              <span className="absolute left-0.5 text-slate-500">W</span>
              <span className="absolute right-0.5 text-slate-500">E</span>
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
            </div>
          </div>
        </div>

        {/* Station Asset Badges (Interactive 3D Coordinates) */}
        <div className="absolute inset-0 pointer-events-auto">
          {/* Wind Turbines */}
          <button
            onClick={() => handleAssetClick('WIND')}
            className="absolute top-[22%] left-[27%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-emerald-500/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Wind className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Wind Turbines</span>
                <span className="text-emerald-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{displayWind.toFixed(0)} kW</div>
            </div>
          </button>

          {/* Solar Array */}
          <button
            onClick={() => handleAssetClick('SOLAR')}
            className="absolute top-[24%] left-[69%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-emerald-500/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Sun className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Solar Array</span>
                <span className="text-emerald-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{displaySolar.toFixed(0)} kW</div>
            </div>
          </button>

          {/* Main Building */}
          <button
            onClick={() => handleAssetClick('MAIN')}
            className="absolute top-[27%] left-[44%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-cyan-500/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Building className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Main Building</span>
                <span className="text-cyan-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{(snapshot.loads.find(l => l.id === 'L-CRITICAL')?.currentLoadKw ?? 0).toFixed(0)} kW</div>
            </div>
          </button>

          {/* Research Block */}
          <button
            onClick={() => handleAssetClick('RESEARCH')}
            className="absolute top-[26%] left-[58%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-cyan-500/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400">
              <FlaskConical className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Research Block</span>
                <span className="text-cyan-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{(snapshot.loads.find(l => l.id === 'L-IMPORTANT')?.currentLoadKw ?? snapshot.loads.find(l => l.name === 'Research & Labs')?.currentLoadKw ?? 0).toFixed(0)} kW</div>
            </div>
          </button>

          {/* Diesel Generators */}
          <button
            onClick={() => handleAssetClick('DG')}
            className="absolute top-[43%] left-[17%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-amber-500/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-amber-500/20 flex items-center justify-center text-amber-400">
              <Flame className="w-3.5 h-3.5 animate-pulse" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Diesel Generators</span>
                <span className="text-amber-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{displayDiesel.toFixed(0)} kW</div>
              <div className="text-[9px] text-amber-300/80 font-mono">({snapshot.generators.filter(g => g.status === 'ONLINE').length} Online | {snapshot.generators.filter(g => g.status === 'STANDBY').length} Standby)</div>
            </div>
          </button>

          {/* Fuel Tanks */}
          <button
            onClick={() => handleAssetClick('FUEL')}
            className="absolute top-[61%] left-[18%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-cyan-700/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300">
              <Fuel className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Fuel Tanks</span>
                <span className="text-slate-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{displayFuel.toLocaleString(undefined,{maximumFractionDigits:0})} L</div>
              <div className="text-[9px] text-slate-400 font-mono">({snapshot.fuel.fillPercent.toFixed(0)}%)</div>
            </div>
          </button>

          {/* Battery System */}
          <button
            onClick={() => handleAssetClick('BATTERY')}
            className="absolute top-[59%] left-[51%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-emerald-500/60 px-3.5 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400">
              <BatteryCharging className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Battery System</span>
                <span className="text-emerald-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">SoC {displaySoc.toFixed(0)}%</div>
              <div className="text-[9px] text-emerald-300 font-mono">{(displaySoc * snapshot.battery.capacityKwh / 100).toFixed(0)} / {snapshot.battery.capacityKwh.toFixed(0)} kWh</div>
            </div>
          </button>

          {/* Workshop & Utilities */}
          <button
            onClick={() => handleAssetClick('WORKSHOP')}
            className="absolute top-[55%] left-[73%] -translate-x-1/2 flex items-center gap-2 bg-[#08172c]/90 hover:bg-[#0c2242] border border-cyan-600/60 px-3 py-1.5 rounded-xl shadow-lg text-left transition-all group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400">
              <Wrench className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 flex items-center gap-1">
                <span>Workshop & Utilities</span>
                <span className="text-blue-400">›</span>
              </div>
              <div className="text-sm font-bold text-white font-mono">{(snapshot.loads.find(l => l.id === 'L-FLEX')?.currentLoadKw ?? 0).toFixed(0)} kW</div>
            </div>
          </button>
        </div>

        {/* Inspector Overlay Card (Matches right side drawer of screenshot 1) */}
        {activeAsset && (
          <AssetInspector
            assetId={activeAsset}
            onClose={() => setActiveAsset(null)}
          />
        )}

        {/* Bottom Left Legend: Energy Flow */}
        <div className="absolute bottom-4 left-4 z-20 flex items-center gap-3 bg-[#061021]/90 backdrop-blur-md border border-slate-800 px-3.5 py-1.5 rounded-xl text-xs font-mono">
          <span className="text-slate-400 font-semibold text-[11px]">Energy Flow</span>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1.5 rounded-full bg-amber-500" />
            <span className="text-slate-300 text-[11px]">Diesel</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-slate-300 text-[11px]">Renewable</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1.5 rounded-full bg-cyan-400" />
            <span className="text-slate-300 text-[11px]">Battery</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1.5 rounded-full bg-blue-300" />
            <span className="text-slate-300 text-[11px]">Load</span>
          </div>
        </div>

        {/* Bottom Right Timeline Scrubber */}
        <div className="absolute bottom-4 right-4 z-20 flex items-center gap-3 bg-[#061021]/90 backdrop-blur-md border border-cyan-900/60 px-4 py-2 rounded-2xl shadow-xl">
          <button
            onClick={() => setIsPlayingTimeline(!isPlayingTimeline)}
            className="w-8 h-8 rounded-full bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center shadow-md shadow-cyan-900 transition-all cursor-pointer"
          >
            {isPlayingTimeline ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>

          <div className="flex items-center gap-1 font-mono text-xs">
            {timelineSteps.map((step) => {
              const isActive = timeOffset === step.offset;
              return (
                <button
                  key={step.offset}
                  onClick={() => setTimeOffset(step.offset)}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    isActive
                      ? 'bg-cyan-600 text-white font-bold shadow-sm'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  {step.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 5 Bottom Mission-Control KPI Cards (Exactly as in Screenshot 1) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 p-4 bg-[#050b16] font-mono">
        {/* Card 1: Generation vs Load (Live) */}
        <div className="bg-[#081224] border border-cyan-950/80 rounded-2xl p-4 flex flex-col justify-between shadow-lg">
          <div>
            <span className="text-xs text-slate-300 font-semibold flex items-center gap-1.5 mb-2">
              <span>Generation vs Load</span>
              <span className="text-[10px] text-cyan-400">({timeOffset === 0 ? 'Current' : `+${timeOffset}h Forecast`})</span>
            </span>

            <div className="grid grid-cols-3 gap-1 mb-2">
              <div>
                <span className="text-[9px] text-slate-400 block">Total Generation</span>
                <span className="text-sm font-bold text-white">{displayGeneration.toFixed(0)} kW</span>
              </div>
              <div>
                <span className="text-[9px] text-slate-400 block">Total Load</span>
                <span className="text-sm font-bold text-white">{displayLoad.toFixed(0)} kW</span>
              </div>
              <div>
                <span className="text-[9px] text-slate-400 block">Balance</span>
                <span className="text-sm font-bold text-emerald-400">{displayBalance >= 0 ? '+' : ''}{displayBalance.toFixed(0)} kW</span>
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-2 text-[9px] text-slate-400 mb-1">
              <span className="flex items-center gap-1"><span className="w-2 h-1 bg-blue-500 rounded" />Load</span>
              <span className="flex items-center gap-1"><span className="w-2 h-1 bg-cyan-400 rounded" />Generation</span>
              <span className="flex items-center gap-1"><span className="w-2 h-1 bg-amber-400 rounded" />Solar</span>
              <span className="flex items-center gap-1"><span className="w-2 h-1 bg-emerald-400 rounded" />Wind</span>
            </div>
          </div>

          {/* Line Chart */}
          <div className="h-20 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={liveChartData}>
                <XAxis dataKey="time" stroke="#475569" fontSize={8} tickLine={false} />
                <YAxis stroke="#475569" fontSize={8} domain={[0, 300]} ticks={[0, 100, 200, 300]} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#071224', fontSize: '10px' }} />
                <Line type="monotone" dataKey="load" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="generation" stroke="#06b6d4" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="wind" stroke="#10b981" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Card 2: Battery State of Charge */}
        <div className="bg-[#081224] border border-cyan-950/80 rounded-2xl p-4 flex flex-col justify-between shadow-lg">
          <span className="text-xs text-slate-300 font-semibold">Battery State of Charge</span>

          <div className="flex items-center justify-around my-1">
            {/* Donut Gauge */}
            <div className="relative w-20 h-20 flex items-center justify-center">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#162947"
                  strokeWidth="3.5"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="3.5"
                  strokeDasharray={`${Math.max(0, Math.min(100, displaySoc))}, 100`}
                />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-base font-bold text-white">{displaySoc.toFixed(0)}%</span>
                <span className="text-[9px] text-slate-400">SoC</span>
              </div>
            </div>

            <div className="space-y-1 text-right">
              <div>
                <span className="text-[10px] text-slate-400 block">Available Energy</span>
                <span className="text-xs font-bold text-white">{snapshot.battery.currentChargeKwh.toFixed(0)} kWh</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">Total Capacity</span>
                <span className="text-xs text-slate-300">{snapshot.battery.capacityKwh.toFixed(0)} kWh</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">Status</span>
                <span className="text-[10px] text-emerald-400 font-semibold flex items-center justify-end gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>{snapshot.battery.status}</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Fuel Level */}
        <div className="bg-[#081224] border border-cyan-950/80 rounded-2xl p-4 flex flex-col justify-between shadow-lg">
          <span className="text-xs text-slate-300 font-semibold">Fuel Level</span>

          <div className="my-1">
            <div className="flex items-center gap-2 mb-1">
              <Fuel className="w-4 h-4 text-amber-500" />
              <div>
                <span className="text-sm font-bold text-white">{displayFuel.toLocaleString(undefined,{maximumFractionDigits:0})} L</span>
                <span className="text-slate-400 text-[10px] ml-1">of {snapshot.fuel.capacityLiters.toFixed(0)} L ({snapshot.fuel.fillPercent.toFixed(0)}%)</span>
              </div>
            </div>

            {/* Segmented Fuel Bar */}
            <div className="grid grid-cols-10 gap-1 h-3.5 my-2">
              {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                <div key={i} className="rounded-xs bg-emerald-500" />
              ))}
              {[9, 10].map((i) => (
                <div key={i} className="rounded-xs bg-slate-800" />
              ))}
            </div>

            <div className="flex items-center gap-2 text-[10px] text-slate-400 pt-1">
              <Calendar className="w-3.5 h-3.5 text-slate-500" />
              <div>
                <span className="block text-[9px]">Estimated Autonomy</span>
                <span className="font-bold text-white text-xs">{snapshot.fuel.estimatedAutonomyDays != null ? snapshot.fuel.estimatedAutonomyDays.toFixed(1) : '—'} days</span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 4: Dynamic Reserve */}
        <div className="bg-[#081224] border border-cyan-950/80 rounded-2xl p-4 flex flex-col justify-between shadow-lg">
          <span className="text-xs text-slate-300 font-semibold">Dynamic Reserve</span>

          <div className="flex items-center justify-around my-1">
            <div className="relative w-20 h-20 flex items-center justify-center">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#162947"
                  strokeWidth="3.5"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="3.5"
                  strokeDasharray={`${Math.max(0, Math.min(100, displayReserve))}, 100`}
                />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-base font-bold text-white">{displayReserve.toFixed(0)}%</span>
              </div>
            </div>

            <div className="space-y-1 text-right text-xs">
              <span className="text-[11px] text-cyan-400 font-semibold block">Target ≥ {snapshot.reserve.targetReservePercent.toFixed(0)}%</span>
              <div className="flex items-center justify-end gap-1 text-[11px] text-emerald-400 font-semibold">
                <span className="w-2 h-2 rounded-full border border-emerald-400 flex items-center justify-center">
                  <span className="w-1 h-1 rounded-full bg-emerald-400" />
                </span>
                <span>Adequate</span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 5: Top AI Recommendation */}
        <div className="bg-[#081224] border border-cyan-950/80 rounded-2xl p-4 flex flex-col justify-between shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300 font-semibold">Top AI Recommendation</span>
            <span className="px-2 py-0.5 rounded border border-amber-600/70 text-[9px] font-bold text-amber-400 uppercase tracking-wide">
              MEDIUM
            </span>
          </div>

          <div className="my-1 flex items-start gap-2">
            <div className="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 shrink-0 mt-0.5">
              <Lightbulb className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="font-bold text-white text-xs block leading-tight">
                {snapshot.topRecommendation.title}
              </span>
              <p className="text-[10px] text-slate-400 font-sans line-clamp-2 mt-1 leading-snug">
                {snapshot.topRecommendation.description}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => setActiveTab('simulator')}
              className="flex-1 py-1.5 rounded-lg bg-[#061021] hover:bg-slate-800 border border-slate-700 text-slate-200 text-[11px] font-bold transition-all cursor-pointer"
            >
              Simulate
            </button>
            <button
              onClick={() => setActiveTab('optimization')}
              className="flex-1 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-[11px] font-bold transition-all cursor-pointer"
            >
              View Details
            </button>
          </div>
        </div>
      </div>

      {/* Persistent Footer */}
      <footer className="flex flex-wrap items-center justify-between px-4 lg:px-6 py-2 bg-[#040813] border-t border-cyan-950/80 text-[11px] text-slate-400 font-mono">
        <div className="flex items-center gap-2">
          {/* Indian Tricolor Flag indicator */}
          <div className="w-4 h-3 rounded-[2px] overflow-hidden flex flex-col border border-slate-700">
            <div className="h-1 bg-[#ff9933]" />
            <div className="h-1 bg-white flex items-center justify-center">
              <div className="w-0.5 h-0.5 rounded-full bg-[#000080]" />
            </div>
            <div className="h-1 bg-[#138808]" />
          </div>
          <span className="text-slate-300 font-semibold">Indian Antarctic Programme</span>
        </div>

        <div className="text-center text-slate-400 hidden sm:block">
          Maitri Station, Antarctica | 70.8° S, 11.7° E
        </div>

        <div className="text-right text-slate-400">
          <span>DHRUVA v1.0</span>
          <span className="mx-2 text-slate-600">|</span>
          <span className="text-slate-300">Clean Energy. Resilient Tomorrow.</span>
        </div>
      </footer>
    </div>
  );
};
