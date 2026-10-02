import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BatteryCharging,
  CheckCircle2,
  ChevronRight,
  CloudSnow,
  Fuel,
  Gauge,
  Radio,
  Shield,
  ShieldAlert,
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
import { useStation } from '../../integration/StationContext';
import {
  fetchStationRisk,
  simulateFailureScenario,
  reevaluateStationResilience,
  fetchFuelLogisticsIntelligence,
} from '../../integration/api';
import type { ResilienceScenarioResult, StationRiskAssessment } from '../../integration/types';

const riskClass = (level: string) => {
  if (level === 'HIGH' || level === 'CRITICAL') return 'text-red-300 border-red-500/40 bg-red-950/30';
  if (level === 'MEDIUM') return 'text-amber-300 border-amber-500/40 bg-amber-950/30';
  return 'text-emerald-300 border-emerald-500/40 bg-emerald-950/30';
};

const severityDot = (level: string) => level === 'HIGH' ? 'bg-red-400' : level === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400';

export const ResilienceTab: React.FC = () => {
  const { resilience, snapshot, refreshResilience, refreshSnapshot, resilienceLoading, resilienceError, systemMode, simulationTrajectory } = useStation();
  const [risk, setRisk] = useState<StationRiskAssessment | null>(null);
  const [scenarioKey, setScenarioKey] = useState('EXTREME_COLD');
  const [scenario, setScenario] = useState<ResilienceScenarioResult | null>(null);
  const [running, setRunning] = useState(false);
  const [riskMode, setRiskMode] = useState(true);
  const [fuelPlan, setFuelPlan] = useState<Awaited<ReturnType<typeof fetchFuelLogisticsIntelligence>> | null>(null);
  const [fuelPlanLoading, setFuelPlanLoading] = useState(false);
  const [showAllThreats, setShowAllThreats] = useState(false);
  const [strategy, setStrategy] = useState({
    loadShedding: true,
    renewablePriority: true,
    batteryReserve: true,
    fuelConservation: true,
    alternateRouting: true,
    emergencyComms: true,
  });

  useEffect(() => {
    if (systemMode === 'SIMULATION') return;
    let cancelled = false;
    setFuelPlanLoading(true);
    void fetchFuelLogisticsIntelligence(72, 72).then(result => {
      if (!cancelled) setFuelPlan(result);
    }).catch(() => {
      if (!cancelled) setFuelPlan(null);
    }).finally(() => {
      if (!cancelled) setFuelPlanLoading(false);
    });
    void fetchStationRisk(72).then(result => {
      if (!cancelled) setRisk(result);
    }).catch(() => {
      if (!cancelled) setRisk(null);
    });
    return () => { cancelled = true; };
  }, [resilience, snapshot.systemTime, systemMode]);

  const simulationRisk = useMemo(() => {
    if (systemMode !== 'SIMULATION' || !simulationTrajectory.length) return null;
    const maxWeather = Math.max(...simulationTrajectory.map(p => (p.outdoor_temperature_celsius ?? 0) <= -35 || (p.wind_speed_mps ?? 0) >= 20 ? 100 : 0));
    const minSoc = Math.min(...simulationTrajectory.map(p => Number(p.battery_soc_percent ?? 100)));
    const minFuel = Math.min(...simulationTrajectory.map(p => Number(p.fuel_remaining_liters ?? snapshot.fuel.currentVolumeLiters)));
    const reserve = snapshot.fuel.emergencyReserveLiters;
    const batteryRisk = Math.max(0, Math.min(100, (25 - minSoc) / 25 * 100));
    const fuelRisk = Math.max(0, Math.min(100, (reserve - minFuel) / Math.max(1, reserve) * 100));
    const criticalRisk = Math.max(...simulationTrajectory.map(p => {
      const load = Math.max(1, Number(p.load_kw ?? 0));
      const shed = Math.max(0, Number(p.shed_load_kw ?? 0));
      return Math.min(100, shed / load * 100);
    }));
    // This is a transparent scenario risk index, not a calibrated probability.
    const overall = Math.max(0, Math.min(100, 0.30 * maxWeather + 0.25 * batteryRisk + 0.20 * fuelRisk + 0.25 * criticalRisk));
    const level = overall >= 70 ? 'CRITICAL' : overall >= 40 ? 'HIGH' : overall >= 20 ? 'MEDIUM' : 'LOW';
    return { overallRiskPercent: overall, riskLevel: level as 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL', components: { extremeWeatherRiskPercent: maxWeather, batterySocRiskPercent: batteryRisk, fuelReserveRiskPercent: fuelRisk, criticalLoadRiskPercent: criticalRisk } };
  }, [systemMode, simulationTrajectory, snapshot.fuel.emergencyReserveLiters, snapshot.fuel.currentVolumeLiters]);

  // Keep the numeric risk index authoritative; threat severity is intentionally
  // separate because a single HIGH threat does not necessarily make the
  // composite station risk index HIGH. This prevents contradictory UI states.
  const overallRisk = simulationRisk?.overallRiskPercent ?? risk?.overallRiskPercent ?? null;
  const riskLevel = simulationRisk?.riskLevel ?? risk?.riskLevel ?? (overallRisk === null ? 'LOW' : overallRisk >= 70 ? 'CRITICAL' : overallRisk >= 40 ? 'HIGH' : overallRisk >= 20 ? 'MEDIUM' : 'LOW');
  const riskComponents = simulationRisk?.components ?? risk?.components ?? { extremeWeatherRiskPercent: 0, fuelReserveRiskPercent: 0, batterySocRiskPercent: 0, criticalLoadRiskPercent: 0 };
  const weather = snapshot.weather;
  const battery = snapshot.battery;
  const fuel = snapshot.fuel;
  const generation = snapshot.powerBalance;

  const activeThreats = useMemo(() => {
    if (systemMode === 'SIMULATION' && simulationTrajectory.length) {
      const threats = [] as { title: string; severity: 'LOW' | 'MEDIUM' | 'HIGH'; timing: string; description: string }[];
      const minSoc = Math.min(...simulationTrajectory.map(p => Number(p.battery_soc_percent ?? 100)));
      const minFuel = Math.min(...simulationTrajectory.map(p => Number(p.fuel_remaining_liters ?? snapshot.fuel.currentVolumeLiters)));
      const maxWind = Math.max(...simulationTrajectory.map(p => Number(p.wind_speed_mps ?? 0)));
      const minTemp = Math.min(...simulationTrajectory.map(p => Number(p.outdoor_temperature_celsius ?? 0)));
      const simShed = simulationTrajectory.some(p => Number(p.shed_load_kw ?? 0) > 0.001);
      if (minTemp <= -35) threats.push({ title: 'Extreme Cold', severity: 'HIGH', timing: 'Simulation horizon', description: `Scenario reaches ${minTemp.toFixed(0)}°C` });
      if (maxWind >= 20) threats.push({ title: 'High Wind', severity: 'HIGH', timing: 'Simulation horizon', description: `Scenario reaches ${maxWind.toFixed(1)} m/s` });
      if (minSoc < 25) threats.push({ title: 'Battery Reserve', severity: 'HIGH', timing: 'Simulation horizon', description: `Minimum SOC ${minSoc.toFixed(0)}%` });
      if (minFuel <= snapshot.fuel.emergencyReserveLiters) threats.push({ title: 'Fuel Reserve', severity: 'HIGH', timing: 'Simulation horizon', description: `Fuel reaches the configured reserve floor` });
      if (simShed) threats.push({ title: 'Load Shedding', severity: 'MEDIUM', timing: 'Simulation horizon', description: 'Flexible/important demand is shed in the scenario' });
      return threats.slice(0, 3);
    }
    const backendThreats = resilience?.activeThreats ?? [];
    if (backendThreats.length) return backendThreats.slice(0, 3);
    const threats = [] as { title: string; severity: 'LOW' | 'MEDIUM' | 'HIGH'; timing: string; description: string }[];
    if (weather.temperature <= -25) threats.push({ title: 'Extreme Cold', severity: 'HIGH', timing: 'Next 12 hours', description: `Temperature at ${weather.temperature.toFixed(0)}°C` });
    if (weather.windSpeed >= 18) threats.push({ title: 'High Wind', severity: 'MEDIUM', timing: 'Next 12 hours', description: `Wind speed ${weather.windSpeed.toFixed(1)} m/s` });
    const offlineGen = snapshot.generators.filter(g => g.status === 'OFFLINE').length;
    if (offlineGen) threats.push({ title: 'Generator Availability', severity: 'HIGH', timing: 'Current', description: `${offlineGen} generator(s) offline` });
    if (battery.socPercent < 35) threats.push({ title: 'Low Battery Reserve', severity: 'MEDIUM', timing: 'Next 24 hours', description: `Battery SOC ${battery.socPercent.toFixed(0)}%` });
    if (fuel.estimatedAutonomyDays !== null && fuel.estimatedAutonomyDays < 14) threats.push({ title: 'Fuel Horizon', severity: 'MEDIUM', timing: 'Resupply watch', description: `${fuel.estimatedAutonomyDays.toFixed(1)} days autonomy` });
    return threats.slice(0, 3);
  }, [resilience, weather, snapshot.generators, battery.socPercent, fuel.estimatedAutonomyDays, systemMode, simulationTrajectory, snapshot.fuel.currentVolumeLiters, snapshot.fuel.emergencyReserveLiters]);

  const riskTrend = useMemo(() => {
    if (systemMode === 'SIMULATION' && simulationTrajectory.length) {
      return simulationTrajectory.map(point => {
        const weatherRisk = (point.outdoor_temperature_celsius ?? 0) <= -35 || (point.wind_speed_mps ?? 0) >= 20 ? 100 : 0;
        const batteryRisk = Math.max(0, Math.min(100, (25 - Number(point.battery_soc_percent ?? 100)) / 25 * 100));
        const fuelRisk = Math.max(0, Math.min(100, (snapshot.fuel.emergencyReserveLiters - Number(point.fuel_remaining_liters ?? snapshot.fuel.currentVolumeLiters)) / Math.max(1, snapshot.fuel.emergencyReserveLiters) * 100));
        const load = Math.max(1, Number(point.load_kw ?? 0));
        const criticalRisk = Math.min(100, Math.max(0, Number(point.shed_load_kw ?? 0)) / load * 100);
        return { hour: point.hour_offset === 0 ? 'Now' : `${point.hour_offset}h`, overall: 0.30 * weatherRisk + 0.25 * batteryRisk + 0.20 * fuelRisk + 0.25 * criticalRisk, weather: weatherRisk, fuel: fuelRisk, asset: criticalRisk, threshold: 40 };
      });
    }
    return (risk?.riskSeries ?? []).map(point => ({ hour: point.hour_offset === 0 ? 'Now' : `${point.hour_offset}h`, overall: point.overall, weather: point.weather, fuel: point.fuel, asset: point.service, threshold: 40 }));
  }, [risk, systemMode, simulationTrajectory, snapshot.fuel.emergencyReserveLiters, snapshot.fuel.currentVolumeLiters]);

  const reserveTrend = useMemo(() => (systemMode === 'SIMULATION' ? [] : (resilience?.reserveForecast ?? []).map(point => ({
    hour: point.hourOffset === 0 ? 'Now' : `${point.hourOffset}h`,
    reliability: Math.max(0, 100 - point.recommendedPercent),
    target: Math.max(0, 100 - point.minimumPercent),
  }))), [resilience, systemMode]);

  const runAnalysis = async () => {
    setRunning(true);
    try {
      const result = await simulateFailureScenario(scenarioKey, 72, 0, {}, true);
      setScenario(result);
      await Promise.all([refreshResilience(72, true), refreshSnapshot()]);
      const nextRisk = await fetchStationRisk(72);
      setRisk(nextRisk);
    } finally {
      setRunning(false);
    }
  };

  const runReevaluation = async () => {
    setRunning(true);
    try {
      await reevaluateStationResilience(72);
      await Promise.all([refreshResilience(72, true), refreshSnapshot()]);
      setRisk(await fetchStationRisk(72));
    } finally {
      setRunning(false);
    }
  };

  const scenarioProjectedFuel = scenario ? Math.max(0, fuel.currentVolumeLiters - Math.max(0, scenario.fuelConsumptionLhr) * 72) : null;
  const scenarioReserveBreach = scenarioProjectedFuel !== null && scenarioProjectedFuel <= fuel.emergencyReserveLiters;
  const displayedFuelNow = scenario ? fuel.currentVolumeLiters : fuelPlan?.current_fuel_liters ?? fuel.currentVolumeLiters;
  const displayedFuelAtHorizon = scenario ? scenarioProjectedFuel : fuelPlan?.projected_fuel_liters ?? null;
  const displayedResupply = scenario ? (scenarioReserveBreach ? Math.max(0, fuel.emergencyReserveLiters - (scenarioProjectedFuel ?? 0)) : 0) : (fuelPlan?.resupply_needed_now ? Math.round(fuelPlan.recommended_resupply_quantity_liters) : 0);
  const displayedHorizonText = scenario ? (scenarioReserveBreach ? 'Reserve breach in scenario' : 'No reserve breach in 72h') : (fuelPlan ? (fuelPlan.reserve_breach_within_horizon ? (fuelPlan.estimated_hours_to_reserve == null ? 'At reserve' : `${(fuelPlan.estimated_hours_to_reserve/24).toFixed(1)} d`) : `No breach in ${fuelPlan.horizon_hours}h`) : 'Unavailable');
  const displayedAction = scenario ? (scenarioReserveBreach ? 'RESUPPLY / CONSERVE' : 'SCENARIO WITHIN RESERVE') : (fuelPlan?.recommended_action?.replaceAll('_',' ') ?? 'MONITOR');

  const autonomyDays = resilience?.fuelSurvivalDays ?? fuel.estimatedAutonomyDays;
  const autonomyPercent = autonomyDays == null ? 0 : Math.min(100, Math.max(0, autonomyDays / 14 * 100));
  const posture = resilience?.status ?? (overallRisk !== null && overallRisk >= 70 ? 'CRITICAL' : overallRisk !== null && overallRisk >= 40 ? 'WATCH' : 'GOOD');

  const recommendation = scenario?.recommendedActions?.[0]
    ?? resilience?.recommendedProactiveActions?.[0]
    ?? (riskLevel === 'HIGH' || riskLevel === 'CRITICAL' ? 'Enter contingency operating posture and protect critical loads.' : 'Maintain current safety-first EMS operation and monitor forecast changes.');

  return (
    <div className="space-y-3 text-slate-200">
      {/* Main resilience workspace */}
      <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2"><Fuel className="h-5 w-5 text-orange-300"/><span className="font-bold">POLAR SURVIVAL HORIZON</span></div>
            <p className="mt-1 text-[10px] text-slate-500">How long the station can protect critical operations before the next resupply window.</p>
          </div>
          <span className={`rounded-md border px-2 py-1 text-[9px] font-bold ${riskClass(riskLevel)}`}>{fuelPlanLoading && !scenario ? 'CALCULATING' : riskLevel}</span>
        </div>
        {systemMode === 'SIMULATION' && simulationTrajectory.length ? (
          <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-2">
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-2.5"><div className="text-[9px] text-slate-500">SIM FUEL NOW</div><div className="text-sm font-black text-white">{Math.round(simulationTrajectory[0].fuel_remaining_liters).toLocaleString()} L</div></div>
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-2.5"><div className="text-[9px] text-slate-500">SIM FUEL END</div><div className="text-sm font-black text-white">{Math.round(simulationTrajectory.at(-1)?.fuel_remaining_liters ?? 0).toLocaleString()} L</div></div>
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-2.5"><div className="text-[9px] text-slate-500">MIN SOC</div><div className="text-sm font-black text-white">{Math.min(...simulationTrajectory.map(p => Number(p.battery_soc_percent ?? 100))).toFixed(0)}%</div></div>
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-2.5"><div className="text-[9px] text-slate-500">SERVICE LEVEL</div><div className="text-sm font-black text-white">{(100 * simulationTrajectory.reduce((sum, p) => sum + Number(p.served_load_kw ?? p.load_kw) / Math.max(1, Number(p.load_kw ?? 0)), 0) / simulationTrajectory.length).toFixed(0)}%</div></div>
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-2.5"><div className="text-[9px] text-slate-500">MODE</div><div className="text-[11px] font-black text-cyan-200">SIMULATION</div></div>
          </div>
        ) : (fuelPlan || scenario) ? (
          <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-2">
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"><div className="text-[9px] text-slate-500">FUEL NOW</div><div className="text-sm font-black text-white">{Math.round(displayedFuelNow).toLocaleString()} L</div></div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"><div className="text-[9px] text-slate-500">RESERVE HORIZON</div><div className={`text-sm font-black ${scenario ? 'text-cyan-200' : 'text-white'}`}>{displayedHorizonText}</div></div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"><div className="text-[9px] text-slate-500">AT +72H</div><div className="text-sm font-black text-white">{displayedFuelAtHorizon == null ? '—' : `${Math.round(displayedFuelAtHorizon).toLocaleString()} L`}</div></div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"><div className="text-[9px] text-slate-500">RESUPPLY</div><div className="text-sm font-black text-white">{displayedResupply > 0 ? `${Math.round(displayedResupply).toLocaleString()} L` : 'Not required'}</div></div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"><div className="text-[9px] text-slate-500">ACTION</div><div className="text-[11px] font-black text-cyan-200">{displayedAction}</div></div>
          </div>
        ) : <div className="mt-3 text-xs text-slate-500">Fuel survival planning is unavailable right now. Other resilience controls remain usable.</div>}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
        {/* Risk overview + threats */}
        <div className="xl:col-span-3 space-y-3">
          <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-cyan-300"/><span className="font-bold">COMPOSITE RISK INDEX</span></div>
              <div className="flex items-center gap-2"><span className={`px-2 py-1 rounded-md border text-[10px] font-bold ${riskClass(riskLevel)}`}>COMPOSITE {riskLevel}</span><span className="text-[9px] text-slate-500">{activeThreats.length} active threat{activeThreats.length === 1 ? "" : "s"}</span></div>
            </div>
            <div className="mb-3 rounded-md border border-slate-800 bg-slate-950/50 px-2.5 py-2 text-[9px] text-slate-500">Composite engineering risk index from the backend resilience projection — threat severity is shown separately and this is not a calibrated field probability.</div>
            <div className="flex items-center gap-4">
              <div className="relative h-28 w-28 shrink-0">
                <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                  <circle cx="60" cy="60" r="46" fill="none" stroke="currentColor" strokeWidth="10" className="text-slate-800" />
                  <circle cx="60" cy="60" r="46" fill="none" stroke="currentColor" strokeWidth="10" strokeLinecap="round" strokeDasharray={`${Math.min(289, Math.max(0, overallRisk ?? 0) * 2.89)} 289`} className={(overallRisk ?? 0) >= 70 ? 'text-red-400' : (overallRisk ?? 0) >= 40 ? 'text-amber-400' : 'text-emerald-400'} />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center"><span className="text-2xl font-black text-white">{overallRisk == null ? '—' : overallRisk.toFixed(0)}</span><span className="text-[10px] text-slate-400">/100</span></div>
              </div>
              <div className="space-y-2 text-xs flex-1">
                <div className="flex justify-between"><span className="text-slate-400">Extreme</span><span className="text-red-300">{riskComponents.extremeWeatherRiskPercent.toFixed(0)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Fuel</span><span className="text-amber-300">{riskComponents.fuelReserveRiskPercent.toFixed(0)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Battery</span><span className="text-cyan-300">{riskComponents.batterySocRiskPercent.toFixed(0)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Critical load</span><span className="text-emerald-300">{riskComponents.criticalLoadRiskPercent.toFixed(0)}</span></div>
              </div>
            </div>
          </section>

          <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
            <div className="flex items-center justify-between mb-3"><div className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-red-400"/><span className="font-bold">ACTIVE THREATS</span></div><button type="button" onClick={() => setShowAllThreats(v => !v)} className="text-[10px] text-cyan-300">{showAllThreats ? 'COLLAPSE' : 'VIEW ALL'} <ChevronRight className={`inline h-3 w-3 transition ${showAllThreats ? 'rotate-90' : ''}`}/></button></div>
            <div className="space-y-2">
              {(showAllThreats ? activeThreats : activeThreats.slice(0, 3)).map((threat, index) => (
                <div key={`${threat.title}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/50 p-2.5">
                  <div className="flex items-start gap-2"><span className={`mt-1 h-2.5 w-2.5 rounded-full ${severityDot(threat.severity)}`} /><div className="min-w-0 flex-1"><div className="flex justify-between gap-2"><span className="text-xs font-bold text-white">{threat.title}</span><span className={`text-[9px] px-1.5 py-0.5 rounded border ${riskClass(threat.severity)}`}>{threat.severity} THREAT</span></div><p className="text-[10px] text-slate-400 mt-1">{threat.description}</p><p className="text-[9px] text-slate-500 mt-1">{threat.timing}</p></div></div>
                </div>
              ))}
              {!activeThreats.length && <div className="text-xs text-emerald-300 flex items-center gap-2"><CheckCircle2 className="h-4 w-4"/>No active threats detected.</div>}
            </div>
          </section>

          <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
            <div className="flex items-center gap-2 mb-3"><Gauge className="h-5 w-5 text-cyan-300"/><span className="font-bold">STATION RESILIENCE STATUS</span></div>
            <div className="space-y-2.5 text-[11px]">
              {[
                ['Critical Load Protection', resilience?.metrics.criticalLoadProtection ?? 0, '%'],
                ['Fuel Autonomy', autonomyDays, ' days'],
                ['Battery SOC', battery.socPercent, '%'],
                ['Renewable Contribution', generation.renewableSharePercent, '%'],
                ['Online Generators', snapshot.generators.filter(g => g.status === 'ONLINE').length, ` / ${snapshot.generators.length}`],
              ].map(([label, value, suffix]) => (
                <div key={label as string}>
                  <div className="flex justify-between mb-1"><span className="text-slate-400">{label}</span><span className="text-white font-semibold">{value == null ? '—' : `${Number(value).toFixed(label === 'Fuel Autonomy' ? 1 : 0)}${suffix}`}</span></div>
                  <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden"><div className={`h-full rounded-full ${label === 'Fuel Autonomy' && autonomyDays != null && autonomyDays < 5 ? 'bg-red-400' : label === 'Fuel Autonomy' && autonomyDays != null && autonomyDays < 10 ? 'bg-amber-400' : 'bg-emerald-400'}`} style={{ width: `${label === 'Fuel Autonomy' ? autonomyPercent : Math.min(100, Number(value))}%` }} /></div>
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"><div className="flex items-center justify-between"><span className="text-xs text-slate-300">Resilience posture</span><span className={`text-xs font-bold ${posture === 'CRITICAL' ? 'text-red-300' : posture === 'WATCH' ? 'text-amber-300' : 'text-emerald-300'}`}>{posture}</span></div><p className="mt-1 text-[9px] text-slate-500">Station resilience score: {resilience?.overallScore?.toFixed(0) ?? '—'}/100. This is separate from the composite risk index.</p></div>
          </section>
        </div>

        {/* Resilience network */}
        <section className="polar-interactive-card xl:col-span-6 rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-cyan-950/80">
            <div className="flex items-center gap-2"><Shield className="h-5 w-5 text-cyan-300"/><div><h2 className="font-bold text-sm">STATION RESILIENCE NETWORK</h2><p className="text-[10px] text-slate-500">Critical dependencies, reserve state and contingency posture</p></div></div>
            <div className="flex items-center gap-2"><button onClick={() => setRiskMode(false)} className={`px-3 py-1.5 rounded-full text-[10px] border ${!riskMode ? 'border-emerald-400/50 bg-emerald-400/10 text-emerald-300' : 'border-slate-700 text-slate-500'}`}>● CURRENT DATA</button><button onClick={() => setRiskMode(true)} className={`px-3 py-1.5 rounded-full text-[10px] border ${riskMode ? 'border-red-400/60 bg-red-400/10 text-red-300' : 'border-slate-700 text-slate-500'}`}>● RISK MODE</button></div>
          </div>
          <div className="relative h-[460px] overflow-hidden bg-[#020914] p-5">
            <div className="absolute inset-0 opacity-35" style={{backgroundImage:'linear-gradient(rgba(34,211,238,.06) 1px, transparent 1px),linear-gradient(90deg, rgba(34,211,238,.06) 1px, transparent 1px)',backgroundSize:'30px 30px'}} />
            <div className="relative h-full">
              <svg viewBox="0 0 900 390" className="absolute inset-0 h-full w-full" preserveAspectRatio="none"><g stroke="#155e75" strokeWidth="3" fill="none" strokeDasharray="7 8"><path d="M450 65 L450 155"/><path d="M180 115 L395 175"/><path d="M720 115 L505 175"/><path d="M180 290 L395 210"/><path d="M720 290 L505 210"/><path d="M450 235 L450 325"/></g><circle cx="450" cy="100" r="5" fill="#22d3ee"><animate attributeName="cy" values="70;145" dur="1.8s" repeatCount="indefinite"/></circle></svg>
              <div className="absolute left-1/2 top-4 -translate-x-1/2 rounded-xl border border-cyan-400/60 bg-cyan-950/80 px-5 py-3 text-center"><div className="text-[8px] tracking-widest text-cyan-300">{scenario ? 'SCENARIO GENERATION' : 'STATION CORE'}</div><div className="text-sm font-black text-white">{(scenario?.totalGenerationKw ?? generation.totalLoadKw).toFixed(0)} kW</div><div className="text-[9px] text-emerald-300">{scenario ? 'ANALYSIS RESULT' : 'CURRENT DEMAND'}</div></div>
              <div className="absolute left-2 top-20 w-36 rounded-xl border border-cyan-900 bg-[#061425]/95 p-3"><div className="text-[8px] tracking-widest text-slate-500">POWER</div><div className="text-sm font-black text-cyan-300">{(scenario?.totalGenerationKw ?? generation.totalGenerationKw).toFixed(0)} kW</div><div className="text-[9px] text-slate-400">{scenario ? 'Scenario generation' : 'Generation path'}</div></div>
              <div className="absolute right-2 top-20 w-36 rounded-xl border border-orange-900/70 bg-[#061425]/95 p-3"><div className="text-[8px] tracking-widest text-slate-500">FUEL</div><div className="text-sm font-black text-orange-300">{Math.round(displayedFuelAtHorizon ?? fuel.currentVolumeLiters).toLocaleString()} L</div><div className="text-[9px] text-slate-400">{scenario ? 'Projected +72h' : `${fuel.estimatedAutonomyDays?.toFixed(1) ?? '—'} days`}</div></div>
              <div className="absolute left-2 bottom-20 w-36 rounded-xl border border-cyan-900 bg-[#061425]/95 p-3"><div className="text-[8px] tracking-widest text-slate-500">BATTERY</div><div className="text-sm font-black text-cyan-300">{(scenario?.batterySocMinPercent ?? battery.socPercent).toFixed(0)}% SOC</div><div className="text-[9px] text-slate-400">{scenario ? 'Scenario minimum' : 'Reserve headroom'}</div></div>
              <div className="absolute right-2 bottom-20 w-36 rounded-xl border border-red-900/70 bg-[#061425]/95 p-3"><div className="text-[8px] tracking-widest text-slate-500">DIESEL</div><div className="text-sm font-black text-red-300">{scenario ? `${scenario.fuelConsumptionLhr.toFixed(2)} L/h` : `${generation.dieselGenKw.toFixed(0)} kW`}</div><div className="text-[9px] text-slate-400">{scenario ? 'Scenario fuel rate' : `${snapshot.generators.filter(g => g.status === 'ONLINE').length} online`}</div></div>
              <div className="absolute left-1/2 bottom-4 -translate-x-1/2 rounded-xl border border-emerald-900/70 bg-[#061425]/95 px-5 py-3 text-center"><div className="text-[8px] tracking-widest text-slate-500">CRITICAL LOAD PATH</div><div className="text-sm font-black text-white">{scenario ? `${scenario.criticalLoadCoveragePercent.toFixed(1)}% COVERAGE` : `${snapshot.loads.filter(l=>l.priority==='P0').reduce((s,l)=>s+l.currentLoadKw,0).toFixed(0)} kW PROTECTED`}</div></div>
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-cyan-400/60 bg-cyan-950/70 px-6 py-5 text-center shadow-[0_0_35px_rgba(34,211,238,.10)]"><div className="text-[8px] tracking-widest text-cyan-300">RESILIENCE BUS</div><div className="text-lg font-black text-white">{posture}</div><div className="text-[9px] text-slate-400">Reserve + redundancy</div></div>
              {riskMode && <div className="absolute inset-0 rounded-xl bg-red-500/[0.025] pointer-events-none" />}
              <div className="absolute top-3 right-3 flex gap-2 text-[9px]"><span className="rounded border border-slate-700 bg-slate-950/80 px-2 py-1">DEPENDENCY MAP</span><span className="rounded border border-red-500/40 bg-red-950/60 px-2 py-1 text-red-300">HIGH</span><span className="rounded border border-amber-500/40 bg-amber-950/60 px-2 py-1 text-amber-300">MEDIUM</span></div>
            </div>
          </div>
        </section>

        {/* Strategy + scenario */}
        <div className="xl:col-span-3 space-y-3">
          <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
            <div className="flex items-center gap-2 mb-3"><Shield className="h-5 w-5 text-cyan-300"/><span className="font-bold">RESILIENCE STRATEGY</span></div>
            <div className="space-y-2">
              {[
                ['loadShedding', 'Dynamic Load Shedding', Zap],
                ['renewablePriority', 'Renewable Priority', Sun],
                ['batteryReserve', 'Battery Reserve Mode', BatteryCharging],
                ['fuelConservation', 'Fuel Conservation Mode', Fuel],
                ['alternateRouting', 'Alternate Power Routing', Wind],
                ['emergencyComms', 'Emergency Communication', Radio],
              ].map(([key, label, Icon]) => {
                const k = key as keyof typeof strategy;
                const IconComponent = Icon as React.ElementType;
                return <button key={k} onClick={() => setStrategy(prev => ({ ...prev, [k]: !prev[k] }))} className="w-full flex items-center justify-between gap-2 text-xs py-1.5"><span className="flex items-center gap-2 text-slate-300"><IconComponent className="h-4 w-4 text-cyan-300"/>{label as string}</span><span className={`h-5 w-9 rounded-full p-0.5 transition ${strategy[k] ? 'bg-emerald-400/80' : 'bg-slate-700'}`}><span className={`block h-4 w-4 rounded-full bg-white transition ${strategy[k] ? 'translate-x-4' : ''}`} /></span></button>;
              })}
            </div>
          </section>

          <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
            <div className="flex items-center gap-2 mb-3"><Snowflake className="h-5 w-5 text-cyan-300"/><span className="font-bold">SCENARIO PLANNING</span></div>
            <select value={scenarioKey} onChange={e => setScenarioKey(e.target.value)} className="w-full rounded-lg border border-cyan-900 bg-slate-950 px-3 py-2 text-xs text-slate-200 outline-none">
              <option value="EXTREME_COLD">Extreme Cold + High Wind</option>
              <option value="DG1_FAILURE">Diesel Generator 1 Failure</option>
              <option value="BATTERY_FAILURE">Battery Failure</option>
              <option value="RENEWABLE_COLLAPSE">Renewable Collapse</option>
              <option value="FUEL_SHORTAGE">Fuel Shortage</option>
              <option value="MULTIPLE_FAILURES">Multiple Failures</option>
            </select>
            <button onClick={runAnalysis} disabled={running} className="mt-3 w-full rounded-lg bg-cyan-500/15 border border-cyan-400/50 px-3 py-2.5 text-xs font-bold text-cyan-200 hover:bg-cyan-500/25 disabled:opacity-50">{running ? 'RUNNING ANALYSIS…' : '▶ RUN RESILIENCE ANALYSIS'}</button>
            <button onClick={runReevaluation} disabled={running} className="mt-2 w-full rounded-lg border border-slate-700 px-3 py-2 text-[10px] text-slate-400 hover:text-white">Re-evaluate Current State</button>
          </section>

          <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
            <div className="flex items-center gap-2 mb-3"><Zap className="h-5 w-5 text-cyan-300"/><span className="font-bold">AI RECOMMENDATION</span></div>
            <div className={`rounded-lg border p-3 ${riskLevel === 'HIGH' || riskLevel === 'CRITICAL' ? 'border-red-500/40 bg-red-950/20' : 'border-amber-500/30 bg-amber-950/15'}`}><div className="flex items-center gap-2 text-xs font-bold"><AlertTriangle className="h-4 w-4 text-amber-300"/>Priority action</div><p className="mt-2 text-xs text-white leading-relaxed">{recommendation}</p></div>
            <div className="mt-3 space-y-2 text-[10px] text-slate-400">
              {(scenario?.recommendedActions ?? resilience?.recommendedProactiveActions ?? []).slice(0, 4).map((action, i) => <div key={i} className="flex gap-2"><span className="text-cyan-300">{i + 1}</span><span>{action}</span></div>)}
            </div>
          </section>
        </div>
      </div>

      {/* Lower analytics */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
          <div className="flex items-center justify-between mb-3"><div className="flex items-center gap-2"><TrendingUpIcon/><span className="font-bold">RISK INDEX (NEXT 72 HOURS)</span></div><span className="text-[10px] text-slate-500">Composite index · high-threat flags shown above</span></div>
          {riskTrend.length ? <div className="h-56"><ResponsiveContainer width="100%" height="100%"><LineChart data={riskTrend}><CartesianGrid stroke="#16324a" strokeDasharray="3 3"/><XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 10 }}/><YAxis domain={[0,100]} tick={{ fill: '#64748b', fontSize: 10 }}/><Tooltip contentStyle={{ background: '#04101d', border: '1px solid #164e63', fontSize: 11 }}/><Line type="monotone" dataKey="overall" stroke="#f87171" strokeWidth={2.5} dot={false} name="Scenario Risk Index"/><Line type="monotone" dataKey="weather" stroke="#22d3ee" strokeWidth={1.5} dot={false} name="Weather Risk"/><Line type="monotone" dataKey="fuel" stroke="#fbbf24" strokeWidth={1.5} dot={false} name="Fuel Risk"/><Line type="monotone" dataKey="asset" stroke="#a78bfa" strokeWidth={1.5} dot={false} name="Asset Risk"/><Line type="monotone" dataKey="threshold" stroke="#fbbf24" strokeDasharray="5 5" strokeWidth={1} dot={false} name="High-index threshold"/></LineChart></ResponsiveContainer></div> : <div className="h-56 flex items-center justify-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">Backend risk trajectory unavailable — no synthetic fallback is shown.</div>}
        </section>

        <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
          <div className="flex items-center justify-between mb-3"><div className="flex items-center gap-2"><Shield className="h-5 w-5 text-cyan-300"/><span className="font-bold">RESILIENCE METRICS (FORECAST)</span></div><span className="text-[10px] text-slate-500">Critical-load reliability target 90%</span></div>
          {reserveTrend.length ? <div className="h-56"><ResponsiveContainer width="100%" height="100%"><AreaChart data={reserveTrend}><defs><linearGradient id="resilienceFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#22d3ee" stopOpacity={0.28}/><stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02}/></linearGradient></defs><CartesianGrid stroke="#16324a" strokeDasharray="3 3"/><XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 10 }}/><YAxis domain={[70,100]} tick={{ fill: '#64748b', fontSize: 10 }}/><Tooltip contentStyle={{ background: '#04101d', border: '1px solid #164e63', fontSize: 11 }}/><Area type="monotone" dataKey="reliability" stroke="#22d3ee" fill="url(#resilienceFill)" strokeWidth={2.5} name="Reserve Margin"/><Line type="monotone" dataKey="target" stroke="#f87171" strokeDasharray="5 5" dot={false} name="Threshold"/></AreaChart></ResponsiveContainer></div> : <div className="h-56 flex items-center justify-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">Backend reserve forecast unavailable.</div>}
        </section>
      </div>

      {scenario && (
        <section className="polar-interactive-card rounded-xl border border-cyan-900/70 bg-[#040d1a]/95 p-4">
          <div className="flex items-center justify-between"><div><div className="text-sm font-bold text-white">CONTINGENCY RESULT · {scenario.title}</div><div className="text-[10px] text-slate-500">{scenario.aiAnalysis}</div></div><span className={`px-2 py-1 rounded border text-[10px] font-bold ${riskClass(scenario.resilienceOutcome === 'CRITICAL_RISK' ? 'HIGH' : scenario.resilienceOutcome === 'MITIGATED' ? 'MEDIUM' : 'LOW')}`}>{scenario.resilienceOutcome.replaceAll('_', ' ')}</span></div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
            {[
              ['Generation', `${scenario.totalGenerationKw.toFixed(0)} kW`],
              ['Fuel', `${scenario.fuelConsumptionLhr.toFixed(1)} L/h`],
              ['Min SOC', `${scenario.batterySocMinPercent.toFixed(0)}%`],
              ['Critical coverage', `${scenario.criticalLoadCoveragePercent.toFixed(1)}%`],
              ['Unserved Energy', `${(scenario.loadShedEnergyKwh ?? scenario.unservedLoadKw).toFixed(1)} kWh`],
            ].map(([label, value]) => <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"><div className="text-[9px] text-slate-500 uppercase">{label}</div><div className="mt-1 text-sm font-bold text-white">{value}</div></div>)}
          </div>
        </section>
      )}

      {(resilienceLoading || resilienceError) && <div className={`px-3 py-2 rounded-lg border text-[10px] ${resilienceError ? 'border-red-900/70 bg-red-950/30 text-red-300' : 'border-cyan-900/60 bg-cyan-950/20 text-cyan-300'}`}>{resilienceLoading ? 'Refreshing backend resilience intelligence…' : `Backend resilience status: ${resilienceError}`}</div>}
    </div>
  );
};

const TrendingUpIcon = () => <svg viewBox="0 0 24 24" className="h-5 w-5 text-cyan-300" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 17l6-6 4 4 8-9"/><path d="M15 6h6v6"/></svg>;
