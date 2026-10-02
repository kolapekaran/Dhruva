import React, { useState } from 'react';
import { ArrowRight, CheckCircle2, Clock3, Crosshair, ShieldCheck, TriangleAlert } from 'lucide-react';
import { fetchMissionAutopilot, MissionAutopilotResult, recordDhruvaOperatorAction } from '../integration/api';
import { useStation } from '../integration/StationContext';

const postureTone: Record<string, string> = {
  NORMAL: 'map-normal', CONSERVATION: 'map-watch', CONTINGENCY: 'map-contingency', SURVIVAL: 'map-survival',
};

export const MissionAutopilotPanel: React.FC = () => {
  const { systemMode, backendConnected } = useStation();
  const [data, setData] = useState<MissionAutopilotResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionStatus, setActionStatus] = useState<string>('');
  const [actionLoading, setActionLoading] = useState(false);

  const record = async (action: 'APPROVE' | 'ACKNOWLEDGE') => {
    if (!data || systemMode !== 'ONLINE' || !backendConnected) return;
    setActionLoading(true);
    try {
      const saved = await recordDhruvaOperatorAction(data.decision_id, action, action === 'APPROVE' ? 'Approved advisory mission posture; no automatic equipment control.' : 'Acknowledged advisory mission plan.');
      setActionStatus(`${saved.action} recorded · ${new Date(saved.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
    } catch { setActionStatus('Operator audit write failed'); }
    finally { setActionLoading(false); }
  };

  const run = async () => {
    if (systemMode !== 'ONLINE' || !backendConnected) return;
    setLoading(true);
    try { setData(await fetchMissionAutopilot(168, 120)); } catch (e) { console.warn('Mission autopilot unavailable', e); setData(null); }
    finally { setLoading(false); }
  };

  return (
    <section className="cc-autopilot-card polar-interactive-card" aria-label="DHRUVA mission autopilot">
      <div className="cc-autopilot-head">
        <div>
          <div className="cc-section-title"><Crosshair className="w-4 h-4 inline mr-2" />MISSION AUTOPILOT · OPERATOR SUPERVISED</div>
          <div className="cc-section-subtitle">7-day mission planning · strategy switching · counterfactuals · approval gate</div>
        </div>
        <button className="cc-autopilot-run" onClick={() => void run()} disabled={loading || systemMode !== 'ONLINE' || !backendConnected}>
          {loading ? 'ASSESSING…' : data ? 'REFRESH MISSION PLAN' : 'RUN MISSION PLAN'}
        </button>
      </div>

      {!data ? (
        <div className="cc-autopilot-empty"><ShieldCheck /><div><b>Mission-level decision layer</b><span>Runs the complete chain: DATA → FORECAST → RISK → OPTIONS → CONSTRAINTS → SAFETY → OPERATOR APPROVAL.</span></div></div>
      ) : (
        <>
          <div className="cc-autopilot-top">
            <div className={`cc-autopilot-posture ${postureTone[data.current_posture]}`}><span>CURRENT POSTURE</span><strong>{data.current_posture}</strong><small>{data.worst_case.scenario.replaceAll('_', ' ')} · P10 {data.worst_case.p10_survival_hours}h</small></div>
            <div className="cc-autopilot-action"><span>DO NOW</span><b>{data.now}</b><small>{data.change_strategy_when}</small></div>
            <div className="cc-autopilot-action"><span>PREPARE FOR</span><b>{data.prepare_for}</b><small>Decision {data.decision_id}</small></div>
          </div>

          <div className="cc-autopilot-flow">
            {data.timeline.slice(0, 6).map((step, i) => <div key={step.window} className="cc-autopilot-step"><span>{step.window}</span><b>{step.action}</b>{i < 5 && <ArrowRight className="w-3 h-3" />}</div>)}
          </div>

          <div className="cc-autopilot-metrics">
            <div><span>DYNAMIC RESERVE</span><b>{data.decision_trace.dynamic_reserve_percent.toFixed(1)}%</b></div>
            <div><span>FORECAST CONFIDENCE</span><b>{data.decision_trace.forecast_confidence_percent.toFixed(0)}%</b></div>
            <div><span>SAFETY SHIELD</span><b>{data.decision_trace.safety_passed ? 'PASS' : 'REVIEW'}</b></div>
            <div><span>FIELD VALIDATION</span><b>NOT ESTABLISHED</b></div>
          </div>

          <div className="cc-autopilot-bottom">
            <div className="cc-autopilot-options">
              <span>STRATEGY OPTIONS</span>
              {data.strategy_options.map(option => <div key={option.strategy}><b>{option.strategy}</b><small>{option.action}</small><em>{option.approval_required ? 'OPERATOR APPROVAL' : 'MONITOR'}</em></div>)}
            </div>
            <div className="cc-autopilot-gate"><TriangleAlert /><b>NO AUTOMATIC EQUIPMENT CONTROL</b><span>Strategy changes remain operator-approved. This endpoint is advisory and state-preserving.</span><div><CheckCircle2 /> {data.operator_gate.approval_required_for_strategy_change ? 'Approval gate active' : 'Approval gate inactive'}</div><div className="cc-autopilot-operator-actions"><button disabled={actionLoading} onClick={() => void record('ACKNOWLEDGE')}>ACKNOWLEDGE</button><button disabled={actionLoading} onClick={() => void record('APPROVE')}>APPROVE ADVISORY</button></div>{actionStatus && <small className="cc-autopilot-audit">{actionStatus}</small>}</div>
          </div>
          <div className="cc-autopilot-note"><Clock3 />Counterfactual lab: {data.counterfactual_lab.map(x => String(x.scenario)).join(' · ')} · {data.provenance.data_status}</div>
        </>
      )}
    </section>
  );
};
