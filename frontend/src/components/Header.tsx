import React from 'react';
import {
  Home,
  Lightbulb,
  Zap,
  Sliders,
  FlaskConical,
  ShieldAlert,
  BarChart3,
  Bot,
  Settings,
  User,
} from 'lucide-react';
import { TabType } from '../types';
import { useStation } from '../integration/StationContext';

interface HeaderProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  onOpenProfile: () => void;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  onOpenProfile,
  onOpenSettings,
}) => {
  const { snapshot, systemMode, timeOffset, setIsStationBrainOpen, backendConnected, setSystemMode } = useStation();
  const navTabs: { id: TabType; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'command-center', label: 'COMMAND CENTER', icon: Home },
    { id: 'optimization', label: 'OPTIMIZATION & ADVISORY', icon: Lightbulb },
    { id: 'energy', label: 'ENERGY', icon: Zap },
    { id: 'assets-loads', label: 'ASSETS & LOADS', icon: Sliders },
    { id: 'simulator', label: 'SIMULATOR', icon: FlaskConical },
    { id: 'resilience', label: 'RESILIENCE', icon: ShieldAlert },
    { id: 'analytics', label: 'ANALYTICS', icon: BarChart3 },
  ];

  return (
    <header className="sticky top-0 z-50 w-full min-w-0 overflow-hidden bg-[#040b15]/95 backdrop-blur border-b border-cyan-950/70 text-slate-100 select-none">
      <div className="w-full min-w-0 px-4 sm:px-6 lg:px-8 py-2.5 flex items-center justify-between gap-4">
        {/* Left: Brand Identity */}
        <div className="flex items-center gap-3 cursor-pointer group" onClick={() => setActiveTab('command-center')}>
          <div className="relative w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-600 via-blue-700 to-indigo-900 p-0.5 shadow-lg shadow-cyan-900/30">
            <div className="w-full h-full bg-[#071322] rounded-[7px] flex items-center justify-center overflow-hidden">
              <svg viewBox="0 0 24 24" className="w-6 h-6 text-cyan-400 group-hover:scale-110 transition-transform" fill="currentColor">
                <path d="M12 2L2 20h20L12 2zm0 4.5l6.5 11.5h-13L12 6.5z" opacity="0.3" />
                <path d="M12 5L4.5 18h15L12 5zm-1 5.5l2 3.5h-4l2-3.5z" />
              </svg>
            </div>
            <div className="absolute -inset-0.5 bg-cyan-400/20 blur-sm -z-10 rounded-lg group-hover:bg-cyan-400/40 transition-all"></div>
          </div>
          <div className="flex flex-col">
            <span className="font-extrabold tracking-wider text-base sm:text-lg text-white drop-shadow-sm flex items-center gap-1.5 font-sans">
              DHRUVA
            </span>
            <span className="text-[11px] font-medium tracking-wide text-cyan-400/80 -mt-0.5">
              Maitri Station | Antarctica
            </span>
          </div>
        </div>

        {/* Center: 7 Main Navigation Tabs */}
        <nav className="hidden xl:flex items-center space-x-1.5">
          {navTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`nav-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-3.5 py-2 rounded-lg text-xs font-semibold tracking-wider flex items-center gap-2 transition-all duration-200 ${
                  isActive
                    ? 'bg-gradient-to-b from-cyan-900/60 to-blue-950/80 text-cyan-300 border border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.25)]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {isActive && (
                  <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 rounded-full"></span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right: Status, Clock, Settings & Profile */}
        <div className="flex items-center gap-3 sm:gap-4">
          {/* Explicit three-state operating mode */}
          <div className="hidden lg:flex items-center rounded-lg border border-slate-800 bg-[#06101d]/80 p-0.5 gap-0.5" title="Operating mode">
            <button onClick={() => setSystemMode('ONLINE')} className={`px-2 py-1 rounded text-[10px] font-semibold ${systemMode === 'ONLINE' ? 'bg-emerald-500/15 text-emerald-300' : 'text-slate-500 hover:text-slate-300'}`}>ONLINE</button>
            <button onClick={() => setSystemMode('OFFLINE')} className={`px-2 py-1 rounded text-[10px] font-semibold ${systemMode === 'OFFLINE' ? 'bg-slate-500/20 text-slate-200' : 'text-slate-500 hover:text-slate-300'}`}>OFFLINE</button>
            <button onClick={() => setSystemMode('SIMULATION')} className={`px-2 py-1 rounded text-[10px] font-semibold ${systemMode === 'SIMULATION' ? 'bg-cyan-500/15 text-cyan-300' : 'text-slate-500 hover:text-slate-300'}`}>SIMULATION</button>
          </div>
          <div className={`flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium ${
            systemMode === 'SIMULATION' ? 'bg-cyan-950/40 border border-cyan-500/30 text-cyan-300' :
            systemMode === 'OFFLINE' ? 'bg-slate-900/80 border border-slate-600/50 text-slate-300' :
            'bg-emerald-950/40 border border-emerald-500/30 text-emerald-400'
          }`}>
            <span className={`h-2 w-2 rounded-full ${systemMode === 'SIMULATION' ? 'bg-cyan-400' : systemMode === 'OFFLINE' ? 'bg-slate-400' : backendConnected ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
            <span className="hidden sm:inline font-mono">{systemMode === 'SIMULATION' ? 'Simulation' : systemMode === 'OFFLINE' ? 'Offline · Cached' : backendConnected ? 'Online · Live' : 'Online · Reconnecting'}</span>
          </div>

          {/* Time */}
          <div className="hidden md:flex flex-col text-right font-mono text-[11px] text-slate-400">
            <span className="text-slate-300">{new Date(snapshot.systemTime).toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })}</span>
            <span className="text-cyan-400/90 font-medium">{new Date(snapshot.systemTime).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })} (UTC){timeOffset > 0 ? ` · +${timeOffset}h projection` : ''}</span>
          </div>

          {/* Station Brain */}
          <button
            id="header-station-brain-btn"
            onClick={() => setIsStationBrainOpen(true)}
            title="Open Station Brain"
            className="p-2 rounded-lg text-cyan-300 hover:text-white hover:bg-cyan-950/70 border border-cyan-800/60 transition-colors"
          >
            <Bot className="w-4 h-4" />
          </button>

          {/* Quick Settings Button */}
          <button
            id="header-settings-btn"
            onClick={onOpenSettings}
            title="System Settings"
            className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-900/80 border border-slate-800 transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>

          {/* User Profile Avatar */}
          <button
            id="header-profile-btn"
            onClick={onOpenProfile}
            title="Operator profile"
            className="relative w-9 h-9 rounded-full bg-gradient-to-tr from-cyan-700 via-blue-600 to-indigo-500 p-0.5 hover:ring-2 hover:ring-cyan-400/80 transition-all flex items-center justify-center cursor-pointer shadow-md"
          >
            <div className="w-full h-full rounded-full bg-[#081528] flex items-center justify-center font-bold text-sm text-cyan-200">
              K
            </div>
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-[#040b15]"></span>
          </button>
        </div>
      </div>

      {/* Mobile / Tablet Horizontal Navigation Scroll */}
      <div className="xl:hidden overflow-x-auto flex items-center px-4 py-2 gap-1.5 border-t border-cyan-950/40 bg-[#06101d]/90 no-scrollbar">
        {navTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={`m-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`whitespace-nowrap px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
                isActive
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/50'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
    </header>
  );
};
