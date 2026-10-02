import React, { useEffect, useMemo, useState } from 'react';
import {
  Wind,
  Sun,
  Building2,
  FlaskConical,
  Zap,
  BatteryCharging,
  Fuel,
  Wrench,
  Play,
  Pause,
  Compass,
  CheckCircle2,
  X,
  ExternalLink,
  ChevronRight,
  Flame,
  Sparkles,
  Lightbulb,
} from 'lucide-react';
import { StationNode } from '../types';
import { SimulationPoint } from '../integration/types';
import { useStation } from '../integration/StationContext';
import { STATION_NODES } from '../data/stationData';
import twinImage from '../assets/images/maitri_station_twin_1789652424632.jpg';
import mainBuildingPhoto from '../assets/images/maitri_main_building_1789652436746.jpg';

interface DigitalTwinProps {
  mode?: 'command' | 'energy' | 'assets' | 'simulator';
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string) => void;
  showFailureMarker?: boolean;
  failedAssetId?: string;
  onOpenAnalyticsModal?: (node: StationNode) => void;
  timelineHour?: number;
  setTimelineHour?: (hour: number) => void;
  showInspector?: boolean;
  showTimeline?: boolean;
  simulationPoint?: SimulationPoint;
}

export const DigitalTwinStation: React.FC<DigitalTwinProps> = ({
  mode = 'command',
  selectedNodeId,
  onSelectNode,
  showFailureMarker = false,
  failedAssetId = 'DG1',
  onOpenAnalyticsModal,
  timelineHour = 0,
  setTimelineHour,
  showInspector = mode === 'command',
  showTimeline = mode === 'command',
  simulationPoint,
}) => {
  const { snapshot, backendConnected } = useStation();
  const [activeNodeId, setActiveNodeId] = useState<string>(selectedNodeId || 'main-building');
  const [isPlaying, setIsPlaying] = useState(false);
  const [subTab, setSubTab] = useState<'Overview' | 'Energy' | 'Loads' | 'Environment'>('Overview');
  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [twinSettings, setTwinSettings] = useState({showFlowLines:true, showBuildingLabels:true});
  useEffect(() => { const read=()=>{ try { const v=JSON.parse(localStorage.getItem('polar_ems_settings')||'{}'); setTwinSettings({showFlowLines:v.showFlowLines!==false, showBuildingLabels:v.showBuildingLabels!==false}); } catch {} }; read(); window.addEventListener('polar-ems-settings-changed',read); return ()=>window.removeEventListener('polar-ems-settings-changed',read); }, []);

  // Command Center now uses the integrated standalone Maitri 3D twin. The parent owns
  // all operational cards; the iframe is intentionally a clean visual canvas.
  useEffect(() => {
    if (mode !== 'command') return;
    const frame = document.querySelector<HTMLIFrameElement>('[data-polar-3d-twin]');
    if (!frame) return;
    const send = () => {
      frame.contentWindow?.postMessage({
        type: 'POLAR_EMS_TELEMETRY',
        source: 'POLAR_EMS',
        mode: snapshot.mode,
        backendConnected,
        selectedHourOffset: timelineHour,
        power: {
          loadKw: snapshot.powerBalance.totalLoadKw,
          windKw: snapshot.powerBalance.windGenKw,
          solarKw: snapshot.powerBalance.solarGenKw,
          dieselKw: snapshot.powerBalance.dieselGenKw,
          batteryKw: snapshot.battery.currentPowerKw,
          renewableSharePercent: snapshot.powerBalance.renewableSharePercent,
        },
        battery: { socPercent: snapshot.battery.socPercent, status: snapshot.battery.status },
        fuel: { liters: snapshot.fuel.currentVolumeLiters, fillPercent: snapshot.fuel.fillPercent },
        weather: { temperatureC: snapshot.weather.temperature, windSpeedMs: snapshot.weather.windSpeed },
        reserve: { percent: snapshot.reserve.currentReservePercent, status: snapshot.reserve.status },
      }, '*');
    };
    if (frame.contentWindow) send();
    frame.addEventListener('load', send);
    return () => frame.removeEventListener('load', send);
  }, [mode, snapshot, timelineHour, backendConnected]);

  if (mode === 'command') {
    return (
      <div className="relative w-full h-full min-h-[560px] overflow-hidden rounded-xl bg-[#020812]" data-polar-3d-wrapper>
        <iframe
          data-polar-3d-twin
          title="Maitri Research Station 3D Digital Twin"
          src="/station-3d/polar-station-3d.html"
          className="absolute inset-0 h-full w-full border-0"
          loading="eager"
          allow="fullscreen"
        />
      </div>
    );
  }

  const activeNode = STATION_NODES.find((n) => n.id === activeNodeId) || STATION_NODES[2];
  const getLoadForNode = (nodeId: string) => {
    const aliases: Record<string, string[]> = {
      'main-building': ['L-CRITICAL', 'Critical Operations', 'Main Building'],
      'research-block': ['L-IMPORTANT', 'Research & Labs'],
      'workshop-utilities': ['L-FLEX', 'Workshop & Utilities'],
    };
    const candidates = aliases[nodeId] ?? [];
    for (const candidate of candidates) {
      const byId = snapshot.loads.find(l => l.id === candidate);
      if (byId) return byId;
      const byName = snapshot.loads.find(l => l.name.toLowerCase() === candidate.toLowerCase());
      if (byName) return byName;
    }
    return undefined;
  };
  const nodeLoad = useMemo(() => getLoadForNode(activeNode.id), [activeNode.id, snapshot.loads]);
  const nodeAsset = activeNode.id === 'wind-turbines' ? snapshot.renewables.find(r=>r.type==='Wind Turbine') : activeNode.id === 'solar-array' ? snapshot.renewables.find(r=>r.type==='Solar Array') : activeNode.id === 'diesel-generators' ? snapshot.generators[0] : undefined;
  const snapshotIsAtTimeline = (snapshot.selectedHourOffset ?? 0) === timelineHour;
  const timelinePoint = timelineHour > 0 && !snapshotIsAtTimeline ? snapshot.horizonForecast.find(p=>p.hourOffset===timelineHour) : undefined;
  const displayLoad = simulationPoint?.load_kw ?? timelinePoint?.predictedTotalLoadKw ?? snapshot.powerBalance.totalLoadKw;
  const displayWind = simulationPoint?.wind_power_kw ?? timelinePoint?.predictedWindKw ?? snapshot.powerBalance.windGenKw;
  const displaySolar = simulationPoint?.solar_power_kw ?? timelinePoint?.predictedSolarKw ?? snapshot.powerBalance.solarGenKw;
  const displayDiesel = simulationPoint?.diesel_power_kw ?? timelinePoint?.predictedDieselKw ?? snapshot.powerBalance.dieselGenKw;
  const displayBattery = simulationPoint ? 0 : (timelinePoint?.predictedBatteryKw ?? snapshot.battery.currentPowerKw);
  const displaySoc = simulationPoint?.battery_soc_percent ?? timelinePoint?.batterySocPercent ?? snapshot.battery.socPercent;
  const displayFuel = simulationPoint?.fuel_remaining_liters ?? timelinePoint?.fuelRemainingLiters ?? snapshot.fuel.currentVolumeLiters;
  const displayReserve = timelinePoint?.dynamicReserveTargetPercent ?? snapshot.reserve.currentReservePercent;
  const displayGeneration = displayWind + displaySolar + displayDiesel;
  const displayBalance = displayGeneration + displayBattery - displayLoad;
  const displayEnvironmentTemperature = simulationPoint?.indoor_temperature_celsius ?? timelinePoint?.temperatureC ?? snapshot.weather.temperature;
  const displayEnvironmentWind = timelinePoint?.windSpeedMs ?? snapshot.weather.windSpeed;
  const displayEnvironmentSolar = timelinePoint?.solarIrradianceWm2 ?? snapshot.weather.solarRadiation;
  const mappedTwinLoads = STATION_NODES.map((node) => getLoadForNode(node.id)).filter(Boolean) as NonNullable<ReturnType<typeof getLoadForNode>>[];
  const mappedTwinLoadTotal = mappedTwinLoads.reduce((sum, load) => sum + Math.max(0, load.currentLoadKw), 0);
  // Normalize the three displayed demand nodes to the authoritative station load so
  // the visual twin cannot show a sum that contradicts the KPI row.
  const loadScale = mappedTwinLoadTotal > 0 ? displayLoad / mappedTwinLoadTotal : 1;
  const displayNodeLoad = nodeLoad ? nodeLoad.currentLoadKw * loadScale : undefined;
  const nodeOutput = activeNode.id === 'battery-system' ? `${displayBattery.toFixed(1)} kW` : nodeAsset ? `${(nodeAsset.type === 'Wind Turbine' ? displayWind : nodeAsset.type === 'Solar Array' ? displaySolar : displayDiesel).toFixed(1)} kW` : nodeLoad ? `${displayNodeLoad!.toFixed(1)} kW` : activeNode.id === 'fuel-tanks' ? `${displayFuel.toFixed(0)} L` : activeNode.id === 'main-building' ? `${(displayNodeLoad ?? 0).toFixed(1)} kW` : activeNode.id === 'research-block' ? `${(displayNodeLoad ?? 0).toFixed(1)} kW` : activeNode.id === 'workshop-utilities' ? `${(displayNodeLoad ?? 0).toFixed(1)} kW` : '—';
  const nodeDisplayOutput = (nodeId: string) => {
    if (nodeId === 'diesel-generators') return `${displayDiesel.toFixed(0)} kW`;
    if (nodeId === 'wind-turbines') return `${displayWind.toFixed(0)} kW`;
    if (nodeId === 'solar-array') return `${displaySolar.toFixed(0)} kW`;
    if (nodeId === 'battery-system') return `SoC ${displaySoc.toFixed(0)}%`;
    if (nodeId === 'fuel-tanks') return `${displayFuel.toFixed(0)} L`;
    if (nodeId === 'main-building' || nodeId === 'research-block' || nodeId === 'workshop-utilities') {
      const load = getLoadForNode(nodeId);
      return load ? `${(load.currentLoadKw * loadScale).toFixed(0)} kW` : '—';
    }
    return '—';
  };

  useEffect(() => {
    if (selectedNodeId && selectedNodeId !== activeNodeId) {
      setActiveNodeId(selectedNodeId);
      setIsInspectorOpen(true);
    }
  }, [selectedNodeId, activeNodeId]);

  useEffect(() => {
    if (!isPlaying || !setTimelineHour) return;
    const offsets = timelineMilestones.map(m => m.hours);
    const timer = window.setInterval(() => {
      const idx = offsets.indexOf(timelineHour);
      setTimelineHour(idx < 0 || idx === offsets.length - 1 ? offsets[0] : offsets[idx + 1]);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [isPlaying, timelineHour, setTimelineHour]);

  const handleNodeClick = (node: StationNode) => {
    setActiveNodeId(node.id);
    setIsInspectorOpen(true);
    if (onSelectNode) onSelectNode(node.id);
  };

  const timelineMilestones = [
    { label: 'Now', hours: 0 },
    { label: '+6h', hours: 6 },
    { label: '+12h', hours: 12 },
    { label: '+24h', hours: 24 },
    { label: '+48h', hours: 48 },
    { label: '+72h', hours: 72 },
  ];

  return (
    <div className="relative w-full rounded-2xl overflow-hidden border border-cyan-900/60 bg-[#030a16] shadow-[0_10px_35px_rgba(0,0,0,0.7)] group">
      {/* Real Station Digital Twin Photographic Satellite/3D Base */}
      <div className={`relative w-full select-none overflow-hidden ${mode === 'command' ? 'command-twin-height' : 'aspect-[16/9] min-h-[430px] lg:min-h-[500px]'}`}>
        <img
          src={twinImage}
          alt="Maitri Station Digital Twin - Antarctica"
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover object-[center_55%] filter saturate-110 contrast-105 brightness-95"
        />

        {/* Ambient Polar Atmospheric Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#030914] via-transparent to-[#051124]/40 pointer-events-none"></div>
        <div className="absolute inset-0 bg-blue-950/15 pointer-events-none mix-blend-color"></div>

        {/* SVG Glowing Energy Conduits Network Layer */}
        <svg className={`absolute inset-0 w-full h-full pointer-events-none z-10 ${twinSettings.showFlowLines ? "" : "opacity-0"}`} viewBox="0 0 1000 600" preserveAspectRatio="none">
          <defs>
            <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-orange" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="glow-blue" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Pulsing Animations */}
            <linearGradient id="grad-green" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
            <linearGradient id="grad-orange" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f97316" />
              <stop offset="100%" stopColor="#fbbf24" />
            </linearGradient>
          </defs>

          {/* Diesel Generation Path -> Central Junction */}
          <path
            d="M 120 294 Q 270 300 420 250"
            fill="none"
            stroke="#f97316"
            strokeWidth="3"
            strokeDasharray="6,6"
            className={displayDiesel > 0 ? "animate-[dash_20s_linear_infinite]" : ""}
            filter="url(#glow-orange)"
            opacity={displayDiesel > 0 ? 0.9 : 0.12}
          />

          {/* Wind Turbines -> Central Junction */}
          <path
            d="M 200 150 Q 310 175 420 250"
            fill="none"
            stroke="#10b981"
            strokeWidth="3"
            strokeDasharray="8,6"
            className={displayWind > 0 ? "animate-[dash_15s_linear_infinite]" : ""}
            filter="url(#glow-green)"
            opacity={displayWind > 0 ? 0.95 : 0.12}
          />

          {/* Solar Array -> Central Junction */}
          <path
            d="M 730 222 Q 610 235 470 255"
            fill="none"
            stroke="#10b981"
            strokeWidth="2.5"
            strokeDasharray="6,6"
            filter="url(#glow-green)"
            opacity={displaySolar > 0 ? 0.85 : 0.12}
          />

          {/* Central Junction -> Battery Storage */}
          <path
            d="M 450 255 Q 450 365 450 430"
            fill="none"
            stroke="#06b6d4"
            strokeWidth="3.5"
            strokeDasharray="7,7"
            filter="url(#glow-cyan)"
            opacity={Math.abs(displayBattery) > 0.1 ? 0.9 : 0.12}
          />

          {/* Central Junction -> Main Building */}
          <path
            d="M 420 250 Q 410 225 410 210"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="3"
            filter="url(#glow-blue)"
            opacity="0.9"
          />

          {/* Central Junction -> Research Block */}
          <path
            d="M 445 250 Q 520 215 570 185"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2.5"
            filter="url(#glow-blue)"
            opacity="0.85"
          />

          {/* Central Junction -> Workshop & Utilities */}
          <path
            d="M 455 275 Q 585 335 700 350"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="2.5"
            filter="url(#glow-blue)"
            opacity="0.8"
          />

          {/* Fuel Pipe: Fuel Tanks -> Diesel Generators */}
          <path
            d="M 120 430 Q 120 355 120 294"
            fill="none"
            stroke="#64748b"
            strokeWidth="2"
            strokeDasharray="4,4"
            opacity="0.6"
          />

          {/* Thermal Loop (Visible especially in Energy mode) */}
          {mode === 'energy' && (
            <path
              d="M 205 285 Q 315 370 450 360 Q 560 350 610 330"
              fill="none"
              stroke="#ef4444"
              strokeWidth="2.5"
              strokeDasharray="5,5"
              opacity="0.85"
            />
          )}
        </svg>

        {/* Interactive Station Callout Nodes */}
        {STATION_NODES.map((node) => {
          const isSelected = activeNodeId === node.id;
          const isFailed = showFailureMarker && failedAssetId === node.id;

          let badgeColor = 'bg-cyan-950/80 border-cyan-500/50 text-cyan-200';
          let accentDot = 'bg-cyan-400';
          let icon = <Building2 className="w-3.5 h-3.5 text-cyan-400" />;

          if (node.id === 'wind-turbines') {
            badgeColor = 'bg-emerald-950/85 border-emerald-500/60 text-emerald-200';
            accentDot = 'bg-emerald-400';
            icon = <Wind className="w-3.5 h-3.5 text-emerald-400" />;
          } else if (node.id === 'solar-array') {
            badgeColor = 'bg-emerald-950/85 border-emerald-500/60 text-emerald-200';
            accentDot = 'bg-emerald-400';
            icon = <Sun className="w-3.5 h-3.5 text-emerald-400" />;
          } else if (node.id === 'diesel-generators') {
            badgeColor = 'bg-amber-950/85 border-amber-500/60 text-amber-200';
            accentDot = 'bg-amber-400';
            icon = <Zap className="w-3.5 h-3.5 text-amber-400" />;
          } else if (node.id === 'battery-system') {
            badgeColor = 'bg-cyan-950/85 border-cyan-400/60 text-cyan-200';
            accentDot = 'bg-cyan-300';
            icon = <BatteryCharging className="w-3.5 h-3.5 text-cyan-300" />;
          } else if (node.id === 'fuel-tanks') {
            badgeColor = 'bg-slate-900/90 border-slate-600/60 text-slate-200';
            accentDot = 'bg-slate-400';
            icon = <Fuel className="w-3.5 h-3.5 text-slate-300" />;
          } else if (node.id === 'research-block') {
            icon = <FlaskConical className="w-3.5 h-3.5 text-cyan-400" />;
          } else if (node.id === 'workshop-utilities') {
            icon = <Wrench className="w-3.5 h-3.5 text-cyan-400" />;
          }

          if (isFailed) {
            badgeColor = 'bg-red-950/95 border-red-500 text-red-100 shadow-[0_0_20px_rgba(239,68,68,0.7)] animate-pulse';
            accentDot = 'bg-red-500';
          }

          return (
            <div
              key={node.id}
              onClick={() => handleNodeClick(node)}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
              className={`absolute -translate-x-1/2 -translate-y-1/2 z-20 cursor-pointer transition-all duration-300 hover:scale-105 select-none ${
                isSelected ? 'scale-110 z-30' : ''
              }`}
            >
              {/* Callout Box */}
              {twinSettings.showBuildingLabels && <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border shadow-xl backdrop-blur-md transition-all ${badgeColor} ${
                  isSelected ? 'ring-2 ring-cyan-400 shadow-[0_0_20px_rgba(6,182,212,0.5)]' : ''
                }`}
              >
                <div className="p-1 rounded bg-black/40">{icon}</div>
                <div className="flex flex-col">
                  <span className="text-xs font-bold leading-tight flex items-center gap-1.5">
                    {node.name}
                    {isFailed ? (
                      <span className="text-[10px] px-1 py-0.2 rounded bg-red-600 text-white font-mono">
                        OFFLINE
                      </span>
                    ) : (
                      <ChevronRight className="w-3 h-3 text-slate-400" />
                    )}
                  </span>
                  <div className="flex items-center gap-1 text-[11px] font-mono leading-none mt-0.5">
                    {node.id === 'diesel-generators' && !isFailed ? (
                      <span>{displayDiesel.toFixed(0)} kW <span className="text-[9px] text-amber-300/80">(Backend EMS)</span></span>
                    ) : node.id === 'battery-system' ? (
                      <span>SoC {displaySoc.toFixed(0)}% <span className="text-[9px] text-cyan-300/80">{(displaySoc / 100 * snapshot.battery.capacityKwh).toFixed(0)} / {snapshot.battery.capacityKwh.toFixed(0)} kWh</span></span>
                    ) : node.id === 'fuel-tanks' ? (
                      <span>{displayFuel.toLocaleString(undefined,{maximumFractionDigits:0})} L <span className="text-[9px] text-slate-400">({(displayFuel / Math.max(1, snapshot.fuel.capacityLiters) * 100).toFixed(0)}%)</span></span>
                    ) : isFailed ? (
                      <span className="text-red-300 font-bold">DG1 Trip (Simulated)</span>
                    ) : node.id === 'wind-turbines' ? (
                      <span>{displayWind.toFixed(0)} kW</span>
                    ) : node.id === 'solar-array' ? (
                      <span>{displaySolar.toFixed(0)} kW</span>
                    ) : node.id === 'main-building' || node.id === 'research-block' || node.id === 'workshop-utilities' ? (
                      <span>{nodeDisplayOutput(node.id)}</span>
                    ) : (
                      <span>{nodeDisplayOutput(node.id)}</span>
                    )}
                  </div>
                </div>
              </div>}

              {/* Anchor Pin & Pulsing Dot */}
              <div className="flex flex-col items-center mt-1">
                <div className={`w-2.5 h-2.5 rounded-full ${accentDot} ring-4 ring-black/60 shadow-md ${isSelected ? 'animate-bounce' : ''}`}></div>
                <div className="w-0.5 h-3 bg-gradient-to-b from-cyan-400 to-transparent"></div>
              </div>
            </div>
          );
        })}

        {/* Compass Widget in Top Right of Digital Twin */}
        <div className="absolute top-4 right-4 z-20 hidden sm:flex items-center justify-center w-11 h-11 rounded-full bg-[#040d1a]/85 border border-cyan-800/60 backdrop-blur shadow-lg">
          <div className="relative w-full h-full flex items-center justify-center font-mono text-[9px] font-bold text-cyan-400">
            <span className="absolute top-0.5 text-cyan-300">N</span>
            <span className="absolute bottom-0.5 text-slate-500">S</span>
            <span className="absolute left-1 text-slate-500">W</span>
            <span className="absolute right-1 text-slate-500">E</span>
            <Compass className="w-4 h-4 text-cyan-500/60" />
          </div>
        </div>

        {/* Map Energy Flow Legend (Bottom Left) */}
        <div className="absolute bottom-4 left-4 z-20 bg-[#040d1d]/85 border border-cyan-900/70 backdrop-blur-md rounded-xl px-3.5 py-2 shadow-xl flex items-center gap-3 text-xs">
          <span className="text-slate-400 font-medium text-[11px] hidden sm:inline">Energy Flow</span>
          <div className="flex items-center gap-3 font-mono text-[11px]">
            <span className="flex items-center gap-1.5 text-slate-200">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-500 shadow-[0_0_6px_#f97316]"></span>
              Diesel
            </span>
            <span className="flex items-center gap-1.5 text-slate-200">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]"></span>
              Renewable
            </span>
            <span className="flex items-center gap-1.5 text-slate-200">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#06b6d4]"></span>
              Battery
            </span>
            <span className="flex items-center gap-1.5 text-slate-200">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-400 shadow-[0_0_6px_#38bdf8]"></span>
              Load
            </span>
            {mode === 'energy' && (
              <span className="flex items-center gap-1.5 text-slate-200">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-[0_0_6px_#ef4444]"></span>
                Thermal
              </span>
            )}
          </div>
        </div>

        {/* Interactive Timeline Scrubber (Bottom Right) */}
        {showTimeline && <div className="absolute bottom-4 right-4 z-20 bg-[#040d1d]/90 border border-cyan-900/70 backdrop-blur-md rounded-xl px-3.5 py-2 shadow-xl flex items-center gap-3">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="w-8 h-8 rounded-full bg-cyan-600 hover:bg-cyan-500 text-black flex items-center justify-center shadow-lg shadow-cyan-600/30 transition-all cursor-pointer"
            title={isPlaying ? 'Pause simulation' : 'Play timeline prediction'}
          >
            {isPlaying ? <Pause className="w-4 h-4 fill-black" /> : <Play className="w-4 h-4 fill-black ml-0.5" />}
          </button>
          <div className="flex items-center gap-2 sm:gap-4 font-mono text-[11px]">
            {timelineMilestones.map((m) => {
              const active = timelineHour === m.hours;
              return (
                <button
                  key={m.hours}
                  onClick={() => {
                    if (setTimelineHour) setTimelineHour(m.hours);
                  }}
                  className={`px-2 py-0.5 rounded transition-all ${
                    active
                      ? 'bg-cyan-500 text-black font-bold shadow-[0_0_8px_#06b6d4]'
                      : 'text-slate-400 hover:text-cyan-300'
                  }`}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>}

        {/* Floating Asset Inspect Drawer / Card (Top-Right on Digital Twin) */}
        {showInspector && isInspectorOpen && activeNode && (
          <div className="absolute top-[24%] right-3 z-30 w-72 sm:w-80 bg-[#061224]/95 border border-cyan-600/50 rounded-xl shadow-2xl backdrop-blur-md overflow-hidden text-slate-200 animate-in fade-in slide-in-from-right-3 duration-200">
            {/* Header */}
            <div className="px-4 py-2.5 bg-cyan-950/60 border-b border-cyan-800/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-cyan-400" />
                <span className="font-bold text-sm tracking-wide text-white font-sans">
                  {activeNode.name}
                </span>
              </div>
              <button
                onClick={() => setIsInspectorOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Sub Tabs: Overview, Energy, Loads, Environment */}
            <div className="px-3 pt-2 flex items-center gap-1 border-b border-cyan-900/40 bg-black/20 text-xs">
              {(['Overview', 'Energy', 'Loads', 'Environment'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setSubTab(tab)}
                  className={`px-2.5 py-1 rounded-t font-medium transition-all ${
                    subTab === tab
                      ? 'bg-cyan-600 text-black font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Content Body with Real Station Photography */}
            <div className="p-3.5 space-y-3 text-xs">
              {/* Real Photograph of the station module */}
              <div className="relative w-full h-28 rounded-lg overflow-hidden border border-cyan-900/60 shadow-inner">
                <img
                  src={mainBuildingPhoto}
                  alt="Real Maitri Station Research Module"
                  referrerPolicy="no-referrer"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-1.5 left-2 px-1.5 py-0.5 rounded bg-black/75 text-[10px] text-cyan-300 font-mono">
                  Maitri Station Module
                </div>
              </div>

              {/* Contextual inspector content changes with the selected sub-tab */}
              <div className="space-y-1.5 font-mono text-xs divide-y divide-cyan-950/60">
                {subTab === 'Overview' && <><div className="flex justify-between pt-1"><span className="text-slate-400 font-sans">Status</span><span className="font-bold text-emerald-300">{nodeAsset?.status ?? (nodeLoad ? 'SERVING' : activeNode.status)}</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Current value</span><span className="font-bold text-cyan-300">{nodeOutput}</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Criticality</span><span className="text-amber-300">{nodeLoad?.priority ?? activeNode.criticality ?? 'SYSTEM'}</span></div></>}
                {subTab === 'Energy' && <><div className="flex justify-between pt-1"><span className="text-slate-400 font-sans">Power</span><span className="font-bold text-cyan-300">{nodeOutput}</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Station generation</span><span className="text-white">{displayGeneration.toFixed(1)} kW</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Net balance</span><span className={displayBalance >= 0 ? 'text-emerald-300' : 'text-red-300'}>{displayBalance.toFixed(1)} kW</span></div></>}
                {subTab === 'Loads' && <><div className="flex justify-between pt-1"><span className="text-slate-400 font-sans">Current load</span><span className="font-bold text-cyan-300">{displayNodeLoad?.toFixed(1) ?? '—'} kW</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Peak load</span><span className="text-white">{nodeLoad?.peakLoadKw.toFixed(1) ?? '—'} kW</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Service</span><span className="text-emerald-300">{nodeLoad?.shedStatus ?? 'N/A'}</span></div></>}
                {subTab === 'Environment' && <><div className="flex justify-between pt-1"><span className="text-slate-400 font-sans">Outdoor</span><span className="text-white">{displayEnvironmentTemperature.toFixed(1)} °C</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Wind</span><span className="text-white">{displayEnvironmentWind.toFixed(1)} m/s</span></div><div className="flex justify-between pt-1.5"><span className="text-slate-400 font-sans">Solar</span><span className="text-white">{displayEnvironmentSolar.toFixed(0)} W/m²</span></div></>}
              </div>

              {/* Action Button */}
              <button
                onClick={() => onOpenAnalyticsModal && onOpenAnalyticsModal(activeNode)}
                className="w-full mt-2 py-2 rounded-lg bg-cyan-900/60 hover:bg-cyan-800/80 border border-cyan-500/50 text-cyan-200 font-semibold text-xs flex items-center justify-center gap-1.5 shadow-md transition-all cursor-pointer"
              >
                <span>View Detailed Analytics</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
