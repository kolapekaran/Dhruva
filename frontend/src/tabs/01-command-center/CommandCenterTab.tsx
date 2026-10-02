import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BatteryCharging, ChevronRight, CloudSnow, Fuel, Lightbulb, Play, ShieldCheck, Wind, Zap, Gauge, ThermometerSnowflake, Bell, Eye , Maximize2, Minimize2} from 'lucide-react';
import { DigitalTwinStation } from '../../components/DigitalTwinStation';
import { StationNode, TabType } from '../../types';
import { useStation } from '../../integration/StationContext';
import { MissionSurvivalPanel } from '../../components/MissionSurvivalPanel';
import { MissionAutopilotPanel } from '../../components/MissionAutopilotPanel';
import { UltimateAICorePanel } from '../../components/UltimateAICorePanel';

interface CommandCenterTabProps {
  onNavigateTab: (tab: TabType) => void;
  onOpenAnalyticsModal: (node: StationNode) => void;
}



const pct = (value: number) => `${Math.max(0, Math.min(100, value)).toFixed(0)}%`;

type IntelTab = 'operations' | 'alerts' | 'weather';

export const CommandCenterTab: React.FC<CommandCenterTabProps> = ({ onNavigateTab, onOpenAnalyticsModal }) => {
  const { snapshot, strategy, timeOffset, setTimeOffset, backendConnected } = useStation();
  const [selectedKpi, setSelectedKpi] = useState('CURRENT LOAD');
  const [digitalTwinMaximized, setDigitalTwinMaximized] = useState(false);
  const [digitalTwinAutoRotate, setDigitalTwinAutoRotate] = useState(true);
  useEffect(() => {
    const sendRotationMode = () => {
      document.querySelectorAll("iframe").forEach((frame) => {
        try {
          frame.contentWindow?.postMessage(
            { type: "POLAR_DIGITAL_TWIN_ROTATION_MODE", autoRotate: digitalTwinAutoRotate },
            "*"
          );
        } catch {}
      });
    };
    sendRotationMode();
    const timer = window.setTimeout(sendRotationMode, 200);
    return () => window.clearTimeout(timer);
  }, [digitalTwinAutoRotate]);

  useEffect(() => {
    document.body.classList.toggle("digital-twin-maximized-body", digitalTwinMaximized);
    return () => document.body.classList.remove("digital-twin-maximized-body");
  }, [digitalTwinMaximized]);

  useEffect(() => {
    const send = () => {
      document.querySelectorAll<HTMLIFrameElement>("iframe[data-polar-3d-twin]").forEach((frame) => {
        try {
          frame.contentWindow?.postMessage(
            { type: "POLAR_DIGITAL_TWIN_MAXIMIZE", maximized: digitalTwinMaximized },
            "*"
          );
        } catch {}
      });
    };
    send();
    const timer = window.setTimeout(send, 150);
    return () => window.clearTimeout(timer);
  }, [digitalTwinMaximized]);
  const [intelTab, setIntelTab] = useState<IntelTab>('operations');
  const [selectedIntel, setSelectedIntel] = useState('PREDICTION');
  const selectIntelTab = (tab: IntelTab) => {
    setIntelTab(tab);
    setSelectedIntel(tab === 'operations' ? 'PREDICTION' : tab.toUpperCase());
  };

  const forecast = snapshot.horizonForecast;
  const next6h = forecast.find((p) => p.hourOffset === 6) ?? forecast[forecast.length > 1 ? 1 : 0];
  const next12h = forecast.find((p) => p.hourOffset === 12) ?? forecast[forecast.length > 2 ? 2 : 0];

  const windDrop = useMemo(() => {
    if (!next6h || snapshot.powerBalance.windGenKw <= 0) return 0;
    return Math.max(0, (1 - next6h.predictedWindKw / snapshot.powerBalance.windGenKw) * 100);
  }, [next6h, snapshot.powerBalance.windGenKw]);

  const risk = snapshot.reserve.status === 'CRITICAL_SHORTFALL'
    ? 'CRITICAL'
    : snapshot.reserve.status === 'ELEVATED_WATCH' || snapshot.topRecommendation.urgency === 'HIGH'
      ? 'WATCH'
      : 'LOW';
  const riskTone = risk === 'CRITICAL' ? 'text-red-300' : risk === 'WATCH' ? 'text-amber-300' : 'text-emerald-300';

  const recommendationTitle = snapshot.topRecommendation.title || strategy?.recommendedStrategy.name || 'Maintain current dispatch';
  const recommendationDescription = snapshot.topRecommendation.description || strategy?.recommendedStrategy.description || 'No immediate operator action required.';
  const reasoning = (strategy?.reasoningPoints ?? []).slice(0, 4);
  const whyItems = reasoning.length
    ? reasoning.map((item) => ({ title: item.title, explanation: item.explanation }))
    : [
        { title: 'Reserve policy', explanation: snapshot.reserve.reasoning },
        { title: 'Forecast source', explanation: snapshot.provenance.forecastModelSource },
      ];

  const kpis = [
    {
      label: 'CURRENT LOAD', value: `${snapshot.powerBalance.totalLoadKw.toFixed(0)} kW`,
      meta: `${snapshot.powerBalance.netBalanceKw >= 0 ? '+' : ''}${snapshot.powerBalance.netBalanceKw.toFixed(0)} kW net`,
      icon: Zap, tone: 'text-cyan-300', tab: 'energy' as TabType,
      detail: `Station demand is ${snapshot.powerBalance.totalLoadKw.toFixed(0)} kW. Net balance is ${snapshot.powerBalance.netBalanceKw >= 0 ? '+' : ''}${snapshot.powerBalance.netBalanceKw.toFixed(0)} kW.`,
      action: 'Open energy balance',
    },
    {
      label: 'BATTERY SOC', value: pct(snapshot.battery.socPercent),
      meta: `${snapshot.battery.status} · ${snapshot.battery.currentPowerKw >= 0 ? '+' : ''}${snapshot.battery.currentPowerKw.toFixed(0)} kW`,
      icon: BatteryCharging, tone: 'text-emerald-300', tab: 'energy' as TabType,
      detail: `Battery is at ${snapshot.battery.socPercent.toFixed(0)}% SOC and ${snapshot.battery.currentPowerKw >= 0 ? 'charging' : 'discharging'} at ${Math.abs(snapshot.battery.currentPowerKw).toFixed(0)} kW.`,
      action: 'Inspect battery state',
    },
    {
      label: 'FUEL RESERVE', value: `${snapshot.fuel.currentVolumeLiters.toLocaleString(undefined, { maximumFractionDigits: 0 })} L`,
      meta: `${snapshot.fuel.fillPercent.toFixed(0)}% · ${snapshot.fuel.estimatedAutonomyDays == null ? '—' : `~${snapshot.fuel.estimatedAutonomyDays.toFixed(1)} days`}`,
      icon: Fuel, tone: 'text-amber-300', tab: 'resilience' as TabType,
      detail: `Fuel inventory is ${snapshot.fuel.currentVolumeLiters.toLocaleString(undefined, { maximumFractionDigits: 0 })} L (${snapshot.fuel.fillPercent.toFixed(0)}% full).`,
      action: 'Inspect fuel resilience',
    },
    {
      label: 'RENEWABLE SHARE', value: pct(snapshot.powerBalance.renewableSharePercent),
      meta: `${snapshot.powerBalance.windGenKw.toFixed(0)} kW wind · ${snapshot.powerBalance.solarGenKw.toFixed(0)} kW solar`,
      icon: Wind, tone: 'text-emerald-300', tab: 'energy' as TabType,
      detail: `Renewables currently supply ${snapshot.powerBalance.renewableSharePercent.toFixed(0)}% of station demand: ${snapshot.powerBalance.windGenKw.toFixed(0)} kW wind and ${snapshot.powerBalance.solarGenKw.toFixed(0)} kW solar.`,
      action: 'Inspect renewable mix',
    },
    {
      label: 'STATION RISK', value: risk,
      meta: backendConnected ? 'Backend grounded' : 'Offline snapshot',
      icon: ShieldCheck, tone: riskTone, tab: 'resilience' as TabType,
      detail: `Current station risk is ${risk}. ${backendConnected ? 'The dashboard is connected to the backend state.' : 'The interface is using the latest available offline snapshot.'}`,
      action: 'Open resilience view',
    },
  ];

  const selected = kpis.find((k) => k.label === selectedKpi) ?? kpis[0];
  const SelectedIcon = selected.icon;

  const simulateRecommendation = () => onNavigateTab('simulator');

  return (
    <div className="command-center-page">
      <section className="cc-kpi-grid" aria-label="Station command KPIs">
        {kpis.map(({ label, value, meta, icon: Icon, tone }) => (
          <button
            key={label}
            type="button"
            aria-pressed={selectedKpi === label}
            data-card-title={label}
            onClick={() => setSelectedKpi(label)}
            className={`polar-interactive-card cc-kpi-card ${selectedKpi === label ? 'cc-kpi-card-active' : ''}`}
          >
            <span className={`cc-kpi-icon ${tone}`}><Icon className="w-5 h-5" /></span>
            <span className="cc-kpi-copy">
              <span className="cc-kpi-label">{label}</span>
              <span className={`cc-kpi-value ${tone}`}>{value}</span>
              <span className="cc-kpi-meta">{meta}</span>
            </span>
            <ChevronRight className="cc-kpi-chevron" />
            <span className="cc-kpi-active-line" />
          </button>
        ))}
      </section>

      <section className="cc-kpi-detail polar-interactive-card" data-card-title={`${selected.label} DETAIL`}>
        <div className={`cc-kpi-detail-icon ${selected.tone}`}><SelectedIcon className="w-4 h-4" /></div>
        <div className="cc-kpi-detail-copy">
          <div className="cc-kpi-detail-head"><span>{selected.label}</span><b>{selected.value}</b></div>
          <p>{selected.detail}</p>
          <span className="cc-kpi-detail-meta">{selected.meta}</span>
        </div>
        <button type="button" onClick={() => onNavigateTab(selected.tab)}>
          {selected.action}<ChevronRight className="w-3.5 h-3.5" />
        </button>
      </section>

      <section className={`cc-main-grid${digitalTwinMaximized ? " digital-twin-maximized" : ""}`}>
        <div className="cc-twin-card polar-interactive-card" data-card-title="DIGITAL TWIN">
          <div className="cc-twin-header">
            <div>
              

<div className="cc-section-title">DIGITAL TWIN</div>
              <div className="cc-section-subtitle">Live station model · click an asset to inspect it</div>
            </div>
            <div className="cc-weather-strip">
              <span><CloudSnow className="w-4 h-4 text-cyan-300" /> {snapshot.weather.temperature.toFixed(0)}°C</span>
              <span><Wind className="w-4 h-4 text-cyan-300" /> {snapshot.weather.windSpeed.toFixed(1)} m/s</span>
              <span>{snapshot.weather.polarDayNight}</span>
            </div>
          </div>
          <button
            type="button"
            data-digital-twin-maximize
            onClick={() => setDigitalTwinMaximized((v) => !v)}
            className="cc-twin-maximize-control"
            title={digitalTwinMaximized ? "Minimize Digital Twin" : "Maximize Digital Twin"}
            aria-label={digitalTwinMaximized ? "Minimize Digital Twin" : "Maximize Digital Twin"}
          >
            {digitalTwinMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            <span>{digitalTwinMaximized ? "MINIMIZE" : "MAXIMIZE"}</span>
          </button>
          <DigitalTwinStation
            mode="command"
            showInspector={false}
            showTimeline={false}
            onOpenAnalyticsModal={onOpenAnalyticsModal}
            timelineHour={timeOffset}
            setTimelineHour={setTimeOffset}
          />
          <div data-digital-twin-rotation className="cc-twin-rotation-control">
            <span className="cc-twin-rotation-label">ROTATION</span>
            <button type="button" onClick={() => setDigitalTwinAutoRotate(true)}
              className={digitalTwinAutoRotate ? 'active' : ''} aria-pressed={digitalTwinAutoRotate}>AUTO ROTATE</button>
            <button type="button" onClick={() => setDigitalTwinAutoRotate(false)}
              className={!digitalTwinAutoRotate ? 'active' : ''} aria-pressed={!digitalTwinAutoRotate}>MANUAL</button>
          </div>
          <div className="cc-timeline-strip">
            <div className="flex items-center gap-2">
              <span className="cc-section-title text-xs">STATION TIMELINE · 72H</span>
              <span className="cc-live-dot" />
              <span className="cc-section-subtitle">Forecast-driven state</span>
            </div>
            <div className="cc-timeline-buttons">
              {[0, 6, 12, 24, 48, 72].map((hour) => (
                <button key={hour} onClick={() => setTimeOffset(hour)} className={timeOffset === hour ? 'active' : ''}>{hour === 0 ? 'NOW' : `+${hour}H`}</button>
              ))}
            </div>
          </div>
        </div>

        <aside className="cc-intelligence-card polar-interactive-card" data-card-title="OPERATIONAL INTELLIGENCE">
          <div className="cc-intelligence-tabs" role="tablist" aria-label="Operational intelligence">
            <button
              type="button"
              role="tab"
              aria-selected={intelTab === 'operations'}
              className={intelTab === 'operations' ? 'active' : ''}
              onPointerDown={(event) => { event.stopPropagation(); selectIntelTab('operations'); }}
              onClick={(event) => { event.stopPropagation(); selectIntelTab('operations'); }}
            >
              Operational Intelligence
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={intelTab === 'alerts'}
              className={intelTab === 'alerts' ? 'active' : ''}
              onPointerDown={(event) => { event.stopPropagation(); selectIntelTab('alerts'); }}
              onClick={(event) => { event.stopPropagation(); selectIntelTab('alerts'); }}
            >
              Alerts {snapshot.topRecommendation.actionable ? <b>1</b> : null}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={intelTab === 'weather'}
              className={intelTab === 'weather' ? 'active' : ''}
              onPointerDown={(event) => { event.stopPropagation(); selectIntelTab('weather'); }}
              onClick={(event) => { event.stopPropagation(); selectIntelTab('weather'); }}
            >
              Weather
            </button>
          </div>

          <div className="cc-intel-body">
            {intelTab === 'operations' && <>
              <button type="button" className={`polar-interactive-card cc-intel-block ${selectedIntel === 'PREDICTION' ? 'cc-intel-selected' : ''}`} data-card-title="PREDICTION" onClick={() => setSelectedIntel('PREDICTION')}>
                <div className="cc-intel-kicker"><Wind className="w-4 h-4" /> PREDICTION <span>Next 6 Hours</span></div>
                <div className="cc-intel-headline">
                  {windDrop > 0 ? <>Wind generation expected to decrease by <strong>{windDrop.toFixed(0)}%</strong>.</> : <>Renewable generation remains within the current forecast range.</>}
                </div>
                <div className="cc-mini-bars" aria-hidden="true">
                  {forecast.slice(0, 8).map((point, i) => {
                    const max = Math.max(...forecast.slice(0, 8).map(p => p.predictedWindKw), 1);
                    return <span key={point.hourOffset} style={{ height: `${Math.max(8, point.predictedWindKw / max * 100)}%`, opacity: i < 4 ? 1 : .55 }} />;
                  })}
                </div>
              </button>

              <button type="button" className={`polar-interactive-card cc-intel-impact ${selectedIntel === 'IMPACT' ? 'cc-intel-selected' : ''}`} data-card-title="IMPACT" onClick={() => setSelectedIntel('IMPACT')}>
                <div className="cc-intel-kicker text-amber-300"><AlertTriangle className="w-4 h-4" /> IMPACT</div>
                <ul>
                  <li>Battery reserve target: {snapshot.reserve.targetReservePercent.toFixed(0)}%</li>
                  <li>Projected SOC at +12h: {next12h ? next12h.batterySocPercent.toFixed(0) : '—'}%</li>
                  <li>Fuel reserve: {snapshot.fuel.fillPercent.toFixed(0)}%</li>
                </ul>
              </button>

              <div className={`polar-interactive-card cc-recommendation ${selectedIntel === 'RECOMMENDATION' ? 'cc-intel-selected' : ''}`} data-card-title="RECOMMENDATION" onClick={() => setSelectedIntel('RECOMMENDATION')}>
                <div className="cc-intel-kicker text-emerald-300"><Lightbulb className="w-4 h-4" /> RECOMMENDATION</div>
                <div className="cc-recommendation-title">{recommendationTitle}</div>
                <div className="cc-recommendation-description">{recommendationDescription}</div>
                <div className="cc-action-row">
                  <button onClick={simulateRecommendation}><Play className="w-3.5 h-3.5" /> Open Simulator</button>
                  <button onClick={() => onNavigateTab('optimization')}>View Alternatives <ChevronRight className="w-3.5 h-3.5" /></button>
                </div>
              </div>

              <div className={`polar-interactive-card cc-why ${selectedIntel === 'WHY' ? 'cc-intel-selected' : ''}`} data-card-title="WHY THIS RECOMMENDATION" onClick={() => setSelectedIntel('WHY')}>
                <div className="cc-intel-kicker"><ShieldCheck className="w-4 h-4" /> WHY THIS RECOMMENDATION?</div>
                {whyItems.map((item, index) => (
                  <div className="cc-why-row" key={`${item.title}-${index}`}><span>{index + 1}</span><div><b>{item.title}</b><small>{item.explanation}</small></div></div>
                ))}
              </div>
            </>}

            {intelTab === 'alerts' && <div className="cc-intel-alt-view cc-alerts-view">
              <div className="cc-alt-hero cc-alert-hero"><Bell className="w-5 h-5" /><div><b>{snapshot.topRecommendation.actionable ? 'ACTION REQUIRED' : 'NO ACTIVE CRITICAL ALERT'}</b><small>{snapshot.topRecommendation.actionable ? recommendationTitle : 'Station state is within the current operating envelope.'}</small></div></div>
              <div className="cc-alert-list">
                {snapshot.topRecommendation.actionable && <div className="cc-alert-row high"><span className="cc-alert-dot" /><div><b>{recommendationTitle}</b><small>{recommendationDescription} · urgency {snapshot.topRecommendation.urgency}</small></div><span className="cc-alert-severity">{snapshot.topRecommendation.urgency}</span></div>}
                <div className={`cc-alert-row ${snapshot.reserve.status === 'CRITICAL_SHORTFALL' ? 'high' : snapshot.reserve.status === 'ELEVATED_WATCH' ? 'medium' : 'low'}`}><span className="cc-alert-dot" /><div><b>Reserve status: {snapshot.reserve.status.replaceAll('_', ' ')}</b><small>Target {snapshot.reserve.targetReservePercent.toFixed(0)}% · current reserve {snapshot.reserve.currentReservePercent.toFixed(0)}% · fuel {snapshot.fuel.fillPercent.toFixed(0)}%</small></div><span className="cc-alert-severity">{snapshot.reserve.status === 'CRITICAL_SHORTFALL' ? 'CRITICAL' : snapshot.reserve.status === 'ELEVATED_WATCH' ? 'WATCH' : 'NORMAL'}</span></div>
                {windDrop >= 15 && <div className="cc-alert-row medium"><span className="cc-alert-dot" /><div><b>Renewable forecast decline</b><small>Wind generation is projected to decrease by {windDrop.toFixed(0)}% over the next 6 hours.</small></div><span className="cc-alert-severity">WATCH</span></div>}
              </div>
              <div className="cc-alert-source">Source: {snapshot.provenance.forecastModelSource} · telemetry: {snapshot.provenance.powerTelemetrySource}</div>
              <button type="button" className="cc-alt-action" onClick={() => onNavigateTab('resilience')}>Open Resilience <ChevronRight className="w-3.5 h-3.5" /></button>
            </div>}

            {intelTab === 'weather' && <div className="cc-intel-alt-view cc-weather-view">
              <div className="cc-alt-hero"><ThermometerSnowflake className="w-5 h-5" /><div><b>{snapshot.weather.condition} · {snapshot.weather.temperature.toFixed(1)}°C</b><small>{snapshot.weather.polarDayNight} · updated {new Date(snapshot.weather.lastUpdated).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</small></div></div>
              <div className="cc-weather-grid cc-weather-grid-rich">
                <div><span>TEMPERATURE</span><b>{snapshot.weather.temperature.toFixed(1)}°C</b><small>Feels {snapshot.weather.apparentTemperature?.toFixed(1) ?? '—'}°C</small></div>
                <div><span>WIND</span><b>{snapshot.weather.windSpeed.toFixed(1)} m/s</b><small>{snapshot.weather.windDirection}</small></div>
                <div><span>HUMIDITY</span><b>{snapshot.weather.humidity.toFixed(0)}%</b><small>Cloud {snapshot.weather.cloudCover.toFixed(0)}%</small></div>
                <div><span>VISIBILITY</span><b>{snapshot.weather.visibilityKm.toFixed(1)} km</b><small>Snow {snapshot.weather.snowfallCm.toFixed(1)} cm</small></div>
                <div><span>SOLAR</span><b>{snapshot.weather.solarRadiation.toFixed(0)} W/m²</b><small>Pressure {snapshot.weather.pressureHpa.toFixed(0)} hPa</small></div>
                <div><span>CONFIDENCE</span><b>{snapshot.weather.confidence.toFixed(0)}%</b><small>{snapshot.weather.provenance}</small></div>
              </div>
              <div className="cc-weather-forecast"><span>NEXT 24H</span>{forecast.slice(0, 4).map(point => <div key={point.hourOffset}><b>+{point.hourOffset}h</b><small>{point.temperatureC?.toFixed(0) ?? '—'}°C · {point.windSpeedMs?.toFixed(1) ?? '—'} m/s</small></div>)}</div>
              <button type="button" className="cc-alt-action" onClick={() => onNavigateTab('analytics')}><Eye className="w-3.5 h-3.5" /> Open Analytics <ChevronRight className="w-3.5 h-3.5" /></button>
            </div>}
          </div>
        </aside>
      </section>

      <MissionAutopilotPanel />
      <UltimateAICorePanel />
      <MissionSurvivalPanel />
    </div>
  );
};
