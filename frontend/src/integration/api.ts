/**
 * DHRUVA Client API Service
 * Client API service for the FastAPI backend with explicit offline cache handling.
 */

import {
  StationSnapshot,
  UnifiedStrategyResponse,
  StationResilienceOverview,
  ResilienceScenarioResult,
  StationRiskAssessment,
} from './types';

function resolveApiBase(): string {
  const configured = String(import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/$/, '');
  if (typeof window !== 'undefined' && /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return configured || 'http://localhost:8000';
}

export const API_BASE = resolveApiBase();

export async function fetchStationRisk(hours: number = 24, signal?: AbortSignal): Promise<StationRiskAssessment> {
  const result = await fetchJson<any>(`${API_BASE}/risk?hours=${hours}`, { signal }, 30000);
  return {
    horizonHours: Number(result.horizon_hours ?? hours),
    overallRiskPercent: Number(result.overall_risk_percent ?? 0),
    riskLevel: result.risk_level ?? 'LOW',
    blackoutRiskPercent: Number(result.blackout_risk_percent ?? 0),
    components: {
      criticalLoadRiskPercent: Number(result.components?.critical_load_risk_percent ?? 0),
      batterySocRiskPercent: Number(result.components?.battery_soc_risk_percent ?? 0),
      fuelReserveRiskPercent: Number(result.components?.fuel_reserve_risk_percent ?? 0),
      serviceLevelRiskPercent: Number(result.components?.service_level_risk_percent ?? 0),
      forecastUncertaintyRiskPercent: Number(result.components?.forecast_uncertainty_risk_percent ?? 0),
      extremeWeatherRiskPercent: Number(result.components?.extreme_weather_risk_percent ?? 0),
    },
    riskSeries: Array.isArray(result.risk_series) ? result.risk_series.map((point: any) => ({
      hour_offset: Number(point.hour_offset ?? 0),
      overall: Number(point.overall ?? 0),
      critical: Number(point.critical ?? 0),
      battery: Number(point.battery ?? 0),
      fuel: Number(point.fuel ?? 0),
      service: Number(point.service ?? 0),
      uncertainty: Number(point.uncertainty ?? 0),
      weather: Number(point.weather ?? 0),
    })) : [],
    isAdvisory: Boolean(result.is_advisory),
    calibrationNote: String(result.calibration_note ?? ''),
  };
}

async function fetchJson<T>(url: string, options: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const externalSignal = options.signal;
  let onAbort: (() => void) | undefined;
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else {
      onAbort = () => controller.abort();
      externalSignal.addEventListener('abort', onAbort, { once: true });
    }
  }
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    if (!res.ok) {
      let detail = '';
      try { detail = await res.text(); } catch { /* ignore */ }
      throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail.slice(0, 180)}` : ''}`);
    }
    return await res.json() as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (externalSignal?.aborted) throw new Error('Backend request cancelled.');
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw err instanceof Error ? err : new Error('Backend request failed');
  } finally {
    window.clearTimeout(timer);
    if (externalSignal && onAbort) externalSignal.removeEventListener('abort', onAbort);
  }
}



export const fallbackSnapshot: StationSnapshot = {
  stationName: 'Maitri Research Station',
  selectedHourOffset: 0,
  location: 'Schirmacher Oasis, Dronning Maud Land, Antarctica',
  coordinates: { lat: -70.7504583, lng: 11.7170694 },
  systemTime: new Date().toISOString(),
  mode: 'OFFLINE',
  weather: {
    temperature: -24.0,
    apparentTemperature: -32.5,
    humidity: 78,
    windSpeed: 12.0,
    windDirection: 'SE',
    visibilityKm: 3.0,
    condition: 'Light Snow',
    solarRadiation: 15,
    cloudCover: 85,
    pressureHpa: 988,
    snowfallCm: 0.2,
    polarDayNight: 'Polar Night',
    provenance: 'ESTIMATED',
    lastUpdated: new Date().toISOString(),
    confidence: 94,
  },
  powerBalance: {
    totalGenerationKw: 50,
    totalLoadKw: 50,
    netBalanceKw: 0,
    dieselGenKw: 32.9,
    windGenKw: 17.1,
    solarGenKw: 0,
    batteryPowerKw: 0,
    renewableSharePercent: 34.2,
    systemEfficiencyPercent: 100,
  },
  battery: {
    capacityKwh: 500,
    currentChargeKwh: 300,
    socPercent: 60,
    currentPowerKw: 0,
    status: 'IDLE',
    minSocPercent: 20,
    maxSocPercent: 95,
    temperatureC: -10,
    healthPercent: 100,
    cyclesCompleted: 0,
  },
  fuel: {
    capacityLiters: 20000,
    currentVolumeLiters: 15000,
    fillPercent: 75,
    currentConsumptionRateLhr: 13.2,
    estimatedAutonomyDays: 47.3,
    emergencyReserveLiters: 2000,
    lastDeliveryDaysAgo: 0,
    nextScheduledDeliveryDays: 0,
  },
  thermal: {
    indoorTemperatureC: 20.0,
    outdoorTemperatureC: -20.0,
    totalHeatingDemandKw: 37.65,
    recoveredHeatKw: 30.91,
    electricalHeatingKw: 6.74,
    heatRecoveryEfficiency: 0.65,
    heatRecoveryEnabled: true,
    thermalOffsetPercent: 50,
  },
  reserve: {
    currentReservePercent: 20,
    targetReservePercent: 20,
    spinningReserveKw: 0,
    status: 'ADEQUATE',
    drivers: {
      windRisk: 0,
      snowfallRisk: 0,
      temperatureColdStress: 0,
      forecastConfidence: 94,
    },
    reasoning: 'Engineering-model fallback only; authoritative EMS reserve is unavailable while the backend is offline.',
  },
  generators: [
    {
      id: 'DG-01',
      name: 'Diesel Generator 1',
      type: 'Diesel Generator',
      capacityKw: 150,
      currentOutputKw: 32.9,
      status: 'ONLINE',
      fuelConsumptionLhr: 13.2,
      electricalEfficiency: 0.38,
      runtimeHours: 0,
      healthPercent: 100,
      nextMaintenanceHours: 0,
      wasteHeatAvailableKw: 0,
      isRecoveringHeat: true,
    },
    {
      id: 'DG-02',
      name: 'Diesel Generator 2',
      type: 'Diesel Generator',
      capacityKw: 150,
      currentOutputKw: 0,
      status: 'STANDBY',
      fuelConsumptionLhr: 0,
      electricalEfficiency: 0.37,
      runtimeHours: 0,
      healthPercent: 100,
      nextMaintenanceHours: 0,
      wasteHeatAvailableKw: 0,
      isRecoveringHeat: false,
    },
    {
      id: 'DG-03',
      name: 'Diesel Generator 3',
      type: 'Diesel Generator',
      capacityKw: 150,
      currentOutputKw: 0,
      status: 'STANDBY',
      fuelConsumptionLhr: 0,
      electricalEfficiency: 0.38,
      runtimeHours: 0,
      healthPercent: 100,
      nextMaintenanceHours: 0,
      wasteHeatAvailableKw: 0,
      isRecoveringHeat: false,
    },
  ],
  renewables: [
    {
      id: 'WT-01',
      name: 'Wind Turbines (3 units)',
      type: 'Wind Turbine',
      capacityKw: 100,
      currentOutputKw: 17.1,
      status: 'ONLINE',
      efficiencyPercent: 0,
      operatingMetrics: { windSpeedOrIrradiance: 8, unit: 'm/s' },
    },
    {
      id: 'PV-01',
      name: 'Solar Array',
      type: 'Solar Array',
      capacityKw: 50,
      currentOutputKw: 0,
      status: 'ONLINE',
      efficiencyPercent: 0,
      operatingMetrics: { windSpeedOrIrradiance: 0, unit: 'W/mÂ²' },
    },
  ],
  loads: [
    { id: 'L-CRITICAL', name: 'Critical Operations', category: 'LIFE_SAFETY', priority: 'P0', currentLoadKw: 15, peakLoadKw: 15, isFlexible: false, shedStatus: 'SERVED' },
    { id: 'L-IMPORTANT', name: 'Research & Labs', category: 'CRITICAL_RESEARCH', priority: 'P1', currentLoadKw: 25, peakLoadKw: 25, isFlexible: false, shedStatus: 'SERVED' },
    { id: 'L-FLEX', name: 'Workshop & Utilities', category: 'WORKSHOP_UTILITIES', priority: 'P2', currentLoadKw: 10, peakLoadKw: 10, isFlexible: true, shedStatus: 'SERVED' },
  ],
  topRecommendation: {
    title: 'Backend strategy unavailable',
    description: 'No authoritative EMS recommendation is available while the backend service is offline.',
    urgency: 'LOW',
    confidencePercent: 0,
    actionable: false,
    strategyCode: '',
  },
  horizonForecast: [
    { hourOffset: 0, timestamp: new Date().toISOString(), temperatureC: -20, windSpeedMs: 8, solarIrradianceWm2: 0, predictedTotalLoadKw: 50, predictedWindKw: 17.1, predictedSolarKw: 0, predictedDieselKw: 32.9, predictedBatteryKw: 0, batterySocPercent: 60, fuelRemainingLiters: 15000, dynamicReserveTargetPercent: 20, confidencePercent: 94, uncertaintyBandKw: 0, heatRecoveryOffsetKw: 30.91 },
    { hourOffset: 6, timestamp: new Date().toISOString(), temperatureC: -21, windSpeedMs: 8.8, solarIrradianceWm2: 0, predictedTotalLoadKw: 56.1, predictedWindKw: 20.6, predictedSolarKw: 0, predictedDieselKw: 35.5, predictedBatteryKw: 0, batterySocPercent: 25, fuelRemainingLiters: 14958, dynamicReserveTargetPercent: 24.1, confidencePercent: 80, uncertaintyBandKw: 0, heatRecoveryOffsetKw: 0 },
    { hourOffset: 12, timestamp: new Date().toISOString(), temperatureC: -19, windSpeedMs: 10.9, solarIrradianceWm2: 0, predictedTotalLoadKw: 55.3, predictedWindKw: 24.3, predictedSolarKw: 0, predictedDieselKw: 31.0, predictedBatteryKw: 0, batterySocPercent: 25, fuelRemainingLiters: 14921, dynamicReserveTargetPercent: 24.3, confidencePercent: 78, uncertaintyBandKw: 0, heatRecoveryOffsetKw: 0 },
    { hourOffset: 24, timestamp: new Date().toISOString(), temperatureC: -21, windSpeedMs: 8.5, solarIrradianceWm2: 0, predictedTotalLoadKw: 54.6, predictedWindKw: 20.0, predictedSolarKw: 0, predictedDieselKw: 34.6, predictedBatteryKw: 0, batterySocPercent: 25, fuelRemainingLiters: 14814, dynamicReserveTargetPercent: 24.8, confidencePercent: 76, uncertaintyBandKw: 0, heatRecoveryOffsetKw: 0 },
    { hourOffset: 48, timestamp: new Date().toISOString(), temperatureC: -23, windSpeedMs: 8.9, solarIrradianceWm2: 0, predictedTotalLoadKw: 53.7, predictedWindKw: 18.0, predictedSolarKw: 0, predictedDieselKw: 35.7, predictedBatteryKw: 0, batterySocPercent: 25, fuelRemainingLiters: 14470, dynamicReserveTargetPercent: 25.8, confidencePercent: 74, uncertaintyBandKw: 0, heatRecoveryOffsetKw: 0 },
    { hourOffset: 72, timestamp: new Date().toISOString(), temperatureC: -24, windSpeedMs: 9.0, solarIrradianceWm2: 0, predictedTotalLoadKw: 52.5, predictedWindKw: 17.0, predictedSolarKw: 0, predictedDieselKw: 35.5, predictedBatteryKw: 0, batterySocPercent: 25, fuelRemainingLiters: 14259, dynamicReserveTargetPercent: 26.7, confidencePercent: 72, uncertaintyBandKw: 0, heatRecoveryOffsetKw: 0 },
  ],
  provenance: {
    weatherSource: 'LIVE',
    powerTelemetrySource: 'ENGINEERING MODEL',
    forecastModelSource: 'ML',
    thermalModelSource: 'ENGINEERING MODEL',
  },
};

// Keep offline mode internally coherent with the backend reference Twin instead of the old demo-only values.
// This path is used only when the FastAPI service is unreachable and is explicitly marked SIMULATION/ESTIMATED.
(() => {
  const loads = fallbackSnapshot.loads;
  const originalLoad = loads.reduce((sum, item) => sum + item.currentLoadKw, 0);
  const targetLoad = 50;
  if (originalLoad > 0) {
    const scale = targetLoad / originalLoad;
    loads.forEach(item => { item.currentLoadKw *= scale; item.peakLoadKw *= scale; });
  }
  fallbackSnapshot.systemTime = new Date().toISOString();
  fallbackSnapshot.mode = 'SIMULATION';
  fallbackSnapshot.powerBalance = { totalGenerationKw: 50, totalLoadKw: targetLoad, netBalanceKw: 0, dieselGenKw: 32.9, windGenKw: 17.1, solarGenKw: 0, batteryPowerKw: 0, renewableSharePercent: 34.2, systemEfficiencyPercent: 100 };
  fallbackSnapshot.battery = { ...fallbackSnapshot.battery, capacityKwh: 500, currentChargeKwh: 300, socPercent: 60, currentPowerKw: 0, status: 'IDLE', minSocPercent: 20, maxSocPercent: 95 };
  fallbackSnapshot.fuel = { ...fallbackSnapshot.fuel, currentVolumeLiters: 15000, fillPercent: 75, currentConsumptionRateLhr: 13.2, estimatedAutonomyDays: 47.3 };
  fallbackSnapshot.generators = fallbackSnapshot.generators.map((g, i) => ({ ...g, capacityKw: 150, currentOutputKw: i === 0 ? 32.9 : 0, status: i === 0 ? 'ONLINE' : 'STANDBY' }));
  const baseTime = Date.parse(fallbackSnapshot.systemTime);
  fallbackSnapshot.horizonForecast = fallbackSnapshot.horizonForecast.map(p => ({
    ...p,
    timestamp: new Date(baseTime + p.hourOffset * 3600_000).toISOString(),
  }));
  fallbackSnapshot.renewables = fallbackSnapshot.renewables.map((r, i) => ({ ...r, currentOutputKw: i === 0 ? 17.1 : 0, status: 'ONLINE' }));
  fallbackSnapshot.provenance = { ...fallbackSnapshot.provenance, weatherSource: 'ESTIMATED', powerTelemetrySource: 'ENGINEERING MODEL', forecastModelSource: 'ENGINEERING MODEL' };
})();

const LAST_KNOWN_SNAPSHOT_KEY = 'polar_ems_last_known_snapshot_v1';
const LAST_KNOWN_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export function readCachedStationSnapshot(): StationSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(LAST_KNOWN_SNAPSHOT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { savedAt?: number; snapshot?: StationSnapshot };
    if (!parsed.snapshot || typeof parsed.savedAt !== 'number') return null;
    if (Date.now() - parsed.savedAt > LAST_KNOWN_MAX_AGE_MS) return null;
    if (!parsed.snapshot.stationName || !parsed.snapshot.powerBalance || !parsed.snapshot.battery || !parsed.snapshot.fuel) return null;
    return parsed.snapshot;
  } catch {
    return null;
  }
}

export function cacheStationSnapshot(snapshot: StationSnapshot): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(LAST_KNOWN_SNAPSHOT_KEY, JSON.stringify({ savedAt: Date.now(), snapshot }));
  } catch {
    // Storage may be unavailable in private/restricted browser contexts.
  }
}

export async function fetchStationSnapshot(hourOffset: number = 0, signal?: AbortSignal): Promise<StationSnapshot> {
  const data = await fetchJson<StationSnapshot>(`${API_BASE}/api/intelligence/snapshot?hourOffset=${hourOffset}`, { signal }, 8000);
  // The backend Digital Twin is authoritative for the displayed timestamp.
  // Do not replace it with a frontend clock, especially when viewing a projected state.
  return data;
}

export function getOfflineSnapshot(): StationSnapshot {
  return { ...fallbackSnapshot, mode: 'OFFLINE', weather: { ...fallbackSnapshot.weather, provenance: 'ESTIMATED' }, provenance: { ...fallbackSnapshot.provenance, weatherSource: 'ESTIMATED', powerTelemetrySource: 'ENGINEERING MODEL' } };
}

export type StrategyParams = { fuel?: boolean; renewables?: boolean; reliability?: boolean; emissions?: boolean; cost?: boolean; fuelWeight?: number; renewableWeight?: number; reliabilityWeight?: number; emissionWeight?: number; costWeight?: number; hours?: number; minReserve?: number; socMin?: number; socMax?: number; socRange?: string };

/** Read the operator's saved local advisory policy. Explicit strategy params always override it. */
export function getStoredEMSStrategyDefaults(): StrategyParams {
  const defaults: StrategyParams = { fuel: true, renewables: true, reliability: true, emissions: false, cost: false, minReserve: 20, socRange: '20 % - 95 %' };
  if (typeof window === 'undefined') return defaults;
  try {
    const raw = JSON.parse(window.localStorage.getItem('polar_ems_settings') || '{}');
    const reserve = Number(raw.reserveTarget);
    const mode = String(raw.aiAdvisoryMode || 'balanced');
    const byMode: Record<string, Partial<StrategyParams>> = {
      conservative: { fuel: true, renewables: false, reliability: true, emissions: false, cost: false },
      balanced: { fuel: true, renewables: true, reliability: true, emissions: false, cost: false },
      aggressive: { fuel: true, renewables: true, reliability: true, emissions: true, cost: false },
    };
    return { ...defaults, ...(byMode[mode] || byMode.balanced), minReserve: Number.isFinite(reserve) ? Math.max(15, Math.min(35, reserve)) : 20 };
  } catch {
    return defaults;
  }
}

function strategyUrl(params?: StrategyParams): string {
  const effective = params ?? getStoredEMSStrategyDefaults();
  const q = new URLSearchParams();
  q.set('fuel_weight', String(effective.fuelWeight ?? (effective.fuel ? 6 : 0)));
  q.set('renewable_weight', String(effective.renewableWeight ?? (effective.renewables ? 5 : 0)));
  q.set('reliability_weight', String(effective.reliabilityWeight ?? (effective.reliability ? 5 : 0)));
  q.set('emission_weight', String(effective.emissionWeight ?? (effective.emissions ? 3 : 0)));
  q.set('cost_weight', String(effective.costWeight ?? (effective.cost ? 3 : 0)));
  if (effective.hours != null) q.set('hours', String(effective.hours));
  q.set('min_reserve_percent', String(effective.minReserve ?? 20));
  const soc = (effective.socRange || '20 % - 95 %').match(/(\d+(?:\.\d+)?)\s*%\s*-\s*(\d+(?:\.\d+)?)\s*%/);
  q.set('soc_min_percent', soc ? soc[1] : String(effective.socMin ?? 20));
  q.set('soc_max_percent', soc ? soc[2] : String(effective.socMax ?? 95));
  return `${API_BASE}/ems/strategy?${q.toString()}`;
}

export async function fetchStationStrategy(
  params?: StrategyParams,
  signal?: AbortSignal,
): Promise<UnifiedStrategyResponse> {
  const data = await fetchJson<UnifiedStrategyResponse>(strategyUrl(params), { signal }, 15000);
  if (!data?.recommendedStrategy?.code) throw new Error('Decision engine returned no feasible strategy.');
  return data;
}

// Startup cache: the application prepares the default decision-engine result once.
// Tab components consume this same promise/result instead of launching a second request.
const strategyPrefetchCache = new Map<string, { promise: Promise<UnifiedStrategyResponse>; value?: UnifiedStrategyResponse; timestamp: number }>();

export function prefetchStationStrategy(params?: StrategyParams): Promise<UnifiedStrategyResponse> {
  const effective = params ?? getStoredEMSStrategyDefaults();
  const key = JSON.stringify(effective);
  const cached = strategyPrefetchCache.get(key);
  if (cached && Date.now() - cached.timestamp < 30000) return cached.promise;
  const promise = fetchStationStrategy(effective).then((value) => {
    const entry = strategyPrefetchCache.get(key);
    if (entry) entry.value = value;
    return value;
  }).catch((error) => {
    strategyPrefetchCache.delete(key);
    throw error;
  });
  strategyPrefetchCache.set(key, { promise, timestamp: Date.now() });
  return promise;
}

export async function fetchStationReport(hours: number = 24): Promise<any> {
  return fetchJson<any>(`${API_BASE}/reports?hours=${hours}`, {}, 20000);
}

/**
 * Lightweight analytics projection. This uses the existing authoritative
 * Digital Twin projection endpoint rather than the downloadable report
 * aggregator. The Analytics screen can therefore render from the same
 * projection data even if report generation/export is unavailable.
 */
const analyticsProjectionCache = new Map<number, { promise: Promise<any>; value?: any; timestamp: number }>();

export function prefetchStationAnalyticsProjection(hours: number = 24): Promise<any> {
  const cached = analyticsProjectionCache.get(hours);
  if (cached && Date.now() - cached.timestamp < 30000) return cached.promise;
  const promise = fetchJson<any>(`${API_BASE}/projection?hours=${hours}`, {}, 20000)
    .then((value) => {
      const entry = analyticsProjectionCache.get(hours);
      if (entry) entry.value = value;
      return value;
    })
    .catch((error) => {
      analyticsProjectionCache.delete(hours);
      throw error;
    });
  analyticsProjectionCache.set(hours, { promise, timestamp: Date.now() });
  return promise;
}

export async function fetchStationAnalyticsProjection(hours: number = 24, signal?: AbortSignal): Promise<any> {
  if (!signal) return prefetchStationAnalyticsProjection(hours);
  return fetchJson<any>(`${API_BASE}/projection?hours=${hours}`, { signal }, 20000);
}

export async function downloadStationReport(hours: number, format: 'csv' | 'pdf'): Promise<Blob> {
  const endpoint = format === 'csv' ? 'export.csv' : 'export.pdf';
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(`${API_BASE}/reports/${endpoint}?hours=${hours}`, { signal: controller.signal });
    if (!res.ok) throw new Error(`Report export API ${res.status}`);
    return await res.blob();
  } finally {
    window.clearTimeout(timer);
  }
}

export async function fetchStationResilience(hours: number = 72, signal?: AbortSignal, minReserve?: number): Promise<StationResilienceOverview> {
  const reserve = Number.isFinite(minReserve) ? minReserve : Number(getStoredEMSStrategyDefaults().minReserve ?? 20);
  return fetchJson<StationResilienceOverview>(`${API_BASE}/api/intelligence/resilience?hours=${hours}&min_reserve_percent=${encodeURIComponent(reserve)}`, { signal }, 30000);
}

// Resilience is one of the expensive intelligence views. Keep a shared startup
// promise so opening the tab can consume the already-prepared result.
const resiliencePrefetchCache = new Map<string, { promise: Promise<StationResilienceOverview>; value?: StationResilienceOverview; timestamp: number }>();

export function prefetchStationResilience(hours: number = 72): Promise<StationResilienceOverview> {
  const reserve = Number(getStoredEMSStrategyDefaults().minReserve ?? 20);
  const key = `${hours}:${reserve}`;
  const cached = resiliencePrefetchCache.get(key);
  if (cached && Date.now() - cached.timestamp < 60000) return cached.promise;
  const promise = fetchStationResilience(hours, undefined, reserve).then((value) => {
    const entry = resiliencePrefetchCache.get(key);
    if (entry) entry.value = value;
    return value;
  }).catch((error) => {
    resiliencePrefetchCache.delete(key);
    throw error;
  });
  resiliencePrefetchCache.set(key, { promise, timestamp: Date.now() });
  return promise;
}

export async function reevaluateStationResilience(hours: number = 72): Promise<StationResilienceOverview | null> {
  try {
    const reserve = Number(getStoredEMSStrategyDefaults().minReserve ?? 20);
    const res = await fetch(`${API_BASE}/api/intelligence/resilience/re-evaluate?hours=${hours}&min_reserve_percent=${encodeURIComponent(reserve)}`, {
      method: 'POST',
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) throw new Error(`Resilience re-evaluation API ${res.status}`);
    return await res.json() as StationResilienceOverview;
  } catch (err) {
    console.warn('API reevaluateStationResilience unavailable:', err);
    return null;
  }
}

export async function simulateFailureScenario(
  scenarioKey: string,
  hours: number = 24,
  startOffsetHours: number = 0,
  overrides: Record<string, number | boolean | string | null> = {},
  aiReoptimization: boolean = true,
): Promise<ResilienceScenarioResult> {
  const res = await fetch(`${API_BASE}/api/intelligence/resilience/simulate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenarioKey, hours, startOffsetHours, aiReoptimization, ...overrides }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`Resilience simulation API ${res.status}`);
  return await res.json();
}

export async function compareWhatIfScenario(
  scenarioKey: string,
  hours: number = 24,
  startOffsetHours: number = 0,
  overrides: Record<string, number | boolean | string | null> = {},
  aiReoptimization: boolean = true,
): Promise<import('./types').WhatIfComparisonResult> {
  const res = await fetch(`${API_BASE}/api/intelligence/resilience/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenarioKey, hours, startOffsetHours, aiReoptimization, ...overrides }),
    signal: AbortSignal.timeout(30000),
  });
  if (!res.ok) throw new Error(`What-if comparison API ${res.status}`);
  return await res.json() as import('./types').WhatIfComparisonResult;
}

export async function askStationBrain(prompt: string): Promise<{ answer: string; groundedFacts: string[] }> {
  try {
    const res = await fetch(`${API_BASE}/api/intelligence/assistant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
      signal: AbortSignal.timeout(15000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn('API askStationBrain fallback:', err);
  }

  throw new Error('Station Brain API unavailable');
}

export async function applyStationStrategy(strategyCode: string): Promise<unknown> {
  const code = strategyCode.toUpperCase();
  const res = await fetch(`${API_BASE}/ems/dispatch?strategy_id=${encodeURIComponent(code)}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Strategy apply failed: ${res.status}`);
  return res.json();
}


export interface FlexibleLoadOptimization {
  station: string;
  horizon_hours: number;
  flexible_load_available_kw: number;
  protected_load_kw: number;
  recommended_action: 'SHIFT_FLEXIBLE_LOAD' | 'HOLD';
  recommendation: {
    title: string; description: string; recommended_shift_kw: number;
    target_hour_offset: number | null; target_timestamp: string | null;
    expected_renewable_headroom_kw: number; predicted_diesel_kw: number;
  };
  windows: Array<{ hour_offset: number; timestamp: string; forecast_load_kw: number; renewable_available_kw: number; renewable_headroom_kw: number; recommended_shift_kw: number; predicted_diesel_kw: number; confidence_percent: number; score: number; }>;
  forecast_source: string; synthetic_weather: boolean; data_status: string; advisory_only: boolean; critical_load_protected: boolean;
  optimizer_summary?: Record<string, number>;
}

export async function fetchFlexibleLoadOptimization(hours: number = 24, signal?: AbortSignal): Promise<FlexibleLoadOptimization> {
  return fetchJson<FlexibleLoadOptimization>(`${API_BASE}/intelligence/flexible-load-optimization?hours=${hours}`, { signal }, 20000);
}

export interface HeatRecoveryIntelligence {
  station: string;
  horizon_hours: number;
  current: {
    hour_offset: number; timestamp: string; outdoor_temperature_c: number;
    heating_demand_kwth: number; diesel_output_kw: number; waste_heat_available_kwth: number;
    recovered_heat_kwth: number; electrical_heating_before_kw: number; electrical_heating_after_kw: number;
    avoided_electrical_heating_kw: number; thermal_offset_percent: number; fuel_equivalent_lph: number;
    confidence_percent: number; data_status: string;
  } | null;
  peak_recovery: any;
  forecast: Array<any>;
  summary: {
    current_heating_demand_kwth: number; current_recovered_heat_kwth: number;
    current_thermal_offset_percent: number; forecast_recovered_heat_kwhth: number;
    forecast_fuel_equivalent_liters: number; peak_recovery_kwth: number;
  };
  assumptions: Record<string, number>;
  data_status: string;
  advisory_only: boolean;
  station_state_mutated: boolean;
  provenance: string;
  note: string;
}

export interface FuelLogisticsIntelligence {
  station: string; horizon_hours: number; resupply_lead_time_hours: number;
  current_fuel_liters: number; tank_capacity_liters: number; emergency_reserve_liters: number; current_fill_percent: number;
  average_burn_lph: number; projected_fuel_liters: number; fuel_consumed_liters: number; estimated_autonomy_hours: number | null; estimated_hours_to_reserve: number | null;
  lead_time_projected_fuel_liters: number; reserve_breach_within_horizon: boolean; reserve_breach_at_lead_time: boolean; resupply_needed_now: boolean;
  recommended_resupply_quantity_liters: number; recommended_action: 'RESUPPLY_REQUIRED' | 'PLAN_RESUPPLY' | 'NO_IMMEDIATE_RESUPPLY';
  recommendation: { title: string; risk_level: 'LOW' | 'MEDIUM' | 'HIGH'; description: string; target_stock_liters: number };
  series: Array<{ hour_offset: number; timestamp: string; fuel_remaining_liters: number; diesel_power_kw: number; data_status: string }>;
  forecast_source: string; data_status: string; advisory_only: boolean; station_state_mutated: boolean; provenance: string; note: string;
}

export async function fetchFuelLogisticsIntelligence(hours: number = 72, leadTimeHours: number = 72, signal?: AbortSignal): Promise<FuelLogisticsIntelligence> {
  return fetchJson<FuelLogisticsIntelligence>(`${API_BASE}/intelligence/fuel-logistics-intelligence?hours=${hours}&resupply_lead_time_hours=${leadTimeHours}`, { signal }, 20000);
}

export async function fetchHeatRecoveryIntelligence(hours: number = 24, signal?: AbortSignal): Promise<HeatRecoveryIntelligence> {
  return fetchJson<HeatRecoveryIntelligence>(`${API_BASE}/intelligence/heat-recovery-intelligence?hours=${hours}`, { signal }, 45000);
}

export async function applyLoadAction(params: { shiftFlexibleKw?: number; shedFlexible?: boolean }): Promise<any> {
  const q = new URLSearchParams({ shift_flexible_kw: String(params.shiftFlexibleKw ?? 0), shed_flexible: String(params.shedFlexible ?? false) });
  const res = await fetch(`${API_BASE}/intelligence/load-action?${q.toString()}`, { method: 'POST', signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`Load action failed: ${res.status}`);
  return res.json();
}

export interface MissionSurvivalResult {
  station: string;
  generated_at: string;
  horizon_hours: number;
  ensemble_members: number;
  status: 'MISSION_SECURE' | 'WATCH' | 'SURVIVAL_MODE';
  survival_percent: number;
  survival_horizon_hours: { p10: number; p50: number; p90: number };
  limiting_factor: string;
  minimum_soc_percent: number;
  minimum_fuel_liters: number;
  median_diesel_runtime_hours: number;
  thermal_unserved_energy_kwh: number;
  recovered_waste_heat_kwh: number;
  hierarchical_control: { day_ahead: string; rolling_mpc: string; real_time_safety: string };
  station_state_mutated: boolean;
  recommendation: string;
  assumptions: Record<string, unknown>;
  data_status: string;
  provenance: string;
}

export interface DhruvaStrategyBenchmark {
  engine: string;
  benchmark_horizon_hours: number;
  compared_control_window_hours: number;
  baseline: { strategy: string; fuel_liters: number; unserved_energy_kwh: number; renewable_served_kwh: number; diesel_runtime_hours: number };
  diesel_only_baseline: { strategy: string; fuel_liters: number; unserved_energy_kwh: number; renewable_served_kwh: number; diesel_runtime_hours: number };
  dhruva: { strategy: string; fuel_liters: number; unserved_energy_kwh: number; renewable_served_kwh: number; diesel_runtime_hours: number; cvar_alpha: number };
  delta: { fuel_liters: number; fuel_percent: number; unserved_energy_kwh: number; diesel_runtime_hours: number; vs_diesel_only_fuel_liters: number; vs_diesel_only_fuel_percent: number };
  current_fuel_liters: number;
  fuel_capacity_liters: number;
  data_status: string;
  field_validated: boolean;
  station_state_mutated: boolean;
  reproducibility: string;
  limitations: string;
}

export async function fetchDhruvaStrategyBenchmark(hours = 168, signal?: AbortSignal): Promise<DhruvaStrategyBenchmark> {
  return fetchJson<DhruvaStrategyBenchmark>(`${API_BASE}/intelligence/strategy-benchmark?hours=${hours}`, { signal }, 45000);
}

export async function fetchMissionSurvival(params: {
  horizonHours?: number;
  ensembleMembers?: number;
  resupplyDelayHours?: number;
  windFactor?: number;
  solarFactor?: number;
  loadFactor?: number;
  generatorAvailable?: boolean;
  resupplyQuantityLiters?: number;
}, signal?: AbortSignal): Promise<MissionSurvivalResult> {
  return fetchJson<MissionSurvivalResult>(`${API_BASE}/intelligence/mission-survival`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      horizon_hours: params.horizonHours ?? 72,
      ensemble_members: params.ensembleMembers ?? 250,
      resupply_delay_hours: params.resupplyDelayHours ?? 0,
      wind_factor: params.windFactor ?? 1,
      solar_factor: params.solarFactor ?? 1,
      load_factor: params.loadFactor ?? 1,
      generator_available: params.generatorAvailable ?? true,
      resupply_quantity_liters: params.resupplyQuantityLiters ?? 5000,
    }),
    signal,
  }, 30000);
}


export interface MissionAssuranceResult {
  engine: string; station: string; horizon_hours: number; ensemble_members_per_scenario: number; scenario_count: number;
  worst_case: { scenario: string; survival_percent: number; p10_survival_hours: number; p50_survival_hours: number; minimum_fuel_liters: number; thermal_unserved_kwh: number; generator_available: boolean; resupply_delay_hours: number };
  recommended_posture: string; scenario_matrix: Array<{ scenario: string; survival_percent: number; p10_survival_hours: number; p50_survival_hours: number; minimum_fuel_liters: number; thermal_unserved_kwh: number; generator_available: boolean; resupply_delay_hours: number }>;
  hierarchy: string[]; station_state_mutated: boolean; data_status: string; field_validated: boolean; provenance: string; limitations: string;
}

export async function fetchMissionAssurance(horizonHours = 168, ensembleMembers = 300, signal?: AbortSignal): Promise<MissionAssuranceResult> {
  return fetchJson<MissionAssuranceResult>(`${API_BASE}/intelligence/mission-assurance?horizon_hours=${horizonHours}&ensemble_members=${ensembleMembers}`, { signal }, 90000);
}

export async function fetchDhruvaDecisionTrace(hours = 24, signal?: AbortSignal): Promise<import('./types').DhruvaDecisionTrace> {
  return fetchJson<import('./types').DhruvaDecisionTrace>(`${API_BASE}/decision/trace?hours=${hours}`, { signal }, 30000);
}

export async function fetchDhruva72hStressTest(signal?: AbortSignal): Promise<import('./types').DhruvaStressTest72h> {
  return fetchJson<import('./types').DhruvaStressTest72h>(`${API_BASE}/decision/stress-test/72h`, { signal }, 60000);
}

export interface DhruvaOperationalPosture {
  posture: 'NORMAL' | 'CONTINGENCY_READY' | 'SURVIVAL_MODE';
  priority: 'NORMAL' | 'WATCH' | 'CRITICAL';
  triggered: boolean;
  reasons: string[];
  recommended_actions: string[];
  dynamic_reserve_percent: number;
  battery_soc_percent: number;
  fuel_remaining_liters: number;
  fuel_autonomy: { p50_days?: number; p10_days?: number; safe_days?: number; status?: string };
  maintenance?: { health?: { dispatch_penalty_active?: boolean } };
  data_status: string;
  advisory_only: boolean;
  station_state_mutated: boolean;
}

export interface DhruvaResupplyDecision {
  decision_id: string;
  action: string;
  priority: string;
  current_fuel_liters: number;
  emergency_reserve_liters: number;
  safe_autonomy_days: number;
  lead_time_hours: number;
  projected_fuel_at_lead_time_liters: number;
  target_stock_after_delivery_liters: number;
  recommended_quantity_liters: number;
  reason: string;
  data_status: string;
  advisory_only: boolean;
  station_state_mutated: boolean;
}

export async function fetchDhruvaOperationalPosture(hours = 24, signal?: AbortSignal): Promise<DhruvaOperationalPosture> {
  return fetchJson<DhruvaOperationalPosture>(`${API_BASE}/intelligence/operational-posture?hours=${hours}`, { signal }, 30000);
}

export async function fetchDhruvaResupplyDecision(hours = 168, leadTimeHours = 72, signal?: AbortSignal): Promise<DhruvaResupplyDecision> {
  return fetchJson<DhruvaResupplyDecision>(`${API_BASE}/intelligence/resupply-decision?hours=${hours}&lead_time_hours=${leadTimeHours}`, { signal }, 30000);
}

export async function recordDhruvaOperatorAction(decisionId: string, action: 'APPROVE' | 'REJECT' | 'DEFER' | 'ACKNOWLEDGE', notes = ''): Promise<any> {
  return fetchJson<any>(`${API_BASE}/intelligence/operator-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision_id: decisionId, action, operator: 'MISSION_CONTROL_OPERATOR', notes }),
  }, 15000);
}

export interface MissionAutopilotResult {
  engine: string;
  decision_id: string;
  mission_horizon_hours: number;
  current_posture: 'NORMAL' | 'CONSERVATION' | 'CONTINGENCY' | 'SURVIVAL';
  posture_reasons: string[];
  now: string;
  prepare_for: string;
  change_strategy_when: string;
  worst_case: { scenario: string; survival_percent: number; p10_survival_hours: number; p50_survival_hours: number; minimum_fuel_liters: number; thermal_unserved_kwh: number; generator_available: boolean; resupply_delay_hours: number };
  timeline: Array<{ window: string; action: string }>;
  strategy_options: Array<{ strategy: string; mode: string; action: string; approval_required: boolean; trigger: string }>;
  counterfactual_lab: Array<Record<string, unknown>>;
  decision_trace: { steps: string[]; selected_posture: string; safety_passed: boolean; dynamic_reserve_percent: number; forecast_confidence_percent: number; planning_case: string };
  hierarchical_control: string[];
  operator_gate: { approval_required_for_strategy_change: boolean; automatic_equipment_control: boolean; recommended_action_is_advisory: boolean };
  provenance: { data_status: string; field_validated: boolean; calibrated_failure_probability: boolean; station_state_mutated: boolean };
  limitations: string;
}

export async function fetchMissionAutopilot(horizonHours = 168, ensembleMembers = 120, signal?: AbortSignal): Promise<MissionAutopilotResult> {
  return fetchJson<MissionAutopilotResult>(`${API_BASE}/intelligence/mission-autopilot?hours=${horizonHours}&ensemble_members=${ensembleMembers}`, { signal }, 90000);
}

export interface UltimateAICoreResult {
  engine: string;
  state_preserving: boolean;
  field_validated: boolean;
  models: Record<string, any>;
  mission_risk: { score: number; reserve_target_percent: number; regime: string };
  governance: { human_approval_required: boolean; safety_shield_authoritative: boolean; automatic_equipment_control: boolean; model_promotion_automatic: boolean };
  limitations: string;
}

export async function fetchUltimateAICore(signal?: AbortSignal): Promise<UltimateAICoreResult> {
  return fetchJson<UltimateAICoreResult>(`${API_BASE}/intelligence/ultimate-ai`, { signal }, 30000);
}
