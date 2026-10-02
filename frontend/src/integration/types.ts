/**
 * DHRUVA Client-side Types
 * Aligned with backend models for Maitri Station, Antarctica.
 */

export type NavigationTab = 
  | 'command-center' 
  | 'optimization' 
  | 'energy' 
  | 'assets-loads' 
  | 'simulator' 
  | 'resilience' 
  | 'analytics';

export type SystemMode = 'ONLINE' | 'OFFLINE' | 'SIMULATION';

export interface WeatherTelemetry {
  temperature: number;
  apparentTemperature?: number;
  humidity: number;
  windSpeed: number;
  windDirection: string;
  visibilityKm: number;
  condition: string;
  solarRadiation: number;
  cloudCover: number;
  pressureHpa: number;
  snowfallCm: number;
  polarDayNight: 'Polar Night' | 'Polar Day' | 'Equinox Transition';
  provenance: string;
  lastUpdated: string;
  confidence: number;
}

export interface GeneratorAsset {
  id: string;
  name: string;
  type: 'Diesel Generator';
  capacityKw: number;
  currentOutputKw: number;
  status: 'ONLINE' | 'STANDBY' | 'MAINTENANCE' | 'OFFLINE';
  fuelConsumptionLhr: number;
  electricalEfficiency: number;
  runtimeHours: number;
  healthPercent: number;
  nextMaintenanceHours: number;
  wasteHeatAvailableKw: number;
  isRecoveringHeat: boolean;
}

export interface RenewableAsset {
  id: string;
  name: string;
  type: 'Wind Turbine' | 'Solar Array';
  capacityKw: number;
  currentOutputKw: number;
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  efficiencyPercent: number;
  operatingMetrics: {
    windSpeedOrIrradiance: number;
    unit: string;
  };
}

export interface BatterySystem {
  capacityKwh: number;
  currentChargeKwh: number;
  socPercent: number;
  currentPowerKw: number;
  status: 'CHARGING' | 'DISCHARGING' | 'IDLE';
  minSocPercent: number;
  maxSocPercent: number;
  temperatureC: number;
  healthPercent: number;
  cyclesCompleted: number;
}

export interface FuelStorage {
  capacityLiters: number;
  currentVolumeLiters: number;
  fillPercent: number;
  currentConsumptionRateLhr: number;
  estimatedAutonomyDays: number | null;
  emergencyReserveLiters: number;
  lastDeliveryDaysAgo: number;
  nextScheduledDeliveryDays: number;
}

export interface ThermalState {
  indoorTemperatureC: number;
  outdoorTemperatureC: number;
  totalHeatingDemandKw: number;
  recoveredHeatKw: number;
  electricalHeatingKw: number;
  heatRecoveryEfficiency: number;
  heatRecoveryEnabled: boolean;
  thermalOffsetPercent: number;
}

export interface StationLoad {
  id: string;
  name: string;
  category: 'LIFE_SAFETY' | 'CRITICAL_RESEARCH' | 'WORKSHOP_UTILITIES' | 'HEATING' | 'WATER_PUMPS' | 'SECONDARY';
  priority: 'P0' | 'P1' | 'P2';
  currentLoadKw: number;
  peakLoadKw: number;
  isFlexible: boolean;
  flexibilityWindow?: string;
  potentialSavingsLiters?: number;
  shedStatus: 'SERVED' | 'SHED';
}

export interface DynamicReserve {
  currentReservePercent: number;
  targetReservePercent: number;
  spinningReserveKw: number;
  status: 'ADEQUATE' | 'ELEVATED_WATCH' | 'CRITICAL_SHORTFALL';
  drivers: {
    windRisk: number;
    snowfallRisk: number;
    temperatureColdStress: number;
    forecastConfidence: number;
  };
  reasoning: string;
}

export interface ForecastHorizonStep {
  hourOffset: number;
  timestamp: string;
  temperatureC: number;
  windSpeedMs: number;
  solarIrradianceWm2: number;
  predictedTotalLoadKw: number;
  predictedWindKw: number;
  predictedSolarKw: number;
  predictedDieselKw: number;
  predictedBatteryKw: number;
  batterySocPercent: number;
  fuelRemainingLiters: number;
  dynamicReserveTargetPercent: number;
  confidencePercent: number;
  uncertaintyBandKw: number;
  heatRecoveryOffsetKw: number;
}

export interface StationSnapshot {
  stationName: string;
  selectedHourOffset?: number;
  location: string;
  coordinates: { lat: number; lng: number };
  systemTime: string;
  mode: SystemMode;
  weather: WeatherTelemetry;
  powerBalance: {
    totalGenerationKw: number;
    totalLoadKw: number;
    netBalanceKw: number;
    dieselGenKw: number;
    windGenKw: number;
    solarGenKw: number;
    batteryPowerKw: number;
    renewableSharePercent: number;
    systemEfficiencyPercent: number;
  };
  battery: BatterySystem;
  fuel: FuelStorage;
  thermal: ThermalState;
  reserve: DynamicReserve;
  generators: GeneratorAsset[];
  renewables: RenewableAsset[];
  loads: StationLoad[];
  /** Full backend decision-engine response used by Optimization & Advisory. */
  decisionStrategy?: UnifiedStrategyResponse;
  topRecommendation: {
    title: string;
    description: string;
    urgency: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    confidencePercent: number;
    actionable: boolean;
    strategyCode: string;
  };
  horizonForecast: ForecastHorizonStep[];
  provenance: {
    weatherSource: string;
    powerTelemetrySource: string;
    forecastModelSource: string;
    thermalModelSource: string;
  };
}

export interface StrategyOption {
  id: string;
  code: 'A' | 'B' | 'C' | 'D';
  name: string;
  description: string;
  fuelConsumptionDeltaL: number;
  renewableUtilizationPercent: number;
  reserveLevelPercent: number;
  co2DeltaPercent: number;
  confidencePercent: number;
  isRecommended: boolean;
  generatorsOnline: string[];
  batteryAction: 'CHARGE' | 'DISCHARGE' | 'HOLD';
  projectedFuelL: number;
  /** @deprecated Use projectedFuelL; retained for backward compatibility. */
  projectedFuel24hL?: number;
  unservedLoadKw: number;
  dispatchSchedule?: {
    hourOffset: number;
    loadKw: number;
    solarKw: number;
    windKw: number;
    renewableKw: number;
    batteryChargeKw: number;
    batteryDischargeKw: number;
    dieselKw: number;
    socPercent: number;
  }[];
}

export interface EnergyOpportunity {
  id: string;
  title: string;
  category: 'HEAT_RECOVERY' | 'LOAD_SHIFT' | 'BATTERY_TIMING';
  description: string;
  metricLabel: string;
  metricValue: string;
  potentialSavings: string;
  isApplied: boolean;
}

export interface UnifiedStrategyResponse {
  recommendedStrategy: StrategyOption;
  alternativeStrategies: StrategyOption[];
  reasoningPoints: { icon: string; title: string; explanation: string }[];
  opportunities: EnergyOpportunity[];
  impactComparison: {
    strategyName: string;
    fuelLiters24h: number;
    reservePercent: number;
    renewableSharePercent: number;
  }[];
  predictedPeakLoadKw: number;
  predictedAvgWindMs: number;
  predictedPeakSolarKw: number;
  predictedMinTempC: number;
  optimalityClaim: false;
}

export interface SimulationPoint {
  timestamp: string;
  hour_offset: number;
  solar_power_kw: number;
  wind_power_kw: number;
  diesel_power_kw: number;
  load_kw: number;
  served_load_kw: number;
  shed_load_kw: number;
  battery_soc_percent: number;
  fuel_remaining_liters: number;
  outdoor_temperature_celsius?: number;
  wind_speed_mps?: number;
  solar_irradiance_w_m2?: number;
  indoor_temperature_celsius?: number;
  operating_mode?: string;
  energy_status?: string;
}

export interface ResilienceScenarioResult {
  scenarioId: string;
  title: string;
  description: string;
  failureDurationHours: number;
  totalGenerationKw: number;
  generationDeltaPercent: number;
  fuelConsumptionLhr: number;
  fuelDeltaPercent: number;
  batterySocMinPercent: number;
  reserveLevelPercent: number;
  unservedLoadKw: number;
  /** Canonical energy quantity; unservedLoadKw is retained for backward compatibility. */
  loadShedEnergyKwh?: number;
  criticalLoadCoveragePercent: number;
  resilienceOutcome: 'OPTIMAL_RECOVERY' | 'MITIGATED' | 'CRITICAL_RISK';
  aiAnalysis: string;
  recommendedActions: string[];
  points?: SimulationPoint[];
  aiReoptimizationApplied?: boolean;
}

export interface WhatIfComparisonMetrics {
  averageGenerationKw: number;
  fuelConsumedLiters: number;
  fuelConsumptionLhr: number;
  renewableSharePercent: number;
  minimumSocPercent: number;
  finalSocPercent: number;
  finalFuelLiters: number;
  loadShedEnergyKwh: number;
  criticalLoadCoveragePercent: number;
  serviceLevelPercent: number;
  blackoutEvent: boolean;
  autonomyDays: number | null;
  points?: SimulationPoint[];
  aiReoptimizationApplied?: boolean;
}

export interface WhatIfComparisonResult {
  scenarioId: string;
  title: string;
  description: string;
  horizonHours: number;
  startOffsetHours: number;
  baseline: WhatIfComparisonMetrics;
  whatIf: WhatIfComparisonMetrics;
  delta: {
    fuelConsumedLiters: number;
    fuelConsumptionLhr: number;
    renewableSharePercent: number;
    minimumSocPercent: number;
    finalFuelLiters: number;
    loadShedEnergyKwh: number;
    criticalLoadCoveragePercent: number;
    averageGenerationKw: number;
  };
  forecastSource: string;
  forecastSyntheticWeather: boolean;
  forecastConfidence?: Record<string, unknown>;
  dataStatus: string;
  aiReoptimizationApplied: boolean;
}

export interface StationRiskAssessment {
  horizonHours: number;
  overallRiskPercent: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  blackoutRiskPercent: number;
  components: {
    criticalLoadRiskPercent: number;
    batterySocRiskPercent: number;
    fuelReserveRiskPercent: number;
    serviceLevelRiskPercent: number;
    forecastUncertaintyRiskPercent: number;
    extremeWeatherRiskPercent: number;
  };
  isAdvisory: boolean;
  calibrationNote: string;
  riskSeries?: Array<{
    hour_offset: number;
    overall: number;
    critical: number;
    battery: number;
    fuel: number;
    service: number;
    uncertainty: number;
    weather: number;
  }>;
}

export interface StationResilienceOverview {
  overallScore: number;
  status: 'OPTIMAL' | 'GOOD' | 'WATCH' | 'CRITICAL';
  metrics: {
    powerReliability: number;
    fuelSecurity: number;
    generatorRedundancy: number;
    batteryAvailability: number;
    renewableStability: number;
    criticalLoadProtection: number;
  };
  nPlusOneStatus: {
    generators: string;
    battery: string;
    windTurbines: string;
    solarArray: string;
  };
  fuelSurvivalDays: number | null;
  reserveForecast: { hourOffset: number; currentPlanPercent: number; recommendedPercent: number; minimumPercent: number }[];
  riskAssessment: { label: string; level: 'LOW' | 'MEDIUM' | 'HIGH'; source: string }[];
  dataStatus?: string;
  source?: string;
  criticalLoadCoverage: {
    name: string;
    isProtected: boolean;
    priority: string;
    requestedKw?: number;
    servedKw?: number;
    coveragePercent?: number;
  }[];
  reserveSemantics?: {
    minimumPercent: number;
    targetPercent: number;
    currentPercent: number;
    description: string;
  };
  activeThreats: {
    title: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH';
    timing: string;
    description: string;
  }[];
  recommendedProactiveActions: string[];
  scenarios: Record<string, ResilienceScenarioResult>;
}

export interface DhruvaDecisionTrace {
  engine: string;
  data_status: string;
  horizon_hours: number;
  decision: string;
  decision_reason: string;
  decision_id: string;
  dynamic_reserve_percent: number;
  planning_case?: string;
  uncertainty?: {
    average_confidence_percent: number;
    minimum_confidence_percent: number;
    bands: {
      load_kw: { p10: number; p50: number; p90: number };
      solar_kw: { p10: number; p50: number; p90: number };
      wind_kw: { p10: number; p50: number; p90: number };
    };
    interpretation: string;
  };
  asset_health?: {
    battery_soh_percent: number;
    generator_health_percent: number;
    battery_condition: string;
    generator_condition: string;
    dispatch_penalty_active: boolean;
  };
  fuel_autonomy?: {
    current_fuel_liters: number;
    p50_days: number;
    p10_days: number;
    safe_days: number;
    status: string;
  };
  safety_validation: {
    passed: boolean;
    violations: { hour: number; code: string; severity: string }[];
    hard_violation_count: number;
    critical_load_protected: boolean;
    minimum_soc_percent: number;
    final_fuel_liters: number;
    reserve_margin_percent: number;
  };
  baseline_comparison: {
    baseline: { fuel_liters: number; renewable_share_percent: number; service_level_percent: number; unserved_energy_kwh: number; final_fuel_liters: number };
    dhruva: { fuel_liters: number; renewable_share_percent: number; service_level_percent: number; unserved_energy_kwh: number; minimum_soc_percent: number };
    delta: { fuel_saved_liters: number; service_level_delta_percent: number; unserved_energy_delta_kwh: number };
  };
  trace: { step: number; title: string; detail: string }[];
}

export interface DhruvaStressTest72h {
  engine: string;
  horizon_hours: number;
  events: { hour_offset: number; event: string }[];
  metrics: {
    fuel_consumed_liters: number;
    final_fuel_liters: number;
    minimum_battery_soc_percent: number;
    critical_load_failure_steps: number;
    critical_load_coverage_percent: number;
    load_shed_energy_kwh: number;
    service_level_percent: number;
    renewable_share_percent: number;
    safety_violations: number;
  };
  success: boolean;
  points: { hour_offset: number; event: string; battery_soc_percent: number; fuel_remaining_liters: number; served_load_kw: number; critical_load_kw: number; shed_load_kw: number }[];
}
