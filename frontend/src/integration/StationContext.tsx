/**
 * Central Station Context (Data Layer)
 * Provides authoritative station snapshot, decision strategy, resilience status,
 * time machine scrubber offsets, and asset inspector state.
 */

import React, { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import {
  StationSnapshot,
  UnifiedStrategyResponse,
  StationResilienceOverview,
  NavigationTab,
  SystemMode,
  SimulationPoint,
} from './types';
import {
  fetchStationSnapshot,
  getOfflineSnapshot,
  fetchStationStrategy,
  fetchStationResilience,
  prefetchStationStrategy,
  prefetchStationResilience,
  fallbackSnapshot,
  readCachedStationSnapshot,
  cacheStationSnapshot,
  API_BASE,
  prefetchStationAnalyticsProjection,
} from './api';

interface StationContextType {
  snapshot: StationSnapshot;
  strategy: UnifiedStrategyResponse | null;
  resilience: StationResilienceOverview | null;
  activeTab: NavigationTab;
  setActiveTab: (tab: NavigationTab) => void;
  timeOffset: number; // 0, 6, 12, 24, 48, 72
  setTimeOffset: (offset: number) => void;
  isPlayingTimeline: boolean;
  setIsPlayingTimeline: (play: boolean) => void;
  selectedAssetId: string | null;
  setSelectedAssetId: (id: string | null) => void;
  systemMode: SystemMode;
  setSystemMode: (mode: SystemMode) => void;
  isStationBrainOpen: boolean;
  setIsStationBrainOpen: (open: boolean) => void;
  refreshSnapshot: (offset?: number) => Promise<void>;
  applySimulationPoint: (point: SimulationPoint) => void;
  clearSimulationState: () => Promise<void>;
  refreshStrategy: (params?: Parameters<typeof fetchStationStrategy>[0]) => Promise<UnifiedStrategyResponse | null>;
  refreshResilience: (hours?: number, forceRefresh?: boolean) => Promise<StationResilienceOverview | null>;
  resilienceLoading: boolean;
  resilienceError: string;
  backendConnected: boolean;
  appliedOpportunities: Record<string, boolean>;
  toggleOpportunity: (id: string) => void;
  appliedStrategyCode: string;
  setAppliedStrategyCode: (code: string) => void;
  strategyLoading: boolean;
  strategyError: string;
  startupReady: boolean;
  startupLoading: boolean;
  enterMissionControl: () => void;
  simulationTrajectory: SimulationPoint[];
  setSimulationTrajectory: (points: SimulationPoint[]) => void;
}

const StationContext = createContext<StationContextType | undefined>(undefined);

export const StationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const cachedStartupSnapshot = readCachedStationSnapshot();
  const [snapshot, setSnapshot] = useState<StationSnapshot>(cachedStartupSnapshot ?? fallbackSnapshot);
  const [strategy, setStrategy] = useState<UnifiedStrategyResponse | null>(null);
  const [strategyLoading, setStrategyLoading] = useState<boolean>(false);
  const [strategyError, setStrategyError] = useState<string>('');
  const snapshotRequestId = useRef(0);
  const snapshotAbortController = useRef<AbortController | null>(null);
  const strategyRequestId = useRef(0);
  const strategyAbortController = useRef<AbortController | null>(null);
  // A manual operator recalculation must remain authoritative until the next
  // scheduled refresh; background snapshot/prefetch work must not overwrite it.
  const strategyManualHold = useRef(false);
  const resilienceAbortController = useRef<AbortController | null>(null);
  const resilienceRequestId = useRef(0);
  const resilienceInFlight = useRef<{ hours: number; promise: Promise<StationResilienceOverview | null> } | null>(null);
  const [resilience, setResilience] = useState<StationResilienceOverview | null>(null);
  const [resilienceLoading, setResilienceLoading] = useState(false);
  const [resilienceError, setResilienceError] = useState('');
  const [backendConnected, setBackendConnected] = useState(Boolean(cachedStartupSnapshot));
  const [startupReady, setStartupReady] = useState(false);
  const [startupLoading, setStartupLoading] = useState(true);
  const enterMissionControl = useCallback(() => {
    setStartupReady(true);
  }, []);
  const [activeTab, setActiveTab] = useState<NavigationTab>('command-center');
  const [timeOffset, setTimeOffset] = useState<number>(0);
  const [isPlayingTimeline, setIsPlayingTimeline] = useState<boolean>(false);
  const [simulationTrajectory, setSimulationTrajectoryState] = useState<SimulationPoint[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [systemMode, setSystemModeState] = useState<SystemMode>('ONLINE');
  const lastKnownSnapshotRef = useRef<StationSnapshot>(cachedStartupSnapshot ?? fallbackSnapshot);
  const timeOffsetRef = useRef(0);
  const systemModeRef = useRef<SystemMode>('ONLINE');
  timeOffsetRef.current = timeOffset;
  systemModeRef.current = systemMode;

  // The application mode is UI-wide state. Backend snapshots remain the data source,
  // but their legacy `mode` field must never override the operator-selected mode.
  const setSystemMode = (mode: SystemMode) => {
    systemModeRef.current = mode;
    if (mode !== 'SIMULATION') setSimulationTrajectoryState([]);
    setSystemModeState(mode);
    if (mode === 'ONLINE') {
      setSnapshot(prev => ({ ...prev, mode: 'ONLINE' }));
      void refreshSnapshot(0);
      return;
    }
    if (mode === 'OFFLINE') {
      const cached = lastKnownSnapshotRef.current;
      setSnapshot({ ...cached, mode: 'OFFLINE', provenance: { ...cached.provenance, powerTelemetrySource: 'CACHED', weatherSource: 'CACHED' } });
      return;
    }
    setSnapshot(prev => ({ ...prev, mode: 'SIMULATION' }));
  };
  const [isStationBrainOpen, setIsStationBrainOpen] = useState<boolean>(false);
  const [appliedStrategyCode, setAppliedStrategyCode] = useState<string>('');
  const [appliedOpportunities, setAppliedOpportunities] = useState<Record<string, boolean>>({
    'opp-1': true,
    'opp-2': false,
    'opp-3': false,
  });

  const refreshStrategy = useCallback(async (params?: Parameters<typeof fetchStationStrategy>[0]) => {
    const requestId = ++strategyRequestId.current;
    strategyAbortController.current?.abort();
    const controller = new AbortController();
    strategyAbortController.current = controller;
    setStrategyLoading(true);
    setStrategyError('');
    try {
      const result = await fetchStationStrategy(params, controller.signal);
      if (!result?.recommendedStrategy?.code) throw new Error('Decision engine returned no feasible strategy.');
      if (requestId !== strategyRequestId.current || controller.signal.aborted) return result;
      setStrategy(result);
      strategyManualHold.current = true;
      return result;
    } catch (err) {
      if (controller.signal.aborted && requestId !== strategyRequestId.current) return null;
      console.warn('Refresh strategy error:', err);
      if (requestId === strategyRequestId.current) {
        const message = err instanceof Error ? (err.name === 'AbortError' ? 'Decision engine request timed out or was cancelled.' : err.message) : 'Decision engine unavailable';
        setStrategyError(message);
        throw new Error(message);
      }
      return null;
    } finally {
      if (requestId === strategyRequestId.current) {
        strategyAbortController.current = null;
        setStrategyLoading(false);
      }
    }
  }, []);

  const refreshResilience = useCallback((hours: number = 72, forceRefresh: boolean = false): Promise<StationResilienceOverview | null> => {
    // React StrictMode/tab remounts must never launch duplicate expensive work.
    if (!forceRefresh && resilienceInFlight.current?.hours === hours) return resilienceInFlight.current.promise;

    const requestId = ++resilienceRequestId.current;
    resilienceAbortController.current?.abort();
    const controller = new AbortController();
    resilienceAbortController.current = controller;
    setResilienceLoading(true);
    setResilienceError('');

    let promise: Promise<StationResilienceOverview | null>;
    promise = (async () => {
      try {
        const result = forceRefresh
          ? await fetchStationResilience(hours, controller.signal)
          : await prefetchStationResilience(hours);
        if (requestId !== resilienceRequestId.current || controller.signal.aborted) return result;
        setResilience(result);
        setResilienceError('');
        return result;
      } catch (err) {
        if (controller.signal.aborted && requestId !== resilienceRequestId.current) return null;
        const message = err instanceof Error ? err.message : 'Resilience backend unavailable';
        if (requestId === resilienceRequestId.current) setResilienceError(message);
        console.warn('Refresh resilience error:', err);
        return null;
      } finally {
        if (requestId === resilienceRequestId.current) {
          resilienceAbortController.current = null;
          setResilienceLoading(false);
        }
        if (resilienceInFlight.current?.promise === promise) resilienceInFlight.current = null;
      }
    })();

    resilienceInFlight.current = { hours, promise };
    return promise;
  }, []);

  const refreshSnapshot = useCallback(async (offset?: number) => {
    // Only ONLINE owns authoritative backend refreshes. OFFLINE is cached/read-only;
    // SIMULATION is owned by the scenario engine and must never be overwritten by live polling.
    if (systemModeRef.current !== 'ONLINE') return;
    const effectiveOffset = offset ?? timeOffsetRef.current;
    const requestId = ++snapshotRequestId.current;
    snapshotAbortController.current?.abort();
    const controller = new AbortController();
    snapshotAbortController.current = controller;
    try {
      const snap = await fetchStationSnapshot(effectiveOffset, controller.signal);
      if (requestId !== snapshotRequestId.current) return;
      setBackendConnected(true);
      const normalizedSnapshot = { ...snap, selectedHourOffset: snap.selectedHourOffset ?? effectiveOffset, mode: systemModeRef.current === 'ONLINE' ? 'ONLINE' : systemModeRef.current };
      // Only a live (+0h) snapshot is a valid last-known operational cache.
      // Future timeline projections must never become the offline baseline.
      if (effectiveOffset === 0) {
        lastKnownSnapshotRef.current = normalizedSnapshot;
        cacheStationSnapshot(normalizedSnapshot);
      }
      setSnapshot(normalizedSnapshot);
      // A snapshot may already contain the same decision-engine response. Use it
      // immediately; otherwise consume the shared startup strategy promise.
      if (snap.decisionStrategy?.recommendedStrategy?.code) {
        if (!strategyManualHold.current) {
          setStrategy(snap.decisionStrategy);
          setStrategyError('');
        }
      } else if (effectiveOffset === 0) {
        // Some compatible backend snapshots do not embed the decision result.
        // Consume the shared startup strategy promise instead of launching a
        // second request that could cancel the startup request.
        void prefetchStationStrategy().then(setStrategy).catch(() => undefined);
      }
    } catch (err) {
      if (requestId !== snapshotRequestId.current) return;
      if (controller.signal.aborted) return;
      setBackendConnected(false);
      const cached = lastKnownSnapshotRef.current ?? getOfflineSnapshot();
      setSnapshot({ ...cached, selectedHourOffset: effectiveOffset, mode: 'OFFLINE', provenance: { ...cached.provenance, powerTelemetrySource: 'CACHED', weatherSource: 'CACHED' } });
      systemModeRef.current = 'OFFLINE';
      setSystemModeState('OFFLINE');
      setStrategyError(prev => prev || 'Backend connection unavailable.');
      console.warn('Refresh snapshot error:', err);
    } finally {
      if (requestId === snapshotRequestId.current) snapshotAbortController.current = null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    // Startup is intentionally non-blocking. The local/cached station state is
    // rendered immediately while the authoritative snapshot hydrates in the
    // background. Expensive strategy, resilience and analytics projections are
    // requested only when their tabs are opened.
    setStartupLoading(true);
    void refreshSnapshot(0).finally(() => {
      if (!cancelled) setStartupLoading(false);
    });
    return () => { cancelled = true; };
  }, [refreshSnapshot]);

  // Keep the current station state fresh after the initial operational data pass.
  // This effect never controls startup readiness and never launches the expensive
  // resilience/analytics calculations on tab changes.
  const applySimulationPoint = useCallback((point: SimulationPoint) => {
    systemModeRef.current = 'SIMULATION';
    setSystemModeState('SIMULATION');
    setSnapshot(prev => {
      const totalGeneration = Math.max(0, point.solar_power_kw + point.wind_power_kw + point.diesel_power_kw);
      const load = Math.max(0, point.load_kw);
      const rawBatteryNeed = load - totalGeneration;
      const socRatio = Math.max(0, Math.min(1, point.battery_soc_percent / 100));
      const minSocRatio = Math.max(0, Math.min(1, prev.battery.minSocPercent / 100));
      const maxSocRatio = Math.max(minSocRatio, Math.min(1, prev.battery.maxSocPercent / 100));
      const availableDischargeKwh = Math.max(0, (socRatio - minSocRatio) * prev.battery.capacityKwh);
      const availableChargeKwh = Math.max(0, (maxSocRatio - socRatio) * prev.battery.capacityKwh);
      // Simulation points are hourly today, but calculate power from the actual
      // trajectory interval so kWh headroom is never accidentally treated as kW.
      const intervalHours = Math.max(1, (point.hour_offset - prev.selectedHourOffset));
      const availableDischargeKw = availableDischargeKwh / intervalHours;
      const availableChargeKw = availableChargeKwh / intervalHours;
      const batteryPower = rawBatteryNeed > 0
        ? Math.min(rawBatteryNeed, prev.battery.maxSocPercent > prev.battery.minSocPercent ? 100 : 0, availableDischargeKw)
        : -Math.min(-rawBatteryNeed, 100, availableChargeKw);
      const fuelCapacity = prev.fuel.capacityLiters;
      const fillPercent = fuelCapacity > 0 ? Math.max(0, Math.min(100, point.fuel_remaining_liters / fuelCapacity * 100)) : prev.fuel.fillPercent;
      const generators = prev.generators.map((g, i) => ({
        ...g,
        currentOutputKw: i === 0 ? Math.max(0, point.diesel_power_kw) : 0,
        status: i === 0 && point.diesel_power_kw > 0 ? 'ONLINE' as const : 'STANDBY' as const,
      }));
      const renewables = prev.renewables.map(r => ({
        ...r,
        currentOutputKw: r.type === 'Wind Turbine' ? Math.max(0, point.wind_power_kw) : Math.max(0, point.solar_power_kw),
        status: 'ONLINE' as const,
      }));
      const scale = prev.powerBalance.totalLoadKw > 0 ? load / prev.powerBalance.totalLoadKw : 1;
      const loads = prev.loads.map(l => ({ ...l, currentLoadKw: Math.max(0, l.currentLoadKw * scale), peakLoadKw: Math.max(l.peakLoadKw, l.currentLoadKw * scale) }));
      return {
        ...prev,
        mode: 'SIMULATION',
        selectedHourOffset: point.hour_offset,
        systemTime: point.timestamp,
        weather: { ...prev.weather, temperature: point.outdoor_temperature_celsius ?? prev.weather.temperature, windSpeed: point.wind_speed_mps ?? prev.weather.windSpeed, solarRadiation: point.solar_irradiance_w_m2 ?? prev.weather.solarRadiation, lastUpdated: point.timestamp, provenance: 'ENGINEERING MODEL' },
        powerBalance: { ...prev.powerBalance, totalGenerationKw: totalGeneration, totalLoadKw: load, netBalanceKw: totalGeneration + batteryPower - load, dieselGenKw: Math.max(0, point.diesel_power_kw), windGenKw: Math.max(0, point.wind_power_kw), solarGenKw: Math.max(0, point.solar_power_kw), batteryPowerKw: batteryPower, renewableSharePercent: totalGeneration > 0 ? 100 * (point.solar_power_kw + point.wind_power_kw) / totalGeneration : 0 },
        battery: { ...prev.battery, socPercent: Math.max(0, Math.min(100, point.battery_soc_percent)), currentChargeKwh: prev.battery.capacityKwh * Math.max(0, Math.min(100, point.battery_soc_percent)) / 100, currentPowerKw: batteryPower, status: batteryPower > 0 ? 'DISCHARGING' : batteryPower < 0 ? 'CHARGING' : 'IDLE' },
        fuel: { ...prev.fuel, currentVolumeLiters: Math.max(0, point.fuel_remaining_liters), fillPercent },
        generators,
        renewables,
        loads,
        provenance: { ...prev.provenance, powerTelemetrySource: 'SIMULATION', weatherSource: 'SIMULATION' },
      };
    });
  }, []);

  const setSimulationTrajectory = useCallback((points: SimulationPoint[]) => {
    setSimulationTrajectoryState(Array.isArray(points) ? points : []);
  }, []);

  const clearSimulationState = useCallback(async () => {
    setSimulationTrajectoryState([]);
    if (!backendConnected) {
      setSystemMode('OFFLINE');
      return;
    }
    setSystemMode('ONLINE');
  }, [backendConnected]);

  // Fetch the selected projection immediately when the operator changes the timeline.
  // Previously only the 10-second background refresh handled offset 0, so +6/+12/+24...
  // could leave the UI showing stale values until another refresh.
  useEffect(() => {
    if (!startupReady) return;
    if (systemModeRef.current === 'ONLINE') {
      void refreshSnapshot(timeOffset);
    }
  }, [startupReady, timeOffset, refreshSnapshot]);

  useEffect(() => {
    const handleSettingsChanged = () => {
      // Settings are a local operator policy, but the resulting strategy/resilience
      // values must still come from the backend. Re-evaluate them immediately so
      // saving a new reserve floor never leaves Command Center/Resilience stale.
      void refreshStrategy().catch(() => undefined);
      void refreshResilience(72, true).catch(() => undefined);
    };
    window.addEventListener('polar-ems-settings-changed', handleSettingsChanged);
    return () => window.removeEventListener('polar-ems-settings-changed', handleSettingsChanged);
  }, [refreshStrategy, refreshResilience]);

  useEffect(() => {
    if (!startupReady) return;
    const interval = setInterval(() => {
      if (systemModeRef.current !== 'ONLINE' || timeOffset !== 0) return;
      // Keep live telemetry responsive, but do not recalculate every expensive
      // intelligence projection on every cycle. Each intelligence layer refreshes
      // only while its tab is active; manual actions remain immediate.
      void refreshSnapshot(0);
      if (activeTab === 'optimization') {
        if (strategyManualHold.current) strategyManualHold.current = false;
        else void prefetchStationStrategy().then(setStrategy).catch(() => undefined);
      }
      if (activeTab === 'resilience') void refreshResilience(72).catch(() => undefined);
      if (activeTab === 'analytics') void prefetchStationAnalyticsProjection(24).catch(() => undefined);
    }, 15000);
    return () => clearInterval(interval);
  }, [startupReady, activeTab, timeOffset, refreshSnapshot, refreshResilience]);


  useEffect(() => {
    if (!startupReady) return;
    const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws/live';
    let socket: WebSocket | null = null;
    let heartbeat: ReturnType<typeof setInterval> | null = null;
    let stopped = false;
    const connect = () => {
      try {
        socket = new WebSocket(wsUrl);
        socket.onopen = () => {
          heartbeat = setInterval(() => socket?.send('ping'), 10000);
        };
        socket.onmessage = (event) => {
          try {
            const raw = JSON.parse(event.data);
            if (raw?.weather && raw?.generation && raw?.loads && startupReady && systemModeRef.current === 'ONLINE') {
              // The websocket carries the authoritative Twin state in backend-native
              // shape. Refresh the normalized StationSnapshot immediately so every tab
              // sees the same changing values instead of only a connection heartbeat.
              setBackendConnected(true);
              void refreshSnapshot(0);
            }
          } catch { /* ignore malformed live frames */ }
        };
        socket.onclose = () => {
          if (heartbeat) clearInterval(heartbeat);
          if (!stopped) {
            setBackendConnected(false);
            if (systemModeRef.current === 'ONLINE') {
              systemModeRef.current = 'OFFLINE';
              setSystemModeState('OFFLINE');
              const cached = lastKnownSnapshotRef.current;
              setSnapshot({ ...cached, mode: 'OFFLINE', provenance: { ...cached.provenance, powerTelemetrySource: 'CACHED', weatherSource: 'CACHED' } });
            }
            setTimeout(connect, 5000);
          }
        };
      } catch { /* polling remains authoritative fallback */ }
    };
    connect();
    return () => {
      stopped = true;
      if (heartbeat) clearInterval(heartbeat);
      socket?.close();
    };
  }, [systemMode, startupReady]);




  useEffect(() => () => { snapshotAbortController.current?.abort(); strategyAbortController.current?.abort(); resilienceAbortController.current?.abort(); }, []);

  // Timeline playback animation loop
  useEffect(() => {
    if (!isPlayingTimeline) return;
    const offsets = [0, 6, 12, 24, 48, 72];
    const timer = setInterval(() => {
      setTimeOffset((prev) => {
        const idx = offsets.indexOf(prev);
        if (idx === -1 || idx === offsets.length - 1) {
          return 0;
        }
        return offsets[idx + 1];
      });
    }, 2800);
    return () => clearInterval(timer);
  }, [isPlayingTimeline]);

  const toggleOpportunity = (id: string) => {
    setAppliedOpportunities((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  return (
    <StationContext.Provider
      value={{
        snapshot,
        strategy,
        resilience,
        activeTab,
        setActiveTab,
        timeOffset,
        setTimeOffset,
        isPlayingTimeline,
        setIsPlayingTimeline,
        selectedAssetId,
        setSelectedAssetId,
        systemMode,
        setSystemMode,
        isStationBrainOpen,
        setIsStationBrainOpen,
        refreshSnapshot,
        applySimulationPoint,
        clearSimulationState,
        refreshStrategy,
        refreshResilience,
        resilienceLoading,
        resilienceError,
        backendConnected,
        strategyLoading,
        strategyError,
        startupReady,
        startupLoading,
        enterMissionControl,
        simulationTrajectory,
        setSimulationTrajectory,
        appliedOpportunities,
        toggleOpportunity,
        appliedStrategyCode,
        setAppliedStrategyCode,
      }}
    >
      {children}
    </StationContext.Provider>
  );
};

export const useStation = (): StationContextType => {
  const context = useContext(StationContext);
  if (!context) {
    throw new Error('useStation must be used within a StationProvider');
  }
  return context;
};
