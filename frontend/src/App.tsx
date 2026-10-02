/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { ProfileModal } from './components/ProfileModal';
import { SettingsModal } from './components/SettingsModal';
import { AssetDetailModal } from './components/AssetDetailModal';

import { CommandCenterTab } from './tabs/01-command-center/CommandCenterTab';
import { OptimizationTab } from './tabs/02-optimization-advisory/OptimizationTab';
import { EnergyTab } from './tabs/03-energy/EnergyTab';
import { AssetsLoadsTab } from './tabs/04-assets-loads/AssetsLoadsTab';
import { SimulatorTab } from './tabs/05-simulator/SimulatorTab';
import { ResilienceTab } from './tabs/06-resilience/ResilienceTab';
import { AnalyticsTab } from './tabs/07-analytics/AnalyticsTab';

import { TabType, StationNode, AssetRecord } from './types';

import { StationProvider, useStation } from './integration/StationContext';
import { StationBrainModal } from './components/advanced/StationBrainModal';

function AppContent() {
  const { snapshot, activeTab, setActiveTab, startupReady, startupLoading, enterMissionControl, backendConnected } = useStation();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Asset detail modal
  const [selectedAsset, setSelectedAsset] = useState<AssetRecord | null>(null);
  const [focusedCard, setFocusedCard] = useState('');

  useEffect(() => {
    const onCardClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      const card = target?.closest<HTMLElement>('.polar-interactive-card');
      if (!card) return;
      document.querySelectorAll('.polar-interactive-card.polar-card-selected').forEach((node) => node.classList.remove('polar-card-selected'));
      document.querySelectorAll('.polar-interactive-card.polar-card-pulse').forEach((node) => node.classList.remove('polar-card-pulse'));
      card.classList.add('polar-card-selected', 'polar-card-pulse');
      window.setTimeout(() => card.classList.remove('polar-card-pulse'), 650);
      const label = card.querySelector('h1,h2,h3,h4,b,strong,[data-card-title]')?.textContent?.trim()
        || card.textContent?.trim().split('\n').map((v) => v.trim()).filter(Boolean)[0]
        || 'Station component';
      setFocusedCard(label.slice(0, 58));
    };
    document.addEventListener('click', onCardClick);
    return () => document.removeEventListener('click', onCardClick);
  }, []);


  const handleOpenAssetModal = (asset: AssetRecord) => {
    setSelectedAsset(asset);
  };

  const [startupAutoRotate, setStartupAutoRotate] = useState(true);

  useEffect(() => {
    if (startupReady) return;
    const postRotationMode = () => {
      const frame = document.querySelector<HTMLIFrameElement>('iframe[data-startup-digital-twin]');
      frame?.contentWindow?.postMessage({ type: 'POLAR_DIGITAL_TWIN_ROTATION_MODE', autoRotate: startupAutoRotate }, '*');
      frame?.contentWindow?.postMessage({ type: 'POLAR_DIGITAL_TWIN_STARTUP_LABELS', show: false }, '*');
    };
    postRotationMode();
    const timer = window.setTimeout(postRotationMode, 500);
    return () => window.clearTimeout(timer);
  }, [startupReady, startupAutoRotate]);

  if (!startupReady) {
    return (
      <div className="fixed inset-0 overflow-hidden bg-[#01050d] text-slate-100 font-sans">
        <iframe
          title="Maitri Research Station 3D Digital Twin"
          data-startup-digital-twin
          src="/station-3d/polar-station-3d.html?startup=1"
          className="absolute inset-0 h-full w-full border-0"
          loading="eager"
          allow="fullscreen"
          onLoad={(event) => {
            event.currentTarget.contentWindow?.postMessage({ type: 'POLAR_DIGITAL_TWIN_ROTATION_MODE', autoRotate: startupAutoRotate }, '*');
            event.currentTarget.contentWindow?.postMessage({ type: 'POLAR_DIGITAL_TWIN_STARTUP_LABELS', show: false }, '*');
          }}
        />
        <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(180deg,rgba(1,5,13,.72)_0%,rgba(1,5,13,.06)_28%,rgba(1,5,13,.10)_62%,rgba(1,5,13,.88)_100%)]" />
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_50%_45%,transparent_28%,rgba(1,5,13,.38)_100%)]" />

        <header className="absolute left-0 right-0 top-0 z-20 flex items-start justify-between px-6 py-6 sm:px-8 sm:py-8">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[.32em] text-cyan-300">DHRUVA · MAITRI RESEARCH STATION</div>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-white drop-shadow-[0_4px_20px_rgba(0,0,0,.55)] sm:text-5xl">Antarctic Mission Control</h1>
            <p className="mt-1 max-w-xl text-xs text-slate-300/90 sm:text-sm">Live 3D operational model · Schirmacher Oasis, Antarctica</p>
          </div>
          <div className={`rounded-full border px-3 py-2 text-[9px] font-mono tracking-widest backdrop-blur-xl ${backendConnected ? 'border-emerald-400/40 bg-emerald-950/60 text-emerald-300' : 'border-amber-400/40 bg-amber-950/50 text-amber-300'}`}>● {backendConnected ? 'LIVE LINK' : 'LOCAL BASELINE'}</div>
        </header>

        <div className="startup-left-panel absolute left-6 bottom-6 z-30 max-w-md sm:left-8 sm:bottom-8">
          <div className="rounded-2xl border border-white/10 bg-[#020914]/72 px-5 py-4 shadow-[0_15px_55px_rgba(0,0,0,.4)] backdrop-blur-xl">
            <div className="text-[9px] font-mono uppercase tracking-[.25em] text-cyan-300">MAITRI RESEARCH STATION</div>
            <p className="mt-2 text-xs leading-5 text-slate-300">Indian polar research station supporting scientific operations, logistics, weather observation and essential station services.</p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-cyan-900/70 bg-black/20 p-2"><span className="text-[8px] font-mono text-slate-500">LOAD</span><b className="mt-1 block text-sm text-white">{snapshot.powerBalance.totalLoadKw.toFixed(0)} kW</b></div>
              <div className="rounded-lg border border-cyan-900/70 bg-black/20 p-2"><span className="text-[8px] font-mono text-slate-500">BATTERY</span><b className="mt-1 block text-sm text-white">{snapshot.battery.socPercent.toFixed(0)}%</b></div>
              <div className="rounded-lg border border-cyan-900/70 bg-black/20 p-2"><span className="text-[8px] font-mono text-slate-500">FUEL</span><b className="mt-1 block text-sm text-white">{snapshot.fuel.fillPercent.toFixed(0)}%</b></div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <div className="flex overflow-hidden rounded-xl border border-cyan-400/35 bg-[#020a14]/90 p-1 shadow-[0_10px_35px_rgba(0,0,0,.35)] backdrop-blur-xl">
              <button type="button" onClick={() => setStartupAutoRotate(true)} className={`px-4 py-2 text-[10px] font-black tracking-widest transition ${startupAutoRotate ? 'bg-cyan-400 text-[#01101a]' : 'text-slate-300 hover:bg-cyan-400/10'}`}>AUTO ROTATE</button>
              <button type="button" onClick={() => setStartupAutoRotate(false)} className={`px-4 py-2 text-[10px] font-black tracking-widest transition ${!startupAutoRotate ? 'bg-cyan-400 text-[#01101a]' : 'text-slate-300 hover:bg-cyan-400/10'}`}>MANUAL</button>
            </div>
            <span className="hidden text-[9px] font-mono text-slate-400 sm:inline">Drag to inspect</span>
          </div>
        </div>

        <aside className="startup-entry-panel absolute bottom-6 right-6 z-30 w-[min(390px,calc(100vw-3rem))] rounded-2xl border border-cyan-400/25 bg-[#020a14]/88 p-5 shadow-[0_18px_70px_rgba(0,0,0,.5)] backdrop-blur-xl sm:bottom-8 sm:right-8">
          <div className="flex items-center justify-between">
            <div className="text-[9px] font-mono uppercase tracking-[.22em] text-slate-500">Mission entry</div>
            <div className="text-[9px] font-mono text-cyan-300">BASELINE READY</div>
          </div>
          <div className="mt-3 text-xl font-black text-white">Maitri Research Station</div>
          <div className="mt-1 text-xs text-slate-400">Schirmacher Oasis · Antarctica · Indian polar programme</div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded-lg border border-slate-800 bg-black/20 px-3 py-2"><span className="text-slate-500">Coordinates</span><b className="mt-1 block text-slate-200">70.7505° S · 11.7171° E</b></div>
            <div className="rounded-lg border border-slate-800 bg-black/20 px-3 py-2"><span className="text-slate-500">Operating mode</span><b className="mt-1 block text-emerald-300">ONLINE · LIVE</b></div>
          </div>
          <button type="button" onClick={enterMissionControl} className="mt-4 w-full rounded-xl border border-cyan-300 bg-cyan-400/15 px-5 py-3.5 text-sm font-black uppercase tracking-[.16em] text-cyan-200 shadow-[0_0_35px_rgba(0,200,255,.12)] transition hover:bg-cyan-400 hover:text-[#01101a]">Enter Mission Control →</button>
          <div className="mt-2 text-center text-[9px] font-mono text-slate-500">Live telemetry and AI intelligence continue hydrating in the background.</div>
        </aside>
      </div>
    );
  }

  const handleOpenNodeModal = (node: StationNode) => {
    const generator = snapshot.generators.find(g => node.name.toLowerCase().includes(g.name.toLowerCase().replace('diesel generator ', '')) || node.name.toLowerCase().includes('diesel'));
    const renewable = snapshot.renewables.find(r => node.name.toLowerCase().includes(r.type === 'Wind Turbine' ? 'wind' : 'solar'));
    const load = snapshot.loads.find(l => node.name.toLowerCase().includes(l.name.toLowerCase()) || (l.name === 'Research & Labs' && node.name.toLowerCase().includes('research')));
    const source: any = generator || renewable || load;
    if (source) {
      const isGen = 'capacityKw' in source && 'healthPercent' in source;
      setSelectedAsset({
        id: source.id.replace('-', ''), name: source.name, type: source.type,
        status: source.status === 'ONLINE' ? 'Online' : source.status === 'STANDBY' ? 'Standby' : source.status === 'OFFLINE' ? 'Maintenance' : 'Online',
        capacity: isGen ? `${source.capacityKw.toFixed(0)} kW` : ('capacityKw' in source ? `${source.capacityKw.toFixed(0)} kW` : `${source.currentLoadKw.toFixed(0)} kW`),
        currentOutput: isGen || 'currentOutputKw' in source ? `${source.currentOutputKw.toFixed(0)} kW` : `${source.currentLoadKw.toFixed(0)} kW`,
        efficiency: isGen ? `${(source.electricalEfficiency * 100).toFixed(0)}%` : 'Modelled',
        health: isGen ? `${source.healthPercent.toFixed(0)}%` : 'Unknown',
        nextMaintenance: isGen ? `${source.nextMaintenanceHours.toFixed(0)} hrs` : '—',
        fuelRate: isGen ? `${source.fuelConsumptionLhr.toFixed(1)} L/hr` : undefined,
        runtime: isGen ? `${source.runtimeHours.toFixed(0)} hrs` : undefined,
      });
      return;
    }
    setSelectedAsset(null);
  };
  return (
    <div className="mission-ui-shell min-h-screen w-full min-w-0 overflow-x-hidden bg-[#020712] text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-black">
      {/* Background radial ambiance */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#072444]/25 via-[#020712]/70 to-[#020712] -z-10"></div>

      {/* Main App Navigation Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenProfile={() => setIsProfileOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Primary Dashboard Content Area */}
      <main className="flex-1 w-full px-0 py-0">
        {activeTab === 'command-center' && (
          <CommandCenterTab
            onNavigateTab={setActiveTab}
            onOpenAnalyticsModal={handleOpenNodeModal}
          />
        )}

        {activeTab === 'optimization' && (
          <OptimizationTab onNavigateTab={setActiveTab} />
        )}

        {activeTab === 'energy' && (
          <EnergyTab
            onNavigateTab={setActiveTab}
            onOpenAnalyticsModal={handleOpenNodeModal}
          />
        )}

        {activeTab === 'assets-loads' && (
          <AssetsLoadsTab
            onOpenAssetDetail={handleOpenAssetModal}
            onOpenNodeDetail={handleOpenNodeModal}
          />
        )}

        {activeTab === 'simulator' && <SimulatorTab />}

        {activeTab === 'resilience' && <ResilienceTab />}

        {activeTab === 'analytics' && <AnalyticsTab />}
      </main>

      {focusedCard && activeTab !== 'resilience' && (
        <div className="polar-focus-hud" role="status" aria-live="polite">
          <span className="polar-focus-dot" />
          <div><small>FOCUS LOCK</small><strong>{focusedCard}</strong></div>
          <button type="button" aria-label="Clear focused card" onClick={() => { document.querySelectorAll('.polar-interactive-card.polar-card-selected').forEach((node) => node.classList.remove('polar-card-selected')); setFocusedCard(''); }}>×</button>
        </div>
      )}

      {/* Footer is intentionally omitted on the Command Center; it is a full-screen mission-control surface. */}
      {activeTab !== 'command-center' && <Footer />}

      {/* Modals */}
      <ProfileModal
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        onOpenSettings={() => {
          setIsProfileOpen(false);
          setIsSettingsOpen(true);
        }}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      <AssetDetailModal
        asset={selectedAsset}
        onClose={() => setSelectedAsset(null)}
      />
      <StationBrainModal />
    </div>
  );
}

export default function App() {
  return <StationProvider><AppContent /></StationProvider>;
}
