import React from 'react';
import { useStation } from '../integration/StationContext';
import {
  User,
  Shield,
  MapPin,
  Clock,
  CheckCircle,
  Key,
  LogOut,
  X,
  Radio,
  FileText,
  Activity,
  Award,
} from 'lucide-react';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({
  isOpen,
  onClose,
  onOpenSettings,
}) => {
  const { snapshot, strategy, appliedStrategyCode } = useStation();
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-[#071324] border border-cyan-500/40 rounded-2xl shadow-2xl overflow-hidden text-slate-200">
        {/* Banner Header with Polar Ice Motif */}
        <div className="relative h-28 bg-gradient-to-r from-blue-900 via-cyan-900 to-indigo-950 p-4 flex justify-between items-start">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(6,182,212,0.3),transparent)]"></div>
          <div className="relative z-10 flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-400/40 text-[10px] font-mono text-cyan-300 font-semibold tracking-wider uppercase">
              DHRUVA Operator
            </span>
          </div>
          <button
            onClick={onClose}
            className="relative z-10 p-1.5 rounded-full bg-black/40 hover:bg-white/20 text-slate-300 hover:text-white transition-all cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Avatar & User Details */}
        <div className="relative px-6 pb-6 pt-0">
          <div className="flex justify-between items-end -mt-12 mb-4">
            <div className="relative w-20 h-20 rounded-2xl bg-[#040d1a] border-2 border-cyan-400 p-1 shadow-xl flex items-center justify-center">
              <div className="w-full h-full rounded-xl bg-gradient-to-br from-cyan-600 to-blue-800 flex items-center justify-center font-extrabold text-2xl text-white font-mono">
                K
              </div>
              <span className="absolute bottom-1 right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-[#071324] shadow"></span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  onClose();
                  onOpenSettings();
                }}
                className="px-3 py-1.5 rounded-lg bg-cyan-900/50 hover:bg-cyan-800/80 border border-cyan-500/50 text-xs font-semibold text-cyan-200 transition-all cursor-pointer"
              >
                Station Settings
              </button>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-white font-sans">Karan Kolape</h2>
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 font-mono">
                ACTIVE DUTY
              </span>
            </div>
            <p className="text-sm text-cyan-400/90 font-medium">Chief Polar Systems Engineer & Microgrid Architect</p>
            <p className="text-xs text-slate-400 font-mono mt-0.5">kolapekaran710@gmail.com</p>
          </div>

          {/* Expedition Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 mt-5 font-mono text-xs">
            <div className="p-2.5 rounded-xl bg-[#040d1a] border border-cyan-950/80">
              <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                <span>Station Base</span>
              </div>
              <span className="font-semibold text-white">Maitri Station</span>
              <p className="text-[10px] text-slate-400">Schirmacher Oasis</p>
            </div>

            <div className="p-2.5 rounded-xl bg-[#040d1a] border border-cyan-950/80">
              <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
                <Shield className="w-3.5 h-3.5 text-amber-400" />
                <span>Clearance</span>
              </div>
              <span className="font-semibold text-amber-300">Operator Profile</span>
              <p className="text-[10px] text-slate-400">Backend authorization not connected</p>
            </div>

            <div className="p-2.5 rounded-xl bg-[#040d1a] border border-cyan-950/80 col-span-2 sm:col-span-1">
              <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
                <Award className="w-3.5 h-3.5 text-emerald-400" />
                <span>Expedition</span>
              </div>
              <span className="font-semibold text-emerald-300">44th ISEA</span>
              <p className="text-[10px] text-slate-400">Wintering Crew</p>
            </div>
          </div>

          {/* Recent Shift Activity Log */}
          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-cyan-400" />
                Recent Command Log
              </span>
              <span className="text-[11px] font-mono text-cyan-400">Shift 08:00 - 20:00 (LT)</span>
            </div>
            <div className="space-y-2 font-mono text-xs">
              <div className="p-2 rounded-lg bg-[#040c19] border border-cyan-900/40 flex items-start gap-2">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <span className="text-slate-200">{appliedStrategyCode ? `Applied EMS Strategy: ${appliedStrategyCode}` : 'No EMS strategy applied in this session'}</span>
                  <span className="block text-[10px] text-slate-400">{snapshot.systemTime} • Backend strategy {strategy?.recommendedStrategy?.code ?? 'unavailable'}</span>
                </div>
              </div>
              <div className="p-2 rounded-lg bg-[#040c19] border border-cyan-900/40 flex items-start gap-2">
                <CheckCircle className="w-3.5 h-3.5 text-cyan-400 mt-0.5 shrink-0" />
                <div>
                  <span className="text-slate-200">No backend command event recorded for this period</span>
                  <span className="block text-[10px] text-slate-400">{snapshot.systemTime} • Dynamic reserve {snapshot.reserve.currentReservePercent.toFixed(0)}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Footer Action */}
          <div className="mt-6 flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-black font-semibold text-xs transition-all cursor-pointer shadow-md shadow-cyan-600/30"
            >
              Close Profile
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
