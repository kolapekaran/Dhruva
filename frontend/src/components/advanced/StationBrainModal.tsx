import React, { useEffect, useState } from 'react';
import { useStation } from '../../integration/StationContext';
import { askStationBrain } from '../../integration/api';
import {
  Bot,
  X,
  Send,
  Sparkles,
  Zap,
  Flame,
  ShieldAlert,
  BatteryCharging,
  TrendingUp,
  Cpu,
  CornerDownLeft,
} from 'lucide-react';

export const StationBrainModal: React.FC = () => {
  const { isStationBrainOpen, setIsStationBrainOpen, snapshot, strategy, resilience } = useStation();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<{ sender: 'user' | 'brain'; text: string; facts?: string[] }[]>([]);

  useEffect(() => {
    if (!isStationBrainOpen || messages.length > 0) return;
    const balance = snapshot.powerBalance.netBalanceKw;
    setMessages([{
      sender: 'brain',
      text: `Energy Copilot synchronized with the current Maitri Digital Twin. Current balance is ${balance >= 0 ? '+' : ''}${balance.toFixed(1)} kW, battery is ${snapshot.battery.status.toLowerCase()} at ${snapshot.battery.socPercent.toFixed(1)}% SoC, and fuel is ${snapshot.fuel.currentVolumeLiters.toFixed(0)} L. Ask for a dispatch explanation, contingency result or forecast-derived metric.`,
      facts: [
        `Net Balance: ${balance >= 0 ? '+' : ''}${balance.toFixed(1)} kW`,
        `Battery: ${snapshot.battery.socPercent.toFixed(1)}% SoC`,
        `Fuel: ${snapshot.fuel.currentVolumeLiters.toFixed(0)} L`,
        `Data: ${snapshot.provenance.powerTelemetrySource}`,
      ],
    }]);
  }, [isStationBrainOpen, messages.length, snapshot]);

  if (!isStationBrainOpen) return null;

  const quickQuestions = [
    'Why did the system start diesel?',
    'What happens if DG-01 fails?',
    'How much heating demand can heat recovery offset?',
    'Why is the dynamic reserve target increasing?',
    'Why is the battery charging?',
    'How much fuel do we expect to consume in 24 hours?',
  ];

  const handleSend = async (textToSend?: string) => {
    const prompt = textToSend || query;
    if (!prompt.trim() || loading) return;

    setMessages((prev) => [...prev, { sender: 'user', text: prompt }]);
    setQuery('');
    setLoading(true);

    try {
      const response = await askStationBrain(prompt);
      setMessages((prev) => [
        ...prev,
        { sender: 'brain', text: response.answer, facts: response.groundedFacts },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'brain',
          text: 'Energy Copilot could not obtain a backend answer within the allowed response window. No additional operational claim is being inferred from missing data.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-[#081224] border border-cyan-500/40 rounded-2xl shadow-2xl shadow-cyan-950/80 flex flex-col max-h-[85vh] overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-gradient-to-r from-cyan-950/80 via-[#0a1832] to-[#071328] border-b border-cyan-900/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-400/40 flex items-center justify-center text-cyan-400 shadow-inner">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display font-bold text-white text-base tracking-wide">
                  POLAR ENERGY COPILOT
                </h3>
                <span className="px-2 py-0.5 rounded-full bg-cyan-950 border border-cyan-500/50 text-[10px] font-mono text-cyan-300 font-semibold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  Twin-Grounded AI
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Authoritative dispatch rationale & contingency advisory for Maitri Station
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsStationBrainOpen(false)}
            className="w-8 h-8 rounded-lg bg-slate-800/60 hover:bg-slate-750 text-slate-400 hover:text-white flex items-center justify-center transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Conversation Message List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 font-sans text-sm">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[88%] rounded-2xl px-4 py-3 leading-relaxed shadow-sm ${
                  m.sender === 'user'
                    ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white rounded-br-none'
                    : 'bg-[#0b1b36] border border-cyan-900/50 text-slate-200 rounded-bl-none'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.text}</div>

                {m.facts && m.facts.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-cyan-900/40 text-[11px] font-mono text-cyan-300 grid grid-cols-2 gap-2">
                    {m.facts.map((fact, fIdx) => (
                      <div key={fIdx} className="flex items-center gap-1.5 bg-cyan-950/60 px-2 py-1 rounded border border-cyan-800/30">
                        <Sparkles className="w-3 h-3 text-cyan-400 shrink-0" />
                        <span className="truncate">{fact}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <span className="text-[10px] text-slate-500 font-mono mt-1 px-1">
                {m.sender === 'user' ? 'Operator' : 'Energy Copilot • Authoritative'}
              </span>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono p-2">
              <Sparkles className="w-4 h-4 animate-spin text-cyan-300" />
              <span>Analyzing Digital Twin physical constraints & telemetry...</span>
            </div>
          )}
        </div>

        {/* Quick Grounded Question Pills */}
        <div className="px-6 py-2.5 bg-[#050e1c] border-t border-slate-800/60 max-h-24 overflow-y-auto">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-slate-500 font-mono whitespace-nowrap">Suggested:</span>
            {quickQuestions.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(q)}
                className="max-w-full text-[11px] font-mono whitespace-normal text-left px-2.5 py-1 rounded-full bg-slate-900 hover:bg-cyan-950 text-slate-300 hover:text-cyan-300 border border-slate-800 hover:border-cyan-700/50 transition-all cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Query Input Box */}
        <div className="p-4 bg-[#061021] border-t border-cyan-950 flex items-center gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask anything about Maitri microgrid, DG dispatch, heat recovery, storm resilience..."
            className="flex-1 bg-[#09172f] border border-slate-700/80 focus:border-cyan-400 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none transition-all"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !query.trim()}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 text-white font-semibold flex items-center gap-2 shadow-md shadow-cyan-950 transition-all cursor-pointer"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline text-xs">Query</span>
          </button>
        </div>
      </div>
    </div>
  );
};
