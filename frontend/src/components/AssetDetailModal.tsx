import React from 'react';
import { X, Activity, Wrench, Shield, CheckCircle2, TrendingUp, Thermometer } from 'lucide-react';
import { StationNode, AssetRecord } from '../types';
import mainBuildingPhoto from '../assets/images/maitri_main_building_1789652436746.jpg';
import { useStation } from '../integration/StationContext';

interface AssetDetailModalProps {
  asset: StationNode | AssetRecord | null;
  onClose: () => void;
}

export const AssetDetailModal: React.FC<AssetDetailModalProps> = ({ asset, onClose }) => {
  if (!asset) return null;

  const { snapshot } = useStation();
  const isNode = 'powerKw' in asset;
  const name = asset.name;
  const gen = snapshot.generators.find(g => name.toLowerCase().includes(g.name.toLowerCase()) || asset.id.replace('-','').toLowerCase() === g.id.replace('-','').toLowerCase());
  const ren = snapshot.renewables.find(r => name.toLowerCase().includes(r.name.toLowerCase()) || asset.id.replace('-','').toLowerCase() === r.id.replace('-','').toLowerCase());
  const load = snapshot.loads.find(l => name.toLowerCase().includes(l.name.toLowerCase()) || asset.id.toLowerCase() === l.id.toLowerCase());
  const dynamicCapacity = gen ? `${gen.capacityKw.toFixed(0)} kW` : ren ? `${ren.capacityKw.toFixed(0)} kW` : load ? `${load.peakLoadKw.toFixed(0)} kW peak` : asset.capacity;
  const dynamicOutput = gen ? `${gen.currentOutputKw.toFixed(1)} kW` : ren ? `${ren.currentOutputKw.toFixed(1)} kW` : load ? `${load.currentLoadKw.toFixed(1)} kW` : isNode ? (asset.output ?? `${asset.powerKw.toFixed(1)} kW`) : asset.currentOutput;
  const dynamicHealth = gen ? `${gen.healthPercent.toFixed(0)}%` : ren ? 'Health not instrumented' : load ? load.shedStatus : '—';
  const dynamicTemp = gen ? `${snapshot.weather.temperature.toFixed(1)} °C ambient` : `${snapshot.thermal.indoorTemperatureC.toFixed(1)} °C indoor`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-[#061224] border border-cyan-500/50 rounded-2xl shadow-2xl overflow-hidden text-slate-200">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-cyan-950/70 border-b border-cyan-800/40 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/20 text-cyan-300">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-sans flex items-center gap-2">
                {name}
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 border border-emerald-500/50 text-emerald-300 font-mono">
                  {asset.status}
                </span>
              </h2>
              <p className="text-xs text-cyan-400/80 font-mono">
                Telemetry Station Asset ID: {asset.id} • Maitri Polar Microgrid
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto text-xs">
          {/* Real Photo + Quick Highlights */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="relative rounded-xl overflow-hidden border border-cyan-900/60 shadow-lg h-36">
              <img
                src={mainBuildingPhoto}
                alt={name}
                referrerPolicy="no-referrer"
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent"></div>
              <span className="absolute bottom-2 left-2 text-[10px] text-cyan-300 font-mono">
                Maitri Station Visual Asset
              </span>
            </div>

            <div className="sm:col-span-2 grid grid-cols-2 gap-2.5 font-mono">
              <div className="p-3 rounded-xl bg-[#030914] border border-cyan-950">
                <span className="text-[11px] text-slate-400 font-sans block">Operational Output</span>
                <span className="text-base font-bold text-cyan-300 mt-1 block">
                  {dynamicOutput}
                </span>
                <span className="text-[10px] text-amber-300 flex items-center gap-1 mt-1">
                  <CheckCircle2 className="w-3 h-3" /> Backend Twin value
                </span>
              </div>

              <div className="p-3 rounded-xl bg-[#030914] border border-cyan-950">
                <span className="text-[11px] text-slate-400 font-sans block">Health Index</span>
                <span className="text-base font-bold text-emerald-400 mt-1 block">
                  {dynamicHealth}
                </span>
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Next maintenance: {gen ? `${gen.nextMaintenanceHours.toFixed(0)} hrs` : (asset as AssetRecord).nextMaintenance || '—'}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-[#030914] border border-cyan-950">
                <span className="text-[11px] text-slate-400 font-sans block">Max Rated Capacity</span>
                <span className="text-base font-bold text-white mt-1 block">
                  {dynamicCapacity || '—'}
                </span>
                <span className="text-[10px] text-cyan-400/80 mt-1 block">Antarctic engineering reference</span>
              </div>

              <div className="p-3 rounded-xl bg-[#030914] border border-cyan-950">
                <span className="text-[11px] text-slate-400 font-sans block">Thermal / Environment</span>
                <span className="text-base font-bold text-amber-300 mt-1 block">
                  {dynamicTemp}
                </span>
                <span className="text-[10px] text-slate-400 mt-1 block">Environment: backend Twin</span>
              </div>
            </div>
          </div>

          {/* 24-Hour Telemetry Profile Graph */}
          <div className="p-4 rounded-xl bg-[#030914] border border-cyan-950 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 flex items-center gap-1.5 font-sans">
                <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
                24-Hour Output & Load Characteristic
              </span>
              <span className="text-[11px] font-mono text-cyan-400">Backend Twin series</span>
            </div>

            <div className="h-32 w-full pt-3">
              <svg className="w-full h-full" viewBox="0 0 500 120" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="curveGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
                  </linearGradient>
                </defs>
                {(() => { const pts=snapshot.horizonForecast; const values=pts.map(p=>load ? p.predictedTotalLoadKw : gen ? p.predictedDieselKw : ren?.type === 'Wind Turbine' ? p.predictedWindKw : p.predictedSolarKw); const max=Math.max(1,...values); const line=values.map((v,i)=>`${i/Math.max(1,values.length-1)*500},${108-(v/max)*78}`).join(' '); return <><polyline points={line} fill="none" stroke="#06b6d4" strokeWidth="2.5"/><polyline points={`${line} 500,120 0,120`} fill="none" stroke="#06b6d4" strokeOpacity="0.2" strokeWidth="1"/></>; })()}
                {/* Horizontal baseline lines */}
                <line x1="0" y1="30" x2="500" y2="30" stroke="#1e293b" strokeDasharray="3,3" />
                <line x1="0" y1="70" x2="500" y2="70" stroke="#1e293b" strokeDasharray="3,3" />
              </svg>
              <div className="flex justify-between font-mono text-[10px] text-slate-500 mt-1">
                {snapshot.horizonForecast.length ? [snapshot.horizonForecast[0], snapshot.horizonForecast[Math.floor((snapshot.horizonForecast.length - 1) / 2)], snapshot.horizonForecast[snapshot.horizonForecast.length - 1]].filter((p, i, a) => p && a.findIndex(x => x?.hourOffset === p?.hourOffset) === i).map(p => <span key={p!.hourOffset}>{p!.hourOffset === 0 ? 'Now' : `+${p!.hourOffset}h`}</span>) : <span>Forecast unavailable</span>}
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-black/40 border-t border-cyan-900/60 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-black font-semibold text-xs transition-all cursor-pointer shadow-md shadow-cyan-600/30"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
