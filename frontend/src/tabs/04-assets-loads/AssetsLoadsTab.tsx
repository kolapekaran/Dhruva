import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity, BatteryCharging, Fuel, Gauge, Search, ServerCog, ShieldAlert, Sun, Thermometer, Wind, Wrench, Zap,
} from 'lucide-react';
import { AssetRecord, StationNode } from '../../types';
import { useStation } from '../../integration/StationContext';
import { applyLoadAction } from '../../integration/api';

interface AssetsLoadsTabProps {
  onOpenAssetDetail: (asset: AssetRecord) => void;
  onOpenNodeDetail: (node: StationNode) => void;
}

type ViewMode = 'Assets' | 'Asset Health' | 'Loads';

const assetNodeId = (asset: AssetRecord): string | undefined => {
  if (asset.id === 'BATTERY') return 'battery-system';
  if (asset.id === 'FUEL') return 'fuel-tanks';
  if (asset.type === 'Wind Turbine') return 'wind-turbines';
  if (asset.type === 'Solar Array') return 'solar-array';
  if (asset.type === 'Diesel Generator') return 'diesel-generators';
  return undefined;
};

const assetIcon = (asset: AssetRecord) => {
  if (asset.id === 'BATTERY') return BatteryCharging;
  if (asset.id === 'FUEL') return Fuel;
  if (asset.type === 'Wind Turbine') return Wind;
  if (asset.type === 'Solar Array') return Sun;
  if (asset.type === 'Diesel Generator') return ServerCog;
  return Activity;
};

const healthPercent = (health: string) => {
  const match = health.match(/(\d+(?:\.\d+)?)%/);
  return match ? Math.max(0, Math.min(100, Number(match[1]))) : null;
};

const statusTone = (status: string) => {
  if (status === 'Online' || status === 'ONLINE' || status === 'SERVED' || status === 'Normal') return 'text-emerald-300 bg-emerald-950/70 border-emerald-700/60';
  if (status === 'Standby' || status === 'STANDBY') return 'text-amber-300 bg-amber-950/60 border-amber-700/60';
  if (status === 'Offline' || status === 'OFFLINE' || status === 'SHED') return 'text-red-300 bg-red-950/60 border-red-700/60';
  return 'text-slate-300 bg-slate-900/70 border-slate-700/60';
};

// Select an asset to inspect the authoritative station state

const AssetMapVisual: React.FC<{ selectedId?: string; onSelect: (nodeId: string) => void; snapshot: any }> = ({ selectedId, onSelect, snapshot }) => {
  const nodes = [
    {id:'wind-turbines', label:'WIND FARM', value:`${snapshot.powerBalance.windGenKw.toFixed(0)} kW`, x:'12%', y:'17%'},
    {id:'solar-array', label:'SOLAR ARRAY', value:`${snapshot.powerBalance.solarGenKw.toFixed(0)} kW`, x:'70%', y:'17%'},
    {id:'diesel-generators', label:'DIESEL GENERATORS', value:`${snapshot.powerBalance.dieselGenKw.toFixed(0)} kW`, x:'10%', y:'57%'},
    {id:'main-building', label:'MAIN BUILDING', value:`${snapshot.loads.find((l:any)=>l.priority==='P0')?.currentLoadKw?.toFixed(0) ?? '—'} kW`, x:'43%', y:'40%'},
    {id:'research-block', label:'RESEARCH BLOCK', value:`${snapshot.loads.find((l:any)=>l.priority==='P1')?.currentLoadKw?.toFixed(0) ?? '—'} kW`, x:'67%', y:'39%'},
    {id:'workshop-utilities', label:'WORKSHOP & UTILITIES', value:`${snapshot.loads.find((l:any)=>l.priority==='P2')?.currentLoadKw?.toFixed(0) ?? '—'} kW`, x:'57%', y:'69%'},
    {id:'battery-system', label:'BATTERY SYSTEM', value:`${snapshot.battery.socPercent.toFixed(0)}% SOC`, x:'37%', y:'76%'},
    {id:'fuel-tanks', label:'FUEL FARM', value:`${Math.round(snapshot.fuel.currentVolumeLiters).toLocaleString()} L`, x:'9%', y:'80%'},
  ];
  return <div className="relative min-h-[420px] overflow-hidden bg-[#020914] p-4 sm:p-6"><div className="absolute inset-0 opacity-35" style={{backgroundImage:'linear-gradient(rgba(34,211,238,.06) 1px, transparent 1px),linear-gradient(90deg, rgba(34,211,238,.06) 1px, transparent 1px)',backgroundSize:'28px 28px'}}/><div className="absolute inset-x-[8%] top-1/2 h-px bg-cyan-900/60"/><div className="absolute left-1/2 top-[12%] bottom-[12%] w-px bg-cyan-900/50"/><div className="absolute left-[24%] right-[24%] top-[52%] h-px bg-cyan-900/40"/><div className="relative h-[370px]">{nodes.map(n=><button key={n.id} onClick={()=>onSelect(n.id)} style={{left:n.x,top:n.y}} className={`absolute -translate-x-1/2 -translate-y-1/2 min-w-32 rounded-xl border px-3 py-2 text-left transition ${selectedId===n.id?'border-cyan-300 bg-cyan-950/90 ring-1 ring-cyan-300/50':'border-cyan-900/80 bg-[#061425]/95 hover:border-cyan-500'}`}><div className="text-[8px] uppercase tracking-widest text-slate-500">ASSET</div><div className="mt-1 text-[11px] font-black text-white">{n.label}</div><div className="mt-0.5 font-mono text-[10px] text-cyan-300">{n.value}</div></button>)}<div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-400/70 bg-cyan-950/80 px-5 py-3 text-center"><div className="text-[8px] tracking-widest text-cyan-300">ASSET NETWORK</div><div className="text-sm font-black text-white">{snapshot.loads.length + snapshot.generators.length + snapshot.renewables.length + 2} TRACKED</div></div></div><div className="absolute bottom-3 left-3 rounded-lg border border-cyan-900 bg-[#061425]/95 px-3 py-2 text-[9px] text-slate-400">Click an asset to synchronize the inspector and detailed state.</div></div>;
};

export const AssetsLoadsTab: React.FC<AssetsLoadsTabProps> = ({ onOpenAssetDetail, onOpenNodeDetail }) => {
  const { snapshot, refreshSnapshot, timeOffset, setSelectedAssetId, systemMode } = useStation();
  const [viewMode, setViewMode] = useState<ViewMode>('Assets');
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [selectedAsset, setSelectedAsset] = useState<AssetRecord | null>(null);
  const [loadActionBusy, setLoadActionBusy] = useState(false);
  const [loadActionMsg, setLoadActionMsg] = useState('');
  const sourceLabel = systemMode === 'OFFLINE' ? 'CACHED' : systemMode === 'SIMULATION' ? 'SIMULATION' : (snapshot.provenance.powerTelemetrySource || 'BACKEND');

  const dynamicAssets = useMemo<AssetRecord[]>(() => {
    const generationAssets = [...snapshot.generators, ...snapshot.renewables].map((a) => ({
      id: a.id, name: a.name, type: a.type,
      status: a.status === 'ONLINE' ? 'Online' : a.status === 'STANDBY' ? 'Standby' : a.status === 'OFFLINE' ? 'Offline' : 'Maintenance',
      capacity: `${a.capacityKw.toFixed(0)} kW`, currentOutput: `${a.currentOutputKw.toFixed(0)} kW`,
      efficiency: 'healthPercent' in a ? `${(a.electricalEfficiency * 100).toFixed(0)}%` : `${a.efficiencyPercent.toFixed(0)}%`,
      health: 'healthPercent' in a ? `${a.healthPercent.toFixed(0)}%` : '—',
      nextMaintenance: 'nextMaintenanceHours' in a && a.nextMaintenanceHours > 0 ? `${a.nextMaintenanceHours.toFixed(0)} h` : '—',
      fuelRate: 'fuelConsumptionLhr' in a ? `${a.fuelConsumptionLhr.toFixed(1)} L/h` : undefined,
      runtime: 'runtimeHours' in a ? `${a.runtimeHours.toFixed(0)} h` : undefined,
    }));

    const supportAssets: AssetRecord[] = [
      { id: 'BATTERY', name: 'Battery System', type: 'Storage', status: snapshot.battery.status === 'CHARGING' || snapshot.battery.status === 'DISCHARGING' ? 'Online' : 'Standby', capacity: `${snapshot.battery.capacityKwh.toFixed(0)} kWh`, currentOutput: `${snapshot.battery.currentPowerKw.toFixed(0)} kW`, efficiency: `${snapshot.battery.healthPercent.toFixed(0)}% health`, health: `${snapshot.battery.healthPercent.toFixed(0)}%`, nextMaintenance: '—' },
      { id: 'FUEL', name: 'Fuel Farm', type: 'Fuel Storage', status: snapshot.fuel.fillPercent > 0 ? 'Online' : 'Offline', capacity: `${snapshot.fuel.capacityLiters.toFixed(0)} L`, currentOutput: `${snapshot.fuel.currentVolumeLiters.toFixed(0)} L`, efficiency: '—', health: '—', nextMaintenance: '—' },
      ...snapshot.loads.map((load) => ({ id: load.id, name: load.name, type: 'Load', status: load.shedStatus === 'SHED' ? 'Offline' as const : 'Online' as const, capacity: `${load.peakLoadKw.toFixed(0)} kW peak`, currentOutput: `${load.currentLoadKw.toFixed(0)} kW`, efficiency: load.priority, health: load.priority, nextMaintenance: '—' })),
    ];
    return [...generationAssets, ...supportAssets];
  }, [snapshot]);

  useEffect(() => {
    if (!selectedAsset && dynamicAssets.length) {
      const preferred = dynamicAssets.find(asset => asset.id === 'BATTERY') ?? dynamicAssets.find(asset => asset.type === 'Diesel Generator') ?? dynamicAssets[0];
      setSelectedAsset(preferred);
      setSelectedAssetId(preferred.id);
    }
  }, [dynamicAssets, selectedAsset, setSelectedAssetId]);

  const filteredAssets = useMemo(() => dynamicAssets.filter((asset) => {
    const q = query.trim().toLowerCase();
    return (!q || `${asset.name} ${asset.id} ${asset.type}`.toLowerCase().includes(q)) && (typeFilter === 'All' || asset.type === typeFilter) && (statusFilter === 'All' || asset.status === statusFilter);
  }), [dynamicAssets, query, typeFilter, statusFilter]);

  const totalTracked = dynamicAssets.length;
  const onlineCount = dynamicAssets.filter(a => a.status === 'Online').length;
  const criticalLoads = snapshot.loads.filter(l => l.priority === 'P0');
  const availableCapacity = [...snapshot.generators, ...snapshot.renewables].filter(a => a.status !== 'OFFLINE' && a.status !== 'MAINTENANCE').reduce((sum, a) => sum + Math.max(0, a.capacityKw - a.currentOutputKw), 0);
  const generationCapacity = [...snapshot.generators, ...snapshot.renewables].reduce((sum, a) => sum + a.capacityKw, 0);
  const loadTotal = snapshot.powerBalance.totalLoadKw;
  const maintenanceAssets = snapshot.generators.filter(g => g.nextMaintenanceHours > 0 && g.nextMaintenanceHours <= 168);
  const typeCounts = dynamicAssets.reduce<Record<string, number>>((acc, asset) => { acc[asset.type] = (acc[asset.type] ?? 0) + 1; return acc; }, {});
  const statusCounts = dynamicAssets.reduce<Record<string, number>>((acc, asset) => { acc[asset.status] = (acc[asset.status] ?? 0) + 1; return acc; }, {});

  const selectAsset = (asset: AssetRecord) => { setSelectedAsset(asset); setSelectedAssetId(asset.id); };
  const assetForNode = (nodeId: string): AssetRecord | null => {
    if (nodeId === 'battery-system') return dynamicAssets.find(a => a.id === 'BATTERY') ?? null;
    if (nodeId === 'fuel-tanks') return dynamicAssets.find(a => a.id === 'FUEL') ?? null;
    if (nodeId === 'wind-turbines') return dynamicAssets.find(a => a.type === 'Wind Turbine') ?? null;
    if (nodeId === 'solar-array') return dynamicAssets.find(a => a.type === 'Solar Array') ?? null;
    if (nodeId === 'diesel-generators') return dynamicAssets.find(a => a.type === 'Diesel Generator') ?? null;
    const priority = nodeId === 'main-building' ? 'P0' : nodeId === 'research-block' ? 'P1' : nodeId === 'workshop-utilities' ? 'P2' : '';
    const load = snapshot.loads.find(l => l.priority === priority);
    return load ? dynamicAssets.find(a => a.id === load.id) ?? null : null;
  };
  const handleNodeSelect = (nodeId: string) => { const asset = assetForNode(nodeId); if (asset) selectAsset(asset); };

  return (
    <div className="space-y-4 text-slate-200">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {[
          { label: 'TRACKED ASSETS', value: totalTracked, meta: `${onlineCount} online`, icon: Activity, tone: 'text-cyan-300' },
          { label: 'CRITICAL LOADS', value: criticalLoads.length, meta: `${criticalLoads.reduce((s,l)=>s+l.currentLoadKw,0).toFixed(0)} kW protected`, icon: ShieldAlert, tone: 'text-red-300' },
          { label: 'STATION LOAD', value: `${loadTotal.toFixed(0)} kW`, meta: `${snapshot.loads.length} load groups`, icon: Zap, tone: 'text-yellow-300' },
          { label: 'AVAILABLE CAPACITY', value: `${availableCapacity.toFixed(0)} kW`, meta: `${generationCapacity.toFixed(0)} kW rated`, icon: Gauge, tone: 'text-emerald-300' },
          { label: 'FUEL RESERVE', value: `${snapshot.fuel.fillPercent.toFixed(0)}%`, meta: `${snapshot.fuel.currentVolumeLiters.toFixed(0)} L`, icon: Fuel, tone: 'text-orange-300' },
          { label: 'ENVIRONMENT', value: `${snapshot.weather.temperature.toFixed(0)}°C`, meta: `Wind ${snapshot.weather.windSpeed.toFixed(1)} m/s`, icon: Thermometer, tone: 'text-cyan-300' },
        ].map(({label,value,meta,icon:Icon,tone}) => (
          <div key={label} className="rounded-xl border border-cyan-900/60 bg-[#040d1a]/90 px-3 py-3 shadow-lg">
            <div className="flex items-center justify-between gap-2"><span className="text-[10px] font-semibold text-slate-400 tracking-wider">{label}</span><Icon className={`w-4 h-4 ${tone}`} /></div>
            <div className="mt-1 text-lg font-black text-white font-mono">{value}</div><div className={`text-[10px] ${tone}`}>{meta}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <div className="xl:col-span-8 rounded-2xl border border-cyan-900/60 bg-[#030a16] overflow-hidden shadow-xl">
          <div className="px-4 py-3 flex items-center justify-between border-b border-cyan-950/70">
            <div><h2 className="text-base font-black text-cyan-300 tracking-wide">STATION ASSETS</h2><p className="text-[10px] text-slate-500">Select one asset — map, inspector and detail state stay synchronized</p></div>
            <div className="flex items-center gap-2 text-[10px] font-mono"><span className={`rounded border px-2 py-1 ${systemMode === 'ONLINE' ? 'border-emerald-800/70 bg-emerald-950/30 text-emerald-300' : systemMode === 'SIMULATION' ? 'border-cyan-800/70 bg-cyan-950/30 text-cyan-300' : 'border-slate-700 bg-slate-900/60 text-slate-300'}`}>● {systemMode} · {sourceLabel}</span><span className="text-slate-400">{timeOffset > 0 ? `+${timeOffset}h` : 'NOW'}</span></div>
          </div>
          <AssetMapVisual selectedId={selectedAsset ? assetNodeId(selectedAsset) : undefined} onSelect={handleNodeSelect} snapshot={snapshot} />
        </div>

        <div className="xl:col-span-4 rounded-2xl border border-cyan-900/60 bg-[#040d1a]/95 shadow-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-cyan-950/70 flex items-center justify-between"><h2 className="text-base font-black text-white">ASSET INSPECTOR</h2>{selectedAsset && <span className={`px-2 py-1 rounded-md border text-[9px] font-bold ${statusTone(selectedAsset.status)}`}>{selectedAsset.status.toUpperCase()}</span>}</div>
          {selectedAsset ? <div className="p-4 space-y-4">
            <div className="rounded-xl border border-cyan-900/70 bg-gradient-to-br from-cyan-950/35 to-slate-950/70 p-3">
              <div className="flex items-start gap-3"><div className="mt-0.5 rounded-lg border border-cyan-800/70 bg-cyan-950/70 p-2 text-cyan-300">{React.createElement(assetIcon(selectedAsset), { className: 'w-4 h-4' })}</div><div className="min-w-0 flex-1"><div className="text-[9px] uppercase tracking-[.16em] text-cyan-500 font-mono">{selectedAsset.type}</div><div className="mt-0.5 text-lg font-black text-white truncate">{selectedAsset.name}</div><div className="mt-1 text-[9px] text-slate-500 font-mono">ID · {selectedAsset.id} · {sourceLabel}</div></div></div>
            </div>
            <div className="grid grid-cols-2 gap-2">{[['Capacity',selectedAsset.capacity],['Live reading',selectedAsset.currentOutput],['Efficiency',selectedAsset.efficiency],['Health',selectedAsset.health],['Maintenance',selectedAsset.nextMaintenance],['Fuel rate',selectedAsset.fuelRate ?? '—']].map(([k,v]) => <div key={k} className="rounded-lg bg-slate-950/80 border border-slate-800/80 p-2.5"><div className="text-[9px] text-slate-500 uppercase tracking-wider">{k}</div><div className="mt-1 text-[12px] font-bold text-white font-mono truncate">{v}</div></div>)}</div>
            {healthPercent(selectedAsset.health) !== null && <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/10 p-2.5"><div className="flex justify-between text-[9px] uppercase tracking-wider"><span className="text-slate-500">Asset health</span><span className="font-mono text-emerald-300">{healthPercent(selectedAsset.health)?.toFixed(0)}%</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-900"><div className="h-full rounded-full bg-emerald-400 transition-all duration-500" style={{width:`${healthPercent(selectedAsset.health)}%`}} /></div></div>}
            <button onClick={() => onOpenAssetDetail(selectedAsset)} className="group w-full rounded-lg border border-cyan-700/70 bg-cyan-950/45 py-2.5 text-xs font-bold text-cyan-300 hover:border-cyan-400 hover:bg-cyan-900/50">Open Full Asset Details <span className="inline-block transition-transform group-hover:translate-x-1">→</span></button>
          </div> : <div className="p-8 text-center text-slate-500 text-sm">No asset is selected. Choose one on the asset network or list.</div>}
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-cyan-950/70">
        {(['Assets','Asset Health','Loads'] as ViewMode[]).map(mode => <button key={mode} onClick={() => setViewMode(mode)} className={`px-4 py-2.5 text-xs font-bold border-b-2 transition-colors ${viewMode === mode ? 'text-cyan-300 border-cyan-400 bg-cyan-950/20' : 'text-slate-500 border-transparent hover:text-slate-300'}`}>{mode}</button>)}
      </div>

      {viewMode === 'Assets' && <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <div className="xl:col-span-8 rounded-xl border border-cyan-900/60 bg-[#040d1a]/90 shadow-lg overflow-hidden">
          <div className="p-4 border-b border-cyan-950/70 flex flex-col lg:flex-row gap-2 lg:items-center lg:justify-between"><div><h3 className="font-black text-white">ASSET LIST</h3><p className="text-[10px] text-slate-500">Equipment and load groups · SOURCE {sourceLabel}</p></div><div className="flex gap-2"><label className="relative"><Search className="absolute left-2 top-2 w-3.5 h-3.5 text-slate-500"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search assets..." className="w-44 rounded-md border border-cyan-900 bg-slate-950 pl-7 pr-2 py-1.5 text-[10px] text-white outline-none focus:border-cyan-500"/></label><select value={typeFilter} onChange={e=>setTypeFilter(e.target.value)} className="rounded-md border border-cyan-900 bg-slate-950 px-2 py-1.5 text-[10px] text-slate-300"><option>All</option>{Array.from(new Set(dynamicAssets.map(a=>a.type))).map(t=><option key={t}>{t}</option>)}</select><select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} className="rounded-md border border-cyan-900 bg-slate-950 px-2 py-1.5 text-[10px] text-slate-300"><option>All</option>{Array.from(new Set(dynamicAssets.map(a=>a.status))).map(s=><option key={s}>{s}</option>)}</select></div></div>
          <div className="max-h-[420px] overflow-auto"><table className="w-full text-left text-[10px]"><thead className="sticky top-0 z-10 bg-[#061321] text-slate-500 uppercase tracking-wider"><tr><th className="px-4 py-2.5">Asset</th><th>Type</th><th>Status</th><th>Capacity</th><th>Live reading</th><th>Health</th><th>Maint.</th></tr></thead><tbody className="divide-y divide-cyan-950/60">{filteredAssets.map(asset=><tr key={asset.id} onClick={()=>selectAsset(asset)} className={`group cursor-pointer border-l-2 transition-colors hover:bg-cyan-950/35 ${selectedAsset?.id===asset.id?'border-cyan-400 bg-cyan-950/55':'border-transparent'}`}><td className="px-4 py-2.5"><div className="flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${asset.status==='Online'?'bg-emerald-400':asset.status==='Standby'?'bg-amber-400':asset.status==='Offline'?'bg-red-400':'bg-slate-500'}`}></span><div className="font-bold text-cyan-300 group-hover:text-cyan-200">{asset.name}</div></div><div className="text-[9px] text-slate-600 font-mono">{asset.id}</div></td><td className="text-slate-400">{asset.type}</td><td><span className={`px-1.5 py-1 rounded border text-[9px] ${statusTone(asset.status)}`}>{asset.status}</span></td><td className="font-mono text-slate-300">{asset.capacity}</td><td className="font-mono text-white">{asset.currentOutput}</td><td className="font-mono text-emerald-300">{asset.health}</td><td className="font-mono text-slate-400">{asset.nextMaintenance}</td></tr>)}</tbody></table>{filteredAssets.length===0 && <div className="p-8 text-center text-slate-500">No matching assets.</div>}</div>
        </div>
        <div className="xl:col-span-4 space-y-4">
          <div className="rounded-xl border border-cyan-900/60 bg-[#040d1a]/90 p-4"><div className="flex items-center justify-between"><h3 className="font-black text-white">LOAD DISTRIBUTION</h3><span className="text-[9px] text-slate-500">SELECT TO INSPECT</span></div><div className="text-2xl font-black text-white font-mono mt-2">{loadTotal.toFixed(0)} <span className="text-xs text-cyan-400">kW total</span></div><div className="mt-4 space-y-2.5">{snapshot.loads.map(load=>{const pct=loadTotal?load.currentLoadKw/loadTotal*100:0;return <button key={load.id} onClick={()=>{const a=dynamicAssets.find(x=>x.id===load.id);if(a)selectAsset(a);setViewMode('Loads')}} className="w-full text-left rounded-lg border border-transparent p-2 -mx-2 hover:border-cyan-900/60 hover:bg-cyan-950/20 transition-colors"><div className="flex justify-between text-[10px]"><span className="text-slate-300 font-medium">{load.name}</span><span className="font-mono text-slate-400">{load.currentLoadKw.toFixed(0)} kW · {pct.toFixed(0)}%</span></div><div className="mt-1 h-1.5 bg-slate-900 rounded-full overflow-hidden"><div className="h-full bg-cyan-400" style={{width:`${Math.min(100,pct)}%`}}/></div></button>})}</div></div>
          <div className="grid grid-cols-2 gap-4"><div className="rounded-xl border border-cyan-900/60 bg-[#040d1a]/90 p-4"><h3 className="text-xs font-black text-white">ASSET STATUS</h3><div className="mt-3 space-y-2 text-[10px]">{Object.entries(statusCounts).map(([s,c])=><div key={s} className="flex justify-between"><span className="text-slate-400">{s}</span><span className="font-mono text-white">{c}</span></div>)}</div></div><div className="rounded-xl border border-cyan-900/60 bg-[#040d1a]/90 p-4"><h3 className="text-xs font-black text-white">ASSET TYPES</h3><div className="mt-3 space-y-2 text-[10px]">{Object.entries(typeCounts).slice(0,6).map(([t,c])=><div key={t} className="flex justify-between gap-2"><span className="text-slate-400 truncate">{t}</span><span className="font-mono text-white">{c}</span></div>)}</div></div></div>
        </div>
      </div>}

      {viewMode === 'Asset Health' && <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">{dynamicAssets.filter(a=>a.type!=='Load'&&a.type!=='Fuel Storage').map(asset=>{const hp=healthPercent(asset.health);return <button key={asset.id} onClick={()=>selectAsset(asset)} className={`text-left w-full rounded-xl border p-4 transition-all ${selectedAsset?.id===asset.id?'border-cyan-400/80 bg-cyan-950/25 shadow-[0_0_24px_rgba(34,211,238,.08)]':'border-cyan-900/60 bg-[#040d1a]/90 hover:border-cyan-700/70'}`}><div className="flex justify-between gap-2"><div><div className="text-[10px] text-cyan-400 font-mono">{asset.type}</div><div className="font-bold text-white">{asset.name}</div></div><span className={`px-2 py-1 rounded border text-[9px] ${statusTone(asset.status)}`}>{asset.status}</span></div><div className="mt-4"><div className="flex justify-between text-[10px] text-slate-400"><span>Health</span><span className="text-white">{asset.health}</span></div><div className="mt-1 h-2 rounded-full bg-slate-900 overflow-hidden"><div className="h-full bg-emerald-400" style={{width:hp!==null?`${hp}%`:'0%'}}/></div></div><div className="mt-3 text-[10px] text-slate-500">Next maintenance: <span className="text-slate-300">{asset.nextMaintenance}</span></div></button>})}{maintenanceAssets.length>0&&<div className="md:col-span-2 xl:col-span-3 rounded-xl border border-amber-800/60 bg-amber-950/20 p-4"><div className="flex items-center gap-2 text-amber-300 font-bold text-sm"><Wrench className="w-4 h-4"/>Maintenance watch</div><div className="mt-2 text-[10px] text-slate-400">{maintenanceAssets.map(a=>`${a.name}: ${a.nextMaintenanceHours.toFixed(0)} h`).join(' · ')}</div></div>}</div>}

      {viewMode === 'Loads' && <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">{snapshot.loads.map(load=>{const pct=loadTotal?load.currentLoadKw/loadTotal*100:0;return <div key={load.id} className="rounded-xl border border-cyan-900/60 bg-[#040d1a]/90 p-4"><div className="flex justify-between gap-2"><div><div className="text-[10px] text-cyan-400 font-mono">{load.priority} · {load.category}</div><div className="font-bold text-white">{load.name}</div></div><span className={`px-2 py-1 rounded border text-[9px] ${statusTone(load.shedStatus)}`}>{load.shedStatus}</span></div><div className="mt-4 text-2xl font-black text-white font-mono">{load.currentLoadKw.toFixed(0)} <span className="text-xs text-cyan-400">kW</span></div><div className="mt-2 h-2 bg-slate-900 rounded-full overflow-hidden"><div className="h-full bg-cyan-400" style={{width:`${Math.min(100,pct)}%`}}/></div><div className="mt-2 flex justify-between text-[10px] text-slate-500"><span>{pct.toFixed(0)}% of station load</span><span>Peak {load.peakLoadKw.toFixed(0)} kW</span></div>{load.isFlexible&&<button disabled={loadActionBusy} onClick={async()=>{setLoadActionBusy(true);try{const r=await applyLoadAction({shiftFlexibleKw:load.currentLoadKw});setLoadActionMsg(`${r.action} · ${Number(r.shifted_kw??r.shiftedKw??0).toFixed(1)} kW`);await refreshSnapshot()}catch(e){setLoadActionMsg(e instanceof Error?e.message:'Action failed')}finally{setLoadActionBusy(false)}}} className="mt-3 w-full rounded-lg border border-cyan-800 bg-cyan-950/50 py-2 text-[10px] font-bold text-cyan-300 disabled:opacity-50">{loadActionBusy?'Applying…':'Shift Flexible Load'}</button>}</div>})}{loadActionMsg&&<div className="xl:col-span-3 rounded-lg border border-emerald-800/60 bg-emerald-950/20 px-3 py-2 text-[10px] text-emerald-300">Backend action: {loadActionMsg}</div>}</div>}
    </div>
  );
};
