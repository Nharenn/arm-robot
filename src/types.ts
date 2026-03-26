export interface JointData {
  J1: number;
  J2: number;
  J3: number;
  J4: number;
  J5: number;
  J6: number;
}

export interface PIDData {
  setpoint: number;
  error: number;
  output: number;
  p: number;
  i: number;
  d: number;
}

export interface SensorData {
  temp: number;
  force: number;
}

export interface HistoryEntry {
  t: number;
  sp: number;
  out: number;
  err: number;
  p: number;
  i: number;
  d: number;
}

export type LayoutMode = "mobile" | "tablet" | "compact" | "desktop";
