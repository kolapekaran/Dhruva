import React, { useState } from 'react';
import { useStation } from '../../../integration/StationContext';
import mainBuildingPhoto from '../../../assets/images/maitri_main_building_1789652436746.jpg';
import {
  X,
  Home,
  Building,
  ArrowRight,
} from 'lucide-react';

interface AssetInspectorProps {
  assetId: string;
  onClose: () => void;
}

export const AssetInspector: React.FC<AssetInspectorProps> = ({ assetId, onClose }) => {
  const { setActiveTab, snapshot } = useStation();
  const normalizedId = assetId.replace('-', '').toUpperCase();
  const loadAlias: Record<string, string> = { MAIN: 'L-CRITICAL', RESEARCH: 'L-IMPORTANT', WORKSHOP: 'L-FLEX' };
  const renewableAlias: Record<string, string> = { WIND: 'WT-01', SOLAR: 'PV-01' };
  const generatorAlias: Record<string, string> = { DG: 'DG-01' };
  const generator = snapshot.generators.find(a => a.id.replace('-', '').toUpperCase() === (generatorAlias[normalizedId] ?? normalizedId).replace('-', '').toUpperCase());
  const renewable = snapshot.renewables.find(a => a.id.replace('-', '').toUpperCase() === (renewableAlias[normalizedId] ?? normalizedId).replace('-', '').toUpperCase());
  const load = snapshot.loads.find(a => a.id.replace('-', '').toUpperCase() === (loadAlias[normalizedId] ?? normalizedId).replace('-', '').toUpperCase());
  const assetName = generator?.name ?? renewable?.name ?? load?.name ?? ({ MAIN: 'Main Building', RESEARCH: 'Research & Labs', WORKSHOP: 'Workshop & Utilities', FUEL: 'Fuel Tanks', BATTERY: 'Battery System' }[normalizedId] ?? assetId);
  const [activeSubTab, setActiveSubTab] = useState<'Overview' | 'Energy' | 'Loads' | 'Environment'>('Overview');

  return (
    <div className="absolute top-4 right-4 z-40 w-84 max-w-[calc(100vw-2rem)] bg-[#071123]/95 border border-cyan-800/60 rounded-2xl shadow-2xl shadow-black/80 backdrop-blur-xl overflow-hidden font-mono select-none">
      {/* Inspector Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#09162c] border-b border-cyan-900/40">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-cyan-600/30 flex items-center justify-center text-cyan-400">
            <Home className="w-3.5 h-3.5" />
          </div>
          <h4 className="font-display font-bold text-white text-sm tracking-wide">
            {assetName}
          </h4>
        </div>
        <button
          onClick={onClose}
          className="w-5 h-5 rounded hover:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center transition-all cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 bg-[#050c18] px-3 py-1.5 border-b border-slate-800 text-[11px]">
        {(['Overview', 'Energy', 'Loads', 'Environment'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveSubTab(tab)}
            className={`px-2.5 py-1 rounded-md font-semibold transition-all cursor-pointer ${
              activeSubTab === tab
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="p-3 space-y-2.5 text-xs">
        {/* Photographic preview of Maitri Station Habitat */}
        <div className="relative h-24 w-full rounded-xl overflow-hidden border border-slate-700/60 shadow-inner">
          <img
            src={mainBuildingPhoto}
            alt="Maitri Station Main Building"
            className="w-full h-full object-cover brightness-95"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#071123]/80 via-transparent to-transparent" />
        </div>

        {/* Telemetry Metrics Table */}
        <div className="space-y-1 text-xs">
          {activeSubTab === 'Overview' && <><MetricRow label="Status" value={generator?.status ?? renewable?.status ?? (load ? load.shedStatus : assetId === 'FUEL' ? 'NORMAL' : assetId === 'BATTERY' ? snapshot.battery.status : 'AVAILABLE')} /><MetricRow label="Current value" value={generator ? `${generator.currentOutputKw.toFixed(1)} kW` : renewable ? `${renewable.currentOutputKw.toFixed(1)} kW` : load ? `${load.currentLoadKw.toFixed(1)} kW` : assetId === 'FUEL' ? `${snapshot.fuel.currentVolumeLiters.toFixed(0)} L` : assetId === 'BATTERY' ? `${snapshot.battery.socPercent.toFixed(1)} % SoC` : '—'} /><MetricRow label="Priority / reserve" value={load?.priority ?? `${snapshot.reserve.targetReservePercent.toFixed(1)} %`} /></>}
          {activeSubTab === 'Energy' && <><MetricRow label="Power" value={generator ? `${generator.currentOutputKw.toFixed(1)} kW` : renewable ? `${renewable.currentOutputKw.toFixed(1)} kW` : load ? `${load.currentLoadKw.toFixed(1)} kW` : assetId === 'BATTERY' ? `${snapshot.battery.currentPowerKw.toFixed(1)} kW` : '—'} /><MetricRow label="Station generation" value={`${snapshot.powerBalance.totalGenerationKw.toFixed(1)} kW`} /><MetricRow label="Net balance" value={`${snapshot.powerBalance.netBalanceKw.toFixed(1)} kW`} /></>}
          {activeSubTab === 'Loads' && <>{(load ? [load] : snapshot.loads).map(l=><div key={l.id}><MetricRow label={l.name} value={`${l.currentLoadKw.toFixed(1)} kW · ${l.priority} · ${l.shedStatus}`} /></div>)}</>}
          {activeSubTab === 'Environment' && <><MetricRow label="Outdoor temperature" value={`${snapshot.weather.temperature.toFixed(1)} °C`} /><MetricRow label="Wind" value={`${snapshot.weather.windSpeed.toFixed(1)} m/s`} /><MetricRow label="Solar" value={`${snapshot.weather.solarRadiation.toFixed(1)} W/m²`} /></>}
        </div>

        {/* Action Link Button */}
        <button
          onClick={() => {
            onClose();
            setActiveTab('energy');
          }}
          className="w-full mt-1 py-1.5 rounded-xl bg-[#091e3e] hover:bg-cyan-900/60 border border-cyan-700/60 text-cyan-300 font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
        >
          <span>View Detailed Analytics</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

const MetricRow = ({label,value}:{label:string;value:string}) => <div className="flex items-center justify-between py-1 border-b border-slate-800/80"><span className="text-slate-400 text-[11px]">{label}</span><span className="text-white font-bold">{value}</span></div>;
