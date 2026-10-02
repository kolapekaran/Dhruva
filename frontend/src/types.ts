export type TabType =
  | 'command-center'
  | 'optimization'
  | 'energy'
  | 'assets-loads'
  | 'simulator'
  | 'resilience'
  | 'analytics';

export interface StationWeather {
  temp: number;
  condition: string;
  windSpeed: number;
  windDirection: string;
  visibility: number;
  humidity: number;
}

export interface StationNode {
  id: string;
  name: string;
  type: 'generation' | 'storage' | 'load' | 'thermal' | 'fuel';
  subType?: string;
  capacity?: string;
  output?: string;
  powerKw: number;
  status: 'Online' | 'Standby' | 'Maintenance' | 'Charging' | 'Discharging' | 'Normal';
  x: number; // percentage in twin 0-100
  y: number; // percentage in twin 0-100
  criticality?: string;
  peakLoad?: string;
  indoorTemp?: string;
  details?: string;
  category: 'Renewable' | 'Diesel' | 'Battery' | 'Building' | 'Infrastructure' | 'Thermal';
}

export interface EnergyFlowData {
  generationTotalKw: number;
  loadTotalKw: number;
  balanceKw: number;
  renewableSharePercent: number;
  energyEfficiencyPercent: number;
  batterySocPercent: number;
  batteryAvailableKwh: number;
  batteryTotalKwh: number;
  fuelLiters: number;
  fuelCapacityLiters: number;
  fuelAutonomyDays: number;
  dynamicReservePercent: number;
  thermalRecoveredKw: number;
  thermalDemandKw: number;
}

export interface AssetRecord {
  id: string;
  name: string;
  type: string;
  status: 'Online' | 'Standby' | 'Offline' | 'Maintenance';
  capacity: string;
  currentOutput: string;
  efficiency: string;
  health: string;
  nextMaintenance: string;
  fuelRate?: string;
  runtime?: string;
}

export interface SimulatorScenario {
  id: string;
  name: string;
  description: string;
  category: string;
  iconName: string;
  impactGen: string;
  impactFuel: string;
  impactSoc: string;
  impactReserve: string;
  impactUnserved: string;
  aiAnalysis: string;
}
