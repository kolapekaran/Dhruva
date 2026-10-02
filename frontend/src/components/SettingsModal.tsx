import React, { useState } from 'react';
import {
  Settings,
  X,
  Sliders,
  Shield,
  Eye,
  Bell,
  Gauge,
  Check,
  RotateCcw,
  Sparkles,
} from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [reserveTarget, setReserveTarget] = useState(20);
  const [autoFailover, setAutoFailover] = useState(true);
  const [showFlowLines, setShowFlowLines] = useState(true);
  const [showBuildingLabels, setShowBuildingLabels] = useState(true);
  const [soundAlerts, setSoundAlerts] = useState(false);
  const [aiAdvisoryMode, setAiAdvisoryMode] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [savedSuccess, setSavedSuccess] = useState(false);
  React.useEffect(() => { try { const raw=localStorage.getItem('polar_ems_settings'); if(raw){ const v=JSON.parse(raw); if(v.reserveTarget!=null)setReserveTarget(v.reserveTarget); if(v.autoFailover!=null)setAutoFailover(v.autoFailover); if(v.showFlowLines!=null)setShowFlowLines(v.showFlowLines); if(v.showBuildingLabels!=null)setShowBuildingLabels(v.showBuildingLabels); if(v.soundAlerts!=null)setSoundAlerts(v.soundAlerts); if(v.aiAdvisoryMode)setAiAdvisoryMode(v.aiAdvisoryMode); } } catch {} }, []);

  if (!isOpen) return null;

  const handleSave = () => {
    localStorage.setItem('polar_ems_settings', JSON.stringify({ reserveTarget, autoFailover, showFlowLines, showBuildingLabels, soundAlerts, aiAdvisoryMode }));
    window.dispatchEvent(new CustomEvent('polar-ems-settings-changed'));
    setSavedSuccess(true);
    setTimeout(() => { setSavedSuccess(false); onClose(); }, 1000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-[#061224] border border-cyan-500/50 rounded-2xl shadow-2xl overflow-hidden text-slate-200">
        {/* Header */}
        <div className="px-6 py-4 bg-cyan-950/60 border-b border-cyan-800/40 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-cyan-500/20 text-cyan-400">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-sans">
                DHRUVA Station Settings
              </h2>
              <p className="text-xs text-cyan-400/80 font-mono">
                Local UI preferences & EMS advisory policy
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto font-sans text-xs">
          {/* Microgrid Resilience Constraints */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-bold text-cyan-300">
              <Shield className="w-4 h-4 text-cyan-400" />
              <span>Microgrid Safety & Reserve Constraints</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#030914] border border-cyan-950 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-200">Minimum Dynamic Reserve</span>
                  <p className="text-[11px] text-slate-400">
                    Local advisory floor used when requesting the backend EMS strategy; it does not rewrite station hardware limits.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min="15"
                    max="35"
                    value={reserveTarget}
                    onChange={(e) => setReserveTarget(Number(e.target.value))}
                    className="w-24 accent-cyan-400"
                  />
                  <span className="font-mono font-bold text-cyan-300 w-10 text-right">
                    {reserveTarget}%
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-cyan-950/60">
                <div>
                  <span className="font-semibold text-slate-200">Diesel N+1 Auto-Failover</span>
                  <p className="text-[11px] text-slate-400">
                    Auto-spin standby generator DG2 if online DG1 trips
                  </p>
                </div>
                <button
                  onClick={() => setAutoFailover(!autoFailover)}
                  className={`w-11 h-6 rounded-full p-1 transition-all ${
                    autoFailover ? 'bg-cyan-600' : 'bg-slate-700'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white transition-transform ${
                      autoFailover ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  ></div>
                </button>
              </div>
            </div>
          </div>

          {/* Digital Twin 3D View Settings */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-bold text-cyan-300">
              <Eye className="w-4 h-4 text-cyan-400" />
              <span>Digital Twin Rendering & Telemetry Overlays</span>
            </div>

            <div className="p-3.5 rounded-xl bg-[#030914] border border-cyan-950 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-200">Animated Energy Conduit Conduits</span>
                  <p className="text-[11px] text-slate-400">
                    Show pulsing directional energy flow vectors over real station terrain
                  </p>
                </div>
                <button
                  onClick={() => setShowFlowLines(!showFlowLines)}
                  className={`w-11 h-6 rounded-full p-1 transition-all ${
                    showFlowLines ? 'bg-cyan-600' : 'bg-slate-700'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white transition-transform ${
                      showFlowLines ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  ></div>
                </button>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-cyan-950/60">
                <div>
                  <span className="font-semibold text-slate-200">Interactive Station Node Badges</span>
                  <p className="text-[11px] text-slate-400">
                    Pin real-time kW badges over station buildings, wind turbines, and solar arrays
                  </p>
                </div>
                <button
                  onClick={() => setShowBuildingLabels(!showBuildingLabels)}
                  className={`w-11 h-6 rounded-full p-1 transition-all ${
                    showBuildingLabels ? 'bg-cyan-600' : 'bg-slate-700'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white transition-transform ${
                      showBuildingLabels ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  ></div>
                </button>
              </div>
            </div>
          </div>

          {/* Audible Alert Policy */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-bold text-cyan-300"><Bell className="w-4 h-4 text-cyan-400" /><span>Operator Alerts</span></div>
            <div className="p-3.5 rounded-xl bg-[#030914] border border-cyan-950 flex items-center justify-between">
              <div><span className="font-semibold text-slate-200">Sound Alerts</span><p className="text-[11px] text-slate-400">Enable local alert cues for critical UI events.</p></div>
              <button onClick={() => setSoundAlerts(!soundAlerts)} className={`w-11 h-6 rounded-full p-1 transition-all ${soundAlerts ? 'bg-cyan-600' : 'bg-slate-700'}`}><div className={`w-4 h-4 rounded-full bg-white transition-transform ${soundAlerts ? 'translate-x-5' : 'translate-x-0'}`}/></button>
            </div>
          </div>

          {/* AI Advisory Aggressiveness */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-bold text-cyan-300">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>AI Optimizer Engine Policy</span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'conservative', title: 'Conservative', desc: 'Bias decisions toward larger reserve margins' },
                { id: 'balanced', title: 'Balanced', desc: 'Balance reliability, fuel and renewable use' },
                { id: 'aggressive', title: 'Max Green', desc: 'Increase renewable-use emphasis within constraints' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setAiAdvisoryMode(m.id as any)}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    aiAdvisoryMode === m.id
                      ? 'bg-cyan-950/80 border-cyan-400 text-cyan-200 shadow-md'
                      : 'bg-[#030914] border-cyan-950 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="font-bold block text-xs">{m.title}</span>
                  <span className="text-[10px] text-slate-400 leading-tight block mt-0.5">{m.desc}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-black/40 border-t border-cyan-900/60 flex items-center justify-between">
          <button
            onClick={() => {
              if (!window.confirm('Reset DHRUVA local preferences and advisory policy to defaults?')) return;
              setReserveTarget(20);
              setAutoFailover(true);
              setShowFlowLines(true);
              setShowBuildingLabels(true);
              setSoundAlerts(false);
              setAiAdvisoryMode('balanced');
            }}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset to Polar Defaults</span>
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-black font-semibold text-xs flex items-center gap-1.5 shadow-lg shadow-cyan-600/30 transition-all cursor-pointer"
            >
              {savedSuccess ? (
                <>
                  <Check className="w-4 h-4 text-black" />
                  <span>Config Applied!</span>
                </>
              ) : (
                <span>Save Preferences & Policy</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
