import React from "react";

export interface SensorGaugeProps {
  label: string;
  value: number | string;
  unit: string;
  pct: number;
  colorClass: string;
  bgClass: string;
}

export function SensorGauge({ label, value, unit, pct, colorClass, bgClass }: SensorGaugeProps) {
  return (
    <div className="mb-3.5">
      <div className="flex justify-between items-baseline mb-1.5">
        <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">{label}</span>
        <span className={`text-xl font-bold font-sans tabular-nums ${colorClass}`}>
          {value}<span className="text-[11px] font-normal text-slate-400 dark:text-slate-500 ml-0.5">{unit}</span>
        </span>
      </div>
      <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-200 ${bgClass}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export interface ParamSliderProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  accentClass: string;
}

export function ParamSlider({ label, value, onChange, min, max, step, accentClass }: ParamSliderProps) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <span className={`text-sm font-bold font-mono w-6 text-right ${accentClass}`}>{label}</span>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(+e.target.value)}
        className={`flex-1 h-1.5 rounded-lg appearance-none cursor-pointer bg-slate-200 dark:bg-slate-700 accent-current ${accentClass}`}
      />
      <div className="flex items-center bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 rounded-lg px-2 py-1 w-16">
        <input
          type="number"
          min={min} max={max} step={step}
          value={value}
          onChange={e => onChange(e.target.value === "" ? 0 : +e.target.value)}
          className="w-full text-sm font-mono text-slate-600 dark:text-slate-300 bg-transparent border-none outline-none text-right appearance-none"
        />
      </div>
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm dark:shadow-[0_1px_4px_rgba(0,0,0,0.4)] transition-colors overflow-hidden shrink-0 ${className}`}>
      {children}
    </div>
  );
}

export function CardLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 tracking-wide mb-4 flex items-center gap-1.5">
      {children}
    </div>
  );
}
