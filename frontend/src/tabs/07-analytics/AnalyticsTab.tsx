import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity, BatteryCharging, BarChart3, CalendarDays, Download, Fuel, Gauge,
  Leaf, LineChart as LineChartIcon, Search, ShieldCheck, Snowflake, Sun,
  Zap
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell
} from 'recharts';
import { useStation } from '../../integration/StationContext';
import { fetchStationAnalyticsProjection, downloadStationReport } from '../../integration/api';

const COLORS = ['#ef4444', '#facc15', '#22d3ee', '#a78bfa'];

export const AnalyticsTab: React.FC = () => {
  const { snapshot, systemMode, simulationTrajectory } = useStation();
  const [range, setRange] = useState('30D');
  const [view, setView] = useState('Hourly');
  const [asset, setAsset] = useState('All Assets');
  const [metric, setMetric] = useState('All Metrics');
  const [projection, setProjection] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState('');
  const [loadMode, setLoadMode] = useState<'Total Load' | 'Critical' | 'Important' | 'Flexible'>('Total Load');
  const [renewableMode, setRenewableMode] = useState<'Solar' | 'Wind'>('Solar');
  const [showAllInsights, setShowAllInsights] = useState(false);

  const hours = range === '7D' ? 168 : range === '30D' ? 720 : range === '90D' ? 2160 : 8760;

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true); setError('');
    fetchStationAnalyticsProjection(hours, controller.signal)
      .then(data => { if (!cancelled) setProjection(data); })
      .catch(err => { if (!cancelled && !controller.signal.aborted) setError(err instanceof Error ? err.message : 'Analytics unavailable'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [hours]);

  const series = useMemo(() => {
    if (systemMode === 'SIMULATION' && simulationTrajectory.length) {
      return simulationTrajectory.map((p: any) => ({
        hour_offset: p.hour_offset,
        load_kw: p.load_kw, critical_load_kw: p.critical_load_kw ?? p.load_kw, served_load_kw: p.served_load_kw ?? p.load_kw, shed_load_kw: p.shed_load_kw ?? 0,
        important_load_kw: p.important_load_kw ?? 0, flexible_load_kw: p.flexible_load_kw ?? 0,
        solar_power_kw: p.solar_power_kw, wind_power_kw: p.wind_power_kw, diesel_power_kw: p.diesel_power_kw,
        battery_soc_ratio: Number(p.battery_soc_percent ?? 0) / 100,
        temperature_celsius: p.outdoor_temperature_celsius ?? 0, wind_speed_mps: p.wind_speed_mps ?? 0,
      }));
    }
    return Array.isArray(projection?.points) ? projection.points : snapshot.horizonForecast ?? [];
  }, [projection, snapshot.horizonForecast, systemMode, simulationTrajectory]);
  const metrics = projection?.metrics ?? {};
  const avg = (key: string) => {
    const values = series.map((x: any) => Number(x[key] ?? 0)).filter(Number.isFinite);
    return values.length ? values.reduce((a: number, b: number) => a + b, 0) / values.length : 0;
  };
  const sum = (key: string) => series.reduce((a: number, x: any) => a + Number(x[key] ?? 0), 0);
  const totalLoad = systemMode === 'SIMULATION' ? sum('load_kw') / 1000 : Number(metrics.load_energy_kwh ?? sum('load_kw')) / 1000;
  const solarMwh = systemMode === 'SIMULATION' ? sum('solar_power_kw') / 1000 : Number(metrics.solar_energy_kwh ?? sum('solar_power_kw')) / 1000;
  const windMwh = systemMode === 'SIMULATION' ? sum('wind_power_kw') / 1000 : Number(metrics.wind_energy_kwh ?? sum('wind_power_kw')) / 1000;
  const dieselMwh = systemMode === 'SIMULATION' ? sum('diesel_power_kw') / 1000 : Number(metrics.diesel_energy_kwh ?? sum('diesel_power_kw')) / 1000;
  const renewableMwh = solarMwh + windMwh;
  const totalGeneration = renewableMwh + dieselMwh;
  const renewableShare = totalGeneration ? renewableMwh / totalGeneration * 100 : Number(snapshot.powerBalance.renewableSharePercent ?? 0);
  const fuelConsumed = systemMode === 'SIMULATION' && simulationTrajectory.length
    ? Math.max(0, Number(simulationTrajectory[0]?.fuel_remaining_liters ?? 0) - Number(simulationTrajectory.at(-1)?.fuel_remaining_liters ?? 0))
    : Number(metrics.fuel_consumed_liters ?? 0);
  const avgLoad = avg('load_kw') || snapshot.powerBalance.totalLoadKw;
  const avgSoc = avg('battery_soc_ratio') ? avg('battery_soc_ratio') * 100 : snapshot.battery.socPercent;
  const uptime = systemMode === 'SIMULATION' && series.length
    ? (100 * series.reduce((sum: number, x: any) => sum + Number(x.served_load_kw ?? x.load_kw) / Math.max(1, Number(x.load_kw ?? 0)), 0) / series.length)
    : 100 - Number(metrics.blackout_risk_percent ?? 0);

  const chart = useMemo(() => {
    if (!series.length) return [];
    const baseBins = view === 'Daily' ? (range === '7D' ? 7 : range === '30D' ? 30 : range === '90D' ? 30 : 36) : (range === '7D' ? 14 : range === '30D' ? 15 : 18);
    const bins = Math.min(baseBins, series.length);
    return Array.from({ length: bins }, (_, i) => {
      const start = Math.floor(i * series.length / bins);
      const end = Math.max(start + 1, Math.floor((i + 1) * series.length / bins));
      const bucket = series.slice(start, end);
      const mean = (key: string) => bucket.reduce((s: number, x: any) => s + Number(x[key] ?? 0), 0) / bucket.length;
      const offset = Number(bucket[0]?.hour_offset ?? start);
      return {
        label: view === 'Daily' ? `D${Math.floor(offset / 24) + 1}` : (range === '30D' ? `D${Math.floor(offset / 24) + 1}` : `+${offset}h`),
        load: mean('load_kw'), critical: mean('critical_load_kw'),
        important: mean('important_load_kw'),
        flexible: mean('flexible_load_kw'),
        solar: mean('solar_power_kw'), wind: mean('wind_power_kw'), diesel: mean('diesel_power_kw'),
        soc: mean('battery_soc_ratio') * 100,
        temp: mean('temperature_celsius'), windSpeed: mean('wind_speed_mps'),
      };
    });
  }, [series, range, view]);

  const energyMix = [
    ...(dieselMwh > 0 ? [{ name: 'Diesel', value: dieselMwh }] : []),
    ...(solarMwh > 0 ? [{ name: 'Solar', value: solarMwh }] : []),
    ...(windMwh > 0 ? [{ name: 'Wind', value: windMwh }] : []),
  ];

  const assetRows = [
    ...snapshot.generators.map(g => ({ name: g.name.replace('Diesel Generator ', 'Diesel Generator '), value: g.capacityKw ? Math.min(100, Math.max(0, g.currentOutputKw) / g.capacityKw * 100) : 0, type: 'Generator' })),
    ...snapshot.renewables.map(r => ({ name: r.name, value: r.capacityKw ? Math.min(100, Math.max(0, r.currentOutputKw) / r.capacityKw * 100) : 0, type: r.type })),
    { name: 'Battery System', value: snapshot.battery.capacityKwh > 0 ? Math.min(100, Math.abs(snapshot.battery.currentPowerKw) / Math.max(1, snapshot.battery.capacityKwh) * 100) : 0, type: 'Storage' },
    ...snapshot.loads.filter(l => l.category === 'WATER_PUMPS').map(l => ({ name: l.name, value: Math.min(100, l.peakLoadKw > 0 ? l.currentLoadKw / l.peakLoadKw * 100 : 0), type: 'Utility' })),
  ];

  const filteredAssetRows = useMemo(() => {
    if (asset === 'Generators') return assetRows.filter(x => x.type === 'Generator');
    if (asset === 'Renewables') return assetRows.filter(x => x.type === 'Wind Turbine' || x.type === 'Solar Array');
    if (asset === 'Battery') return assetRows.filter(x => x.type === 'Storage');
    return assetRows;
  }, [asset, assetRows]);

  const insight = useMemo(() => [
    { label: 'OBSERVATION', text: `Renewables contribute ${renewableShare.toFixed(0)}% of projected generation over the selected window.`, implication: renewableShare >= 50 ? 'Lower diesel dependence in this projection.' : 'Diesel remains an important generation source.' },
    { label: 'DEMAND', text: `Average station demand is ${avgLoad.toFixed(0)} kW across the available projection.`, implication: 'Use Load Analysis to inspect critical, important and flexible demand.' },
    { label: 'STORAGE', text: `Battery SOC averages ${avgSoc.toFixed(0)}% across the selected window.`, implication: 'SOC trend indicates available storage headroom; inspect the Battery Analysis for changes over time.' },
    { label: 'FUEL', text: `Projected fuel consumption is ${fuelConsumed.toFixed(0)} L for the selected window.`, implication: 'Use Fuel Analysis to inspect diesel dispatch intensity across the window.' },
    { label: 'WEATHER', text: 'Weather correlation uses temperature and wind observations from the station projection.', implication: 'These are reference/projection inputs, not a claim of live Maitri NWP data.' }
  ], [renewableShare, avgLoad, avgSoc, fuelConsumed]);

  const visibleInsights = showAllInsights ? insight : insight.slice(0, 3);

  const primaryMetric = metric === 'Fuel' ? 'diesel' : metric === 'Battery' ? 'soc' : metric === 'Renewables' ? renewableMode.toLowerCase() : loadMode === 'Critical' ? 'critical' : loadMode === 'Important' ? 'important' : loadMode === 'Flexible' ? 'flexible' : 'load';
  const primaryMetricLabel = metric === 'All Metrics' ? loadMode : metric === 'Fuel' ? 'Fuel / Diesel' : metric === 'Battery' ? 'Battery SOC' : renewableMode;

  const exportReport = async () => {
    setExporting(true);
    try {
      const blob = await downloadStationReport(hours, 'pdf');
      const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = `dhruva-analytics-${range}.pdf`; a.click(); URL.revokeObjectURL(url);
      setExportNotice(`REPORT READY · ${range} · ${systemMode} · ENGINEERING MODEL`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Export unavailable'); setExportNotice(''); }
    finally { setExporting(false); }
  };

  return (
    <div className="analytics-page">
      <div className="analytics-toolbar">
        <div className="analytics-filter"><CalendarDays size={13}/> Analysis Window <select value={range} onChange={e => { setRange(e.target.value); setExportNotice(''); }}><option value="7D">7D Projection</option><option value="30D">30D Projection</option><option value="90D">90D Projection</option><option value="1Y">Reference Year</option></select></div>
        <div className="analytics-filter"><BarChart3 size={13}/> Data View <select value={view} onChange={e => setView(e.target.value)}><option>Hourly</option><option>Daily</option></select></div>
        <div className="analytics-filter"><Search size={13}/> Asset Filter <select value={asset} onChange={e => setAsset(e.target.value)}><option>All Assets</option><option>Generators</option><option>Renewables</option><option>Battery</option></select></div>
        <div className="analytics-filter"><Gauge size={13}/> Metric Filter <select value={metric} onChange={e => setMetric(e.target.value)}><option>All Metrics</option><option>Load</option><option>Fuel</option><option>Battery</option><option>Renewables</option></select></div>
        <div className="range-buttons"><button className={range === '7D' ? 'active' : ''} onClick={() => setRange('7D')}>7D</button><button className={range === '30D' ? 'active' : ''} onClick={() => setRange('30D')}>30D</button><button className={range === '90D' ? 'active' : ''} onClick={() => setRange('90D')}>90D</button><button className={range === '1Y' ? 'active' : ''} onClick={() => setRange('1Y')}>1Y</button></div>
        <button className="export-btn" onClick={() => void exportReport()} disabled={exporting}><Download size={15}/>{exporting ? 'Exporting…' : 'Export Report'}</button>
      </div>

      {loading && <div className="analytics-status">Loading {hours.toLocaleString()}h backend station projection…</div>}
      {error && <div className="analytics-status error">Backend analytics unavailable: {error}</div>}
      <div className="analytics-status"><span>PROVENANCE</span> · BACKEND PROJECTION · ENGINEERING MODEL · MODE: {systemMode} · WINDOW: {range}</div>
      {exportNotice && <div className="analytics-status analytics-export-status">{exportNotice} · REPORT IS GENERATED FROM THE SELECTED BACKEND PROJECTION WINDOW</div>}

      <div className="polar-interactive-card analytics-kpis">
        <Kpi icon={<Zap/>} title="Total Energy Generated" value={`${totalGeneration.toFixed(0)} MWh`} trend={range === '1Y' ? '8,760h reference projection' : 'Backend projection'} tone="yellow" />
        <Kpi icon={<Leaf/>} title="Renewable Contribution" value={`${renewableShare.toFixed(0)}%`} trend="Solar + wind" tone="green" />
        <Kpi icon={<Fuel/>} title="Total Fuel Consumption" value={`${fuelConsumed.toFixed(0)} L`} trend={`${hours.toLocaleString()}h ${range === '1Y' ? 'reference' : 'projection'}`} tone="red" />
        <Kpi icon={<Activity/>} title="Avg. Station Load" value={`${avgLoad.toFixed(0)} kW`} trend="Station demand" tone="blue" />
        <Kpi icon={<BatteryCharging/>} title="Battery SOC (Avg)" value={`${avgSoc.toFixed(0)}%`} trend="Projection average" tone="purple" />
        <Kpi icon={<ShieldCheck/>} title={systemMode === 'SIMULATION' ? 'Simulation Service Level' : 'Projected Service Level'} value={`${uptime.toFixed(1)}%`} trend={systemMode === 'SIMULATION' ? 'Scenario trajectory' : 'Projection-derived'} tone="green" />
      </div>

      <div className="analytics-main-grid">
        <div className="analytics-left">
          <Panel title="Energy Generation Mix" icon={<Leaf/>} className="mix-panel">
            <div className="donut-row"><div className="donut"><PieChart width={145} height={145}><Pie data={energyMix} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={43} outerRadius={64} paddingAngle={2}><Cell fill="#ef4444"/><Cell fill="#facc15"/><Cell fill="#22d3ee"/><Cell fill="#a78bfa"/></Pie></PieChart><div className="donut-center"><b>{totalGeneration.toFixed(0)}</b><span>MWh</span><small>Total</small></div></div><div className="legend-list">{energyMix.map((x,i)=><div key={x.name}><i style={{background:COLORS[i]}}/>{x.name}<strong>{(x.value / Math.max(0.01,totalGeneration) * 100).toFixed(0)}%</strong></div>)}</div></div>
          </Panel>
          <Panel title="Fuel Analysis" icon={<Fuel/>} action={<button type="button" className="panel-action-button" onClick={() => setMetric('Fuel')}>Details →</button>}>
            <div className="big-inline"><b>{fuelConsumed.toFixed(0)} L</b><span>selected horizon</span></div>
            <ResponsiveContainer width="100%" height={135}><BarChart data={chart}><CartesianGrid stroke="#12304a" vertical={false}/><XAxis dataKey="label" stroke="#64748b" fontSize={9}/><YAxis stroke="#64748b" fontSize={9}/><Tooltip contentStyle={{background:'#061224',border:'1px solid #164e63',color:'#e2e8f0'}} formatter={analyticsTooltipFormatter}/><Bar dataKey="diesel" fill="#f97316" radius={[3,3,0,0]}/></BarChart></ResponsiveContainer>
          </Panel>
          <Panel title="Battery Analysis" icon={<BatteryCharging/>} action={<button type="button" className="panel-action-button" onClick={() => setMetric('Battery')}>Details →</button>}>
            <div className="big-inline"><b>{avgSoc.toFixed(0)}%</b><span>average SOC</span></div>
            <ResponsiveContainer width="100%" height={120}><AreaChart data={chart}><CartesianGrid stroke="#12304a" vertical={false}/><XAxis dataKey="label" stroke="#64748b" fontSize={9}/><YAxis domain={[0,100]} stroke="#64748b" fontSize={9}/><Tooltip contentStyle={{background:'#061224',border:'1px solid #164e63'}} formatter={analyticsTooltipFormatter}/><Area dataKey="soc" stroke="#c084fc" fill="#c084fc" fillOpacity={0.18}/></AreaChart></ResponsiveContainer>
          </Panel>
        </div>

        <div className="analytics-center">
          <Panel title="Generation & Load Performance" icon={<LineChartIcon/>} className="analytics-primary-panel" action={<span className="live-pill">● {systemMode}</span>}>
            <div className="analytics-panel-kicker"><span>PRIMARY TREND</span><b>{view.toUpperCase()} · {range}</b></div>
            <ResponsiveContainer width="100%" height={250}><LineChart data={chart}><CartesianGrid stroke="#12304a" vertical={false}/><XAxis dataKey="label" stroke="#64748b" fontSize={9}/><YAxis stroke="#64748b" fontSize={9}/><Tooltip contentStyle={{background:'#061224',border:'1px solid #164e63',color:'#e2e8f0'}} formatter={analyticsTooltipFormatter}/><Legend wrapperStyle={{fontSize:9}}/><Line dataKey="load" name="Load (kW)" stroke="#f43f5e" strokeWidth={2.2} dot={false}/><Line dataKey="solar" name="Solar (kW)" stroke="#facc15" strokeWidth={1.8} dot={false}/><Line dataKey="wind" name="Wind (kW)" stroke="#22d3ee" strokeWidth={1.8} dot={false}/><Line dataKey="diesel" name="Diesel (kW)" stroke="#f97316" strokeWidth={1.8} dot={false}/></LineChart></ResponsiveContainer>
            <div className="analytics-trend-note"><span>READING</span><p>Compare demand against generation sources across the selected backend projection window.</p></div>
          </Panel>
          <div className="two-chart-row">
            <Panel title="Weather Correlation" icon={<Snowflake/>} action={<button type="button" className="panel-action-button" onClick={() => setMetric('Renewables')}>Details →</button>}><ResponsiveContainer width="100%" height={180}><LineChart data={chart}><CartesianGrid stroke="#12304a" vertical={false}/><XAxis dataKey="label" stroke="#64748b" fontSize={9}/><YAxis stroke="#64748b" fontSize={9}/><Tooltip contentStyle={{background:'#061224',border:'1px solid #164e63'}} formatter={analyticsTooltipFormatter}/><Legend wrapperStyle={{fontSize:9}}/><Line dataKey="temp" name="Temperature (°C)" stroke="#22d3ee" dot={false}/><Line dataKey="windSpeed" name="Wind (m/s)" stroke="#34d399" dot={false}/></LineChart></ResponsiveContainer><div className="analytics-source-note">REFERENCE WEATHER / PROJECTION INPUTS</div></Panel>
            <Panel title="Asset Utilization" icon={<Gauge/>} action={<button type="button" className="panel-action-button" onClick={() => setAsset('All Assets')}>Details →</button>}><div className="mb-2 text-[9px] text-slate-500">Utilization = current power ÷ rated capacity; battery uses instantaneous power, not health.</div><div className="util-list">{filteredAssetRows.slice(0,6).map(r=><div key={r.name}><span>{r.name}</span><div><i style={{width:`${Math.max(3,r.value)}%`}}/><b>{r.value.toFixed(0)}%</b></div></div>)}</div></Panel>
          </div>
        </div>

        <div className="analytics-right">
          <Panel title={`${metric === 'All Metrics' ? 'Load Analysis' : `${metric} Analysis`}`} icon={<Activity/>} action={<button type="button" className="panel-action-button" onClick={() => setMetric('Load')}>Details →</button>}><div className="subtabs">{(['Total Load','Critical','Important','Flexible'] as const).map(mode => <button type="button" key={mode} onClick={() => setLoadMode(mode)} className={loadMode === mode ? 'active' : ''}>{mode}</button>)}</div><ResponsiveContainer width="100%" height={180}><LineChart data={chart}><CartesianGrid stroke="#12304a" vertical={false}/><XAxis dataKey="label" stroke="#64748b" fontSize={9}/><YAxis stroke="#64748b" fontSize={9}/><Tooltip contentStyle={{background:'#061224',border:'1px solid #164e63'}} formatter={analyticsTooltipFormatter}/><Line dataKey={primaryMetric} name={primaryMetricLabel} stroke={primaryMetric === 'soc' ? '#c084fc' : primaryMetric === 'solar' ? '#facc15' : primaryMetric === 'wind' ? '#22d3ee' : primaryMetric === 'diesel' ? '#f97316' : primaryMetric === 'critical' ? '#f43f5e' : primaryMetric === 'important' ? '#facc15' : primaryMetric === 'flexible' ? '#22d3ee' : '#f43f5e'} strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></Panel>
          <Panel title="Renewable Performance" icon={<Sun/>} action={<button type="button" className="panel-action-button" onClick={() => setMetric('Renewables')}>Details →</button>}><div className="subtabs">{(['Solar','Wind'] as const).map(mode => <button type="button" key={mode} onClick={() => setRenewableMode(mode)} className={renewableMode === mode ? 'active' : ''}>{mode}</button>)}</div><ResponsiveContainer width="100%" height={155}><AreaChart data={chart}><CartesianGrid stroke="#12304a" vertical={false}/><XAxis dataKey="label" stroke="#64748b" fontSize={9}/><YAxis stroke="#64748b" fontSize={9}/><Tooltip contentStyle={{background:'#061224',border:'1px solid #164e63'}} formatter={analyticsTooltipFormatter}/><Area dataKey={renewableMode === 'Solar' ? 'solar' : 'wind'} stroke={renewableMode === 'Solar' ? '#facc15' : '#22d3ee'} fill={renewableMode === 'Solar' ? '#facc15' : '#22d3ee'} fillOpacity={0.16}/></AreaChart></ResponsiveContainer></Panel>
          <Panel title="Insights & Trends" icon={<LineChartIcon/>} action={<button type="button" className="panel-action-button" onClick={() => setShowAllInsights(v => !v)}>{showAllInsights ? 'Collapse ↑' : 'View All →'}</button>}><div className="insight-list">{visibleInsights.map((x,i)=><div key={x.text}><span>{i+1}</span><p><strong>{x.label}</strong>{x.text}<em>{x.implication}</em></p><b>↗</b></div>)}</div></Panel>
        </div>
      </div>
    </div>
  );
};

const analyticsTooltipFormatter = (value: number | string, name: string) => {
  const numeric = Number(value);
  return [Number.isFinite(numeric) ? numeric.toFixed(2) : String(value), name];
};

const Kpi = ({icon,title,value,trend,tone}:{icon:React.ReactNode;title:string;value:string;trend:string;tone:string}) => <div className={`analytics-kpi ${tone}`}><div className="kpi-icon">{icon}</div><div><span>{title}</span><strong>{value}</strong><small>{trend}</small></div><div className="kpi-spark"/></div>;
const Panel = ({title,icon,children,action,className=''}:{title:string;icon:React.ReactNode;children:React.ReactNode;action?:React.ReactNode;className?:string}) => <section className={`analytics-panel ${className}`}><div className="panel-head"><div><span className="panel-icon">{icon}</span><b>{title}</b></div>{action && <span className="panel-action">{action}</span>}</div><div className="panel-body">{children}</div></section>;
